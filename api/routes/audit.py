"""审核接口 — 事前/事中/事后三阶段审核 + 结果查询"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import json

from ..deps import get_db_conn, db_cursor, get_engine, model_to_claim_event, model_to_claim_line, result_to_dict
from ..schemas import (
    PreCheckRequest, PreCheckResponse, PreCheckItemModel,
    ConcurrentAuditRequest, PostAuditRequest,
    AuditResponse, AuditResultItem,
)
from audit_engine import ClaimEvent, ClaimLine

router = APIRouter(tags=["审核"])


@router.post("/api/v1/audit/precheck", summary="事前医嘱审核",
             response_model=PreCheckResponse,
             description="""
医生开单时实时调用。仅执行 pre_check 阶段规则（高置信度、明确违规规则），
响应时间 < 200ms。

**决策逻辑**：
- `block`：存在 severity=violation 的规则触发，建议拦截
- `warn`：存在 severity=suspicious 的规则触发，建议提醒
- `pass`：无规则触发
             """)
def precheck(req: PreCheckRequest):
    setl_id = f"PRECHECK_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    claim = ClaimEvent(
        setl_id=setl_id,
        gend=req.gend, brdy=req.brdy, med_type=req.med_type,
        hosp_lv=req.hosp_lv, dept=req.dept, insutype=req.insutype,
        main_diag_code=req.main_diag_code, main_diag_name=req.main_diag_name,
        diag_codes=req.diag_codes, main_oprn_code=req.main_oprn_code,
    )
    lines = []
    for i, item in enumerate(req.items):
        lines.append(ClaimLine(
            setl_id=setl_id, feedetl_sn=f"PRE_{i+1}", line_no=i+1,
            list_type=item.list_type, med_list_name=item.med_list_name,
            med_list_codg=item.med_list_codg, cnt=item.cnt, pric=item.pric,
            chrgitm_lv=item.chrgitm_lv, hosp_appr_flag=item.hosp_appr_flag,
            oprn_code_used=item.oprn_code_used,
        ))

    engine = get_engine()
    try:
        results = engine.audit_claim(claim, lines, stage="pre_check")
    finally:
        engine.close()

    alerts = [result_to_dict(r) for r in results]
    block_count = sum(1 for a in alerts if a["verdict"] == "violation")
    warn_count = sum(1 for a in alerts if a["verdict"] == "warning")
    decision = "block" if block_count > 0 else ("warn" if warn_count > 0 else "pass")

    return PreCheckResponse(
        decision=decision, total_items=len(req.items),
        total_alerts=len(alerts), block_count=block_count,
        warn_count=warn_count, alerts=alerts,
    )


@router.post("/api/v1/audit/end_check", summary="事中出科审核",
             response_model=AuditResponse,
             description="""
结算前调用。执行 end_check 阶段全量规则审核（柱1-3逐行 + 柱4事件级预检），
含跨行互斥判断。
             """)
def end_check_audit(req: ConcurrentAuditRequest):
    claim = model_to_claim_event(req.claim_event)
    lines = [model_to_claim_line(l) for l in req.claim_lines]
    for i, line in enumerate(lines):
        if not line.line_no:
            line.line_no = i + 1
        if not line.setl_id:
            line.setl_id = claim.setl_id

    engine = get_engine()
    try:
        if req.persist:
            engine.save_claim(claim)
            engine.save_lines(lines)
        results = engine.audit_claim(claim, lines, stage="end_check")
        if req.persist:
            engine.save_results(results)
    finally:
        engine.close()

    return _build_audit_response(claim.setl_id, "end_check", len(lines), results)


@router.post("/api/v1/audit/postaudit", summary="事后结算监管",
             response_model=AuditResponse,
             description="""
结算后调用。执行 post_audit 阶段全量规则 + DRG深度分析（高套分组/分解住院/低标入院等）。
             """)
def post_audit(req: PostAuditRequest):
    claim = model_to_claim_event(req.claim_event)
    lines = [model_to_claim_line(l) for l in req.claim_lines]
    for i, line in enumerate(lines):
        if not line.line_no:
            line.line_no = i + 1
        if not line.setl_id:
            line.setl_id = claim.setl_id

    engine = get_engine()
    try:
        if req.persist:
            engine.save_claim(claim)
            engine.save_lines(lines)
        results = engine.audit_claim(claim, lines, stage="post_audit")
        if req.persist:
            engine.save_results(results)
    finally:
        engine.close()

    return _build_audit_response(claim.setl_id, "post_audit", len(lines), results)


@router.get("/api/v1/audit/results/{setl_id}", summary="查询审核结果")
def get_audit_results(setl_id: str):
    """根据结算ID查询已持久化的审核结果"""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_result WHERE setl_id = ? ORDER BY line_no, pillar",
            (setl_id,)
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"未找到结算ID {setl_id} 的审核结果")
        results = []
        for row in rows:
            d = dict(row)
            if d.get("matched_facts"):
                try:
                    d["matched_facts"] = json.loads(d["matched_facts"])
                except json.JSONDecodeError:
                    pass
            results.append(d)
        return {"code": 0, "setl_id": setl_id, "total": len(results), "results": results}


def _build_audit_response(setl_id: str, stage: str, total_lines: int,
                          results: list) -> AuditResponse:
    """构建审核响应"""
    items = [result_to_dict(r) for r in results]
    violation_count = sum(1 for r in results if r.verdict == "violation")
    warning_count = sum(1 for r in results if r.verdict == "warning")
    info_count = sum(1 for r in results if r.verdict == "info")
    has_block = any(r.action == "block" for r in results)

    return AuditResponse(
        setl_id=setl_id, stage=stage, total_lines=total_lines,
        total_results=len(results), violation_count=violation_count,
        warning_count=warning_count, info_count=info_count,
        has_block=has_block, results=items,
    )
