"""规则沙箱接口 — 规则列表/测试/模板/统计/前端页面"""

import time as _time

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_cursor, get_engine, result_to_dict
from ..schemas import SandboxTestRequest
from audit_engine import ClaimEvent, ClaimLine

router = APIRouter(tags=["规则沙箱"])


@router.get("/api/v1/sandbox/rules", summary="规则列表查询(含条件DSL)")
def sandbox_rules(
    keyword: str = Query("", description="搜索关键词(规则编码/中文名/类别)"),
    pillar: str = Query("", description="柱别: YP/FW/HC/BZ"),
    stage: str = Query("", description="阶段: pre_check/end_check/post_audit"),
    category: str = Query("", description="规则类别"),
    limit: int = Query(100, description="返回数量"),
):
    """查询规则列表,返回完整条件DSL供沙箱展示"""
    with db_cursor() as conn:
        sql = """SELECT id, rule_code, rule_code_cn, rule_name, rule_category,
                        pillar, stage, severity, action, is_active,
                        conditions, source_reference, source_batch
                 FROM rule_items WHERE is_active=1"""
        params = []
        if keyword:
            sql += " AND (rule_code LIKE ? OR rule_code_cn LIKE ? OR rule_category LIKE ? OR source_reference LIKE ?)"
            params.extend([f"%{keyword}%"] * 4)
        if pillar:
            sql += " AND pillar=?"
            params.append(pillar)
        if stage:
            sql += " AND stage=?"
            params.append(stage)
        if category:
            sql += " AND rule_category=?"
            params.append(category)
        sql += " ORDER BY rule_code LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return {"code": 0, "total": len(rows), "items": [dict(r) for r in rows]}


@router.get("/api/v1/sandbox/rules/{rule_code}", summary="单条规则详情")
def sandbox_rule_detail(rule_code: str):
    """获取单条规则的完整定义"""
    with db_cursor() as conn:
        row = conn.execute(
            "SELECT * FROM rule_items WHERE rule_code=? AND is_active=1",
            (rule_code,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"规则 {rule_code} 不存在或未激活")
        return {"code": 0, "rule": dict(row)}


@router.post("/api/v1/sandbox/test", summary="执行规则测试")
def sandbox_test(req: SandboxTestRequest):
    """提交费用结算数据,执行审核引擎,返回触发结果和推理链"""
    event = ClaimEvent(
        setl_id=f"SANDBOX_{_time.strftime('%Y%m%d%H%M%S')}",
        med_type=req.med_type, gend=req.gend, brdy=req.brdy,
        hosp_lv=req.hosp_lv, dept=req.dept, insutype=req.insutype,
        main_diag_code=req.main_diag_code, main_diag_name=req.main_diag_name,
        diag_codes=req.diag_codes, main_oprn_code=req.main_oprn_code,
        inhosp_days=req.inhosp_days, adm_date=req.adm_date, dscg_date=req.dscg_date,
        dscg_way=req.dscg_way, drg_codg=req.drg_codg, drg_wt=req.drg_wt,
        drg_pay=req.drg_pay, medfee_sumamt=req.medfee_sumamt,
        fund_pay_sumamt=req.fund_pay_sumamt, psn_part_amt=req.psn_part_amt,
    )

    claim_lines = []
    for ln in req.lines:
        claim_lines.append(ClaimLine(
            setl_id=event.setl_id,
            feedetl_sn=ln.get("feedetl_sn", f"L{len(claim_lines)+1}"),
            line_no=ln.get("line_no", len(claim_lines) + 1),
            list_type=ln.get("list_type", "11"),
            med_list_name=ln.get("med_list_name", ""),
            med_list_codg=ln.get("med_list_codg", ""),
            cnt=ln.get("cnt", 1), pric=ln.get("pric", 0),
            det_amt=ln.get("det_amt", 0), chrgitm_lv=ln.get("chrgitm_lv", ""),
            hosp_appr_flag=ln.get("hosp_appr_flag", ""),
            oprn_code_used=ln.get("oprn_code_used", ""),
            dosage_form=ln.get("dosage_form", ""),
            tcmdrug_used_way=ln.get("tcmdrug_used_way", ""),
        ))

    engine = get_engine()
    t0 = _time.perf_counter()
    results = engine.audit_claim(event, claim_lines, req.stage)
    elapsed_ms = (_time.perf_counter() - t0) * 1000

    result_list = []
    for r in results:
        item = result_to_dict(r)
        if req.rule_code_filter and r.rule_code != req.rule_code_filter:
            continue
        result_list.append(item)

    violation_count = sum(1 for r in result_list if r.get("severity") == "violation")
    suspicious_count = sum(1 for r in result_list if r.get("severity") == "suspicious")
    has_block = any(r.get("action") == "block" for r in result_list)

    return {
        "code": 0, "setl_id": event.setl_id,
        "stage": req.stage, "elapsed_ms": round(elapsed_ms, 1),
        "total_lines": len(claim_lines), "total_results": len(result_list),
        "violation_count": violation_count, "suspicious_count": suspicious_count,
        "has_block": has_block, "results": result_list,
    }


@router.get("/api/v1/sandbox/templates", summary="测试模板列表")
def sandbox_templates():
    """返回按规则类别组织的测试模板列表"""
    templates = [
        {"category": "YP_SYZ", "name": "药品适应症限定", "count": 675, "sample": "乌司他丁+非胰腺炎诊断→违规"},
        {"category": "YP_XB", "name": "药品性别限定", "count": 481, "sample": "男性用艾附暖宫丸→违规"},
        {"category": "FW_XMHC", "name": "项目互斥", "count": 937, "sample": "手法松解+中医推拿同单→违规"},
        {"category": "FW_DJZJ", "name": "项目定价折价", "count": 445, "sample": "放疗多模式非最高价另收→违规"},
        {"category": "ZY_YPZF", "name": "中药饮片支付限定", "count": 153, "sample": "阿胶单独使用→违规"},
        {"category": "YP_ETZY", "name": "儿童专用药", "count": 271, "sample": "成人用儿童清肺口服液→违规"},
        {"category": "YP_JGJB", "name": "医院等级限定", "count": 88, "sample": "三级医院用热毒宁→违规"},
        {"category": "YP_EXYY", "name": "二线用药限定", "count": 126, "sample": "艾托格列净片使用→提醒"},
        {"category": "FW_XMPC", "name": "频次限定", "count": 112, "sample": "同管路护理重复收费→违规"},
        {"category": "YP_CBXZ", "name": "险种限定", "count": 19, "sample": "居民用职工限定药→违规"},
        {"category": "YP_NL", "name": "年龄限定", "count": 5, "sample": "儿童用老年限定药→违规"},
        {"category": "HC_WH", "name": "物耗限定", "count": 5, "sample": "钠石灰单独收费→违规"},
        {"category": "HC_SP", "name": "耗材审批", "count": 1, "sample": "高值耗材未审批→违规"},
        {"category": "WRZ", "name": "DRG未入组", "count": 1, "sample": "住院无DRG编码→违规"},
        {"category": "DFSW", "name": "低风险死亡", "count": 1, "sample": "低权重+死亡→违规"},
        {"category": "GQZ", "name": "高权重审查", "count": 1, "sample": "DRG权重>3.0→审查"},
    ]
    return {"code": 0, "items": templates}


@router.get("/api/v1/sandbox/template/{category}", summary="获取类别测试模板")
def sandbox_template_detail(category: str):
    """获取指定类别的测试模板(含违规+合规两个场景)"""
    template_map = {
        "YP_SYZ": {
            "stage": "pre_check",
            "violation": {
                "name": "乌司他丁+哮喘(非适应症)→应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "main_diag_code": "J45", "diag_codes": ["J45"]},
                "lines": [{"list_type": "11", "med_list_name": "乌司他丁", "cnt": 1, "pric": 100, "det_amt": 100}],
            },
            "pass": {
                "name": "乌司他丁+急性胰腺炎(适应症)→不应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "main_diag_code": "K85", "diag_codes": ["K85"]},
                "lines": [{"list_type": "11", "med_list_name": "乌司他丁", "cnt": 1, "pric": 100, "det_amt": 100}],
            },
        },
        "YP_XB": {
            "stage": "pre_check",
            "violation": {
                "name": "男性用艾附暖宫丸→应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "main_diag_code": "N92", "diag_codes": ["N92"]},
                "lines": [{"list_type": "12", "med_list_name": "艾附暖宫丸", "med_list_codg": "ZD03AAA0043010100166", "cnt": 1, "pric": 30, "det_amt": 30}],
            },
            "pass": {
                "name": "女性用艾附暖宫丸→不应触发",
                "event": {"med_type": "11", "gend": "2", "brdy": "1980-01-01", "main_diag_code": "N92", "diag_codes": ["N92"]},
                "lines": [{"list_type": "12", "med_list_name": "艾附暖宫丸", "med_list_codg": "ZD03AAA0043010100166", "cnt": 1, "pric": 30, "det_amt": 30}],
            },
        },
        "FW_XMHC": {
            "stage": "end_check",
            "violation": {
                "name": "手法松解+中医推拿同单→应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "main_diag_code": "M54", "diag_codes": []},
                "lines": [
                    {"list_type": "21", "med_list_name": "手法松解", "cnt": 1, "pric": 80, "det_amt": 80},
                    {"list_type": "21", "med_list_name": "中医推拿", "cnt": 1, "pric": 100, "det_amt": 100},
                ],
            },
            "pass": {
                "name": "仅中医推拿单一项目→不应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "main_diag_code": "M54", "diag_codes": []},
                "lines": [{"list_type": "21", "med_list_name": "中医推拿", "cnt": 1, "pric": 100, "det_amt": 100}],
            },
        },
        "ZY_YPZF": {
            "stage": "end_check",
            "violation": {
                "name": "阿胶单独使用→应触发",
                "event": {"med_type": "11", "main_diag_code": "Z00", "diag_codes": []},
                "lines": [{"list_type": "13", "med_list_name": "阿胶", "cnt": 1, "pric": 100, "det_amt": 100}],
            },
            "pass": {
                "name": "阿胶+黄芪配伍使用→不应触发(视规则)",
                "event": {"med_type": "11", "main_diag_code": "Z00", "diag_codes": []},
                "lines": [
                    {"list_type": "13", "med_list_name": "阿胶", "cnt": 1, "pric": 100, "det_amt": 100},
                    {"list_type": "13", "med_list_name": "黄芪", "cnt": 1, "pric": 50, "det_amt": 50},
                ],
            },
        },
        "YP_ETZY": {
            "stage": "pre_check",
            "violation": {
                "name": "成人用儿童清肺口服液→应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1990-01-01", "main_diag_code": "J00", "diag_codes": ["J00"]},
                "lines": [{"list_type": "12", "med_list_name": "儿童清肺口服液", "med_list_codg": "ZA04CAE0023010100166", "cnt": 1, "pric": 30, "det_amt": 30}],
            },
            "pass": {
                "name": "儿童用儿童清肺口服液→不应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "2020-01-01", "main_diag_code": "J00", "diag_codes": ["J00"]},
                "lines": [{"list_type": "12", "med_list_name": "儿童清肺口服液", "med_list_codg": "ZA04CAE0023010100166", "cnt": 1, "pric": 30, "det_amt": 30}],
            },
        },
        "YP_JGJB": {
            "stage": "pre_check",
            "violation": {
                "name": "三级医院用热毒宁→应触发",
                "event": {"med_type": "11", "gend": "1", "brdy": "1980-01-01", "hosp_lv": "2", "main_diag_code": "J00", "diag_codes": ["J00"]},
                "lines": [{"list_type": "12", "med_list_name": "热毒宁注射液", "cnt": 1, "pric": 40, "det_amt": 40}],
            },
        },
        "FW_DJZJ": {
            "stage": "end_check",
            "violation": {
                "name": "放疗多模式非最高价另收→应触发",
                "event": {"med_type": "21", "gend": "1", "brdy": "1965-01-01", "main_diag_code": "C34", "diag_codes": [], "adm_date": "2026-01-01", "dscg_date": "2026-01-10"},
                "lines": [
                    {"list_type": "21", "med_list_name": "调强放疗", "cnt": 1, "pric": 2000, "det_amt": 2000},
                    {"list_type": "21", "med_list_name": "电子线放疗", "cnt": 1, "pric": 500, "det_amt": 500},
                ],
            },
        },
        "WRZ": {
            "stage": "post_audit",
            "violation": {
                "name": "住院无DRG编码→应触发",
                "event": {"med_type": "21", "main_diag_code": "I21", "diag_codes": ["I21"], "inhosp_days": 7, "medfee_sumamt": 20000, "drg_codg": "", "drg_wt": 0, "fund_pay_sumamt": 15000, "dscg_way": "1", "adm_date": "2026-01-01", "dscg_date": "2026-01-08", "psn_part_amt": 5000},
                "lines": [],
            },
        },
        "DFSW": {
            "stage": "post_audit",
            "violation": {
                "name": "低权重+死亡→应触发",
                "event": {"med_type": "21", "main_diag_code": "I21", "diag_codes": ["I21"], "inhosp_days": 3, "medfee_sumamt": 10000, "drg_codg": "AH19", "drg_wt": 0.5, "drg_pay": 8000, "dscg_way": "5", "adm_date": "2026-01-01", "dscg_date": "2026-01-04", "psn_part_amt": 2000, "fund_pay_sumamt": 8000},
                "lines": [],
            },
        },
        "GQZ": {
            "stage": "post_audit",
            "violation": {
                "name": "DRG权重3.5→应触发审查",
                "event": {"med_type": "21", "main_diag_code": "I21", "diag_codes": ["I21"], "inhosp_days": 10, "medfee_sumamt": 80000, "drg_codg": "AH19", "drg_wt": 3.5, "drg_pay": 60000, "dscg_way": "1", "adm_date": "2026-01-01", "dscg_date": "2026-01-11", "psn_part_amt": 20000, "fund_pay_sumamt": 60000, "main_oprn_code": "88.41"},
                "lines": [],
            },
        },
    }

    if category not in template_map:
        raise HTTPException(status_code=404, detail=f"类别 {category} 无预置模板")
    return {"code": 0, "category": category, "templates": template_map[category]}


@router.get("/api/v1/sandbox/stats", summary="规则统计")
def sandbox_stats():
    """返回规则统计信息供沙箱展示"""
    with db_cursor() as conn:
        cat_rows = conn.execute("""
            SELECT rule_category, pillar, COUNT(*) as cnt
            FROM rule_items WHERE is_active=1
            GROUP BY rule_category, pillar ORDER BY cnt DESC
        """).fetchall()

        pillar_rows = conn.execute("""
            SELECT pillar, COUNT(*) as cnt
            FROM rule_items WHERE is_active=1
            GROUP BY pillar ORDER BY cnt DESC
        """).fetchall()

        stage_rows = conn.execute("""
            SELECT stage, COUNT(*) as cnt
            FROM rule_items WHERE is_active=1
            GROUP BY stage ORDER BY cnt DESC
        """).fetchall()

        drg_count = conn.execute(
            "SELECT COUNT(*) FROM drg_rules WHERE is_active=1 OR is_active IS NULL"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM rule_items WHERE is_active=1").fetchone()[0]

        return {
            "code": 0, "total_rules": total, "drg_rules": drg_count,
            "categories": [dict(r) for r in cat_rows],
            "pillars": [dict(r) for r in pillar_rows],
            "stages": [dict(r) for r in stage_rows],
        }
