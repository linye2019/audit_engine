"""规则管理接口 — 规则列表/详情/版本管理/快照/变更日志"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import json
import sqlite3

from ..deps import db_cursor
from ..schemas import CreateSnapshotRequest, UpdateRuleVersionRequest

router = APIRouter(tags=["规则"])


@router.get("/api/v1/rules", summary="规则列表查询")
def query_rules(
    pillar: str = Query("", description="支柱: YP/HC/FW/BZ"),
    stage: str = Query("", description="阶段: pre_check/end_check/post_audit"),
    category: str = Query("", description="规则大类"),
    active_only: bool = Query(True, description="仅返回启用规则"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查询审核规则列表，支持多条件筛选"""
    conditions = []
    params = []

    if pillar:
        conditions.append("pillar = ?")
        params.append(pillar)
    if stage:
        conditions.append("(stage = ? OR stage = 'post_audit')")
        params.append(stage)
    if category:
        conditions.append("rule_category = ?")
        params.append(category)
    if active_only:
        conditions.append("is_active = 1")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with db_cursor() as conn:
        rows = conn.execute(
            f"""SELECT id, rule_code, rule_name, rule_category, rule_subcategory,
                       pillar, stage, severity, action, action_message,
                       source_batch, is_active
                FROM rule_items WHERE {where_clause}
                ORDER BY pillar, severity DESC, id
                LIMIT ? OFFSET ?""",
            params + [limit, offset]
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM rule_items WHERE {where_clause}", params
        ).fetchone()[0]

        pillar_stats = {}
        for row in conn.execute(
            f"SELECT pillar, COUNT(*) as cnt FROM rule_items WHERE {where_clause} GROUP BY pillar",
            params
        ).fetchall():
            pillar_stats[row["pillar"]] = row["cnt"]

        return {
            "code": 0, "total": total, "pillar_stats": pillar_stats,
            "items": [dict(r) for r in rows],
        }


@router.get("/api/v1/rules/{rule_id}", summary="规则详情")
def get_rule_detail(rule_id: int):
    """查询规则完整详情（含条件DSL）"""
    with db_cursor() as conn:
        row = conn.execute("SELECT * FROM rule_items WHERE id = ?", (rule_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"规则ID {rule_id} 不存在")

        d = dict(row)
        for field in ("conditions", "diagnosis_codes", "procedure_codes"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    pass

        return {"code": 0, "rule": d}


# ============================================================================
# 规则版本管理
# ============================================================================

@router.get("/api/v1/rules/snapshots", tags=["规则版本"], summary="获取规则集快照列表")
def get_snapshots():
    """获取所有规则集快照"""
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT id, snapshot_name, snapshot_desc, rule_count,
                      created_at, created_by, effective_date, expired_date
               FROM rule_set_snapshot ORDER BY created_at DESC"""
        ).fetchall()
        return {"code": 0, "snapshots": [dict(row) for row in rows]}


@router.post("/api/v1/rules/snapshots", tags=["规则版本"], summary="创建规则集快照")
def create_snapshot(req: CreateSnapshotRequest):
    """创建规则集快照，用于标记当前规则状态"""
    try:
        with db_cursor() as conn:
            current_date = datetime.now().strftime("%Y-%m-%d")
            rule_count = conn.execute(
                "SELECT COUNT(*) FROM rule_items WHERE is_active = 1 AND (expired_date IS NULL OR expired_date > ?)",
                (current_date,)
            ).fetchone()[0]

            conn.execute(
                "INSERT INTO rule_set_snapshot (snapshot_name, snapshot_desc, rule_count, created_by, effective_date) VALUES (?, ?, ?, ?, ?)",
                (req.snapshot_name, req.snapshot_desc, rule_count, req.created_by, current_date)
            )
            conn.execute(
                "UPDATE rule_set_snapshot SET expired_date = ? WHERE expired_date IS NULL AND snapshot_name != ?",
                (current_date, req.snapshot_name)
            )

        return {"code": 0, "message": f"快照 {req.snapshot_name} 创建成功",
                "rule_count": rule_count, "created_at": current_date}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"快照名称 {req.snapshot_name} 已存在")


@router.get("/api/v1/rules/changelog", tags=["规则版本"], summary="获取规则变更日志")
def get_changelog(
    rule_id: Optional[int] = Query(None, description="规则ID"),
    rule_code: Optional[str] = Query(None, description="规则编码"),
    limit: int = Query(100, ge=1, le=500),
):
    """获取规则变更日志"""
    with db_cursor() as conn:
        query = "SELECT * FROM rule_changelog WHERE 1=1"
        params = []
        if rule_id:
            query += " AND rule_id = ?"
            params.append(rule_id)
        elif rule_code:
            query += " AND rule_code = ?"
            params.append(rule_code)
        query += " ORDER BY changed_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        changelog = []
        for row in rows:
            d = dict(row)
            if d.get("changed_fields"):
                try:
                    d["changed_fields"] = json.loads(d["changed_fields"])
                except json.JSONDecodeError:
                    pass
            changelog.append(d)

        return {"code": 0, "changelog": changelog}


@router.put("/api/v1/rules/{rule_code}/version", tags=["规则版本"], summary="更新规则版本")
def update_rule_version(rule_code: str, req: UpdateRuleVersionRequest):
    """更新规则版本：保留旧版本（设为过期），插入新版本"""
    updates = {}
    for field in ["rule_name", "rule_category", "pillar", "stage", "severity",
                  "conditions", "action", "action_message", "effective_date", "expired_date"]:
        value = getattr(req, field)
        if value is not None:
            updates[field] = value

    if not updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个更新字段")

    try:
        with db_cursor() as conn:
            current_date = datetime.now().strftime("%Y-%m-%d")
            row = conn.execute(
                """SELECT id, version, rule_name, rule_category, rule_subcategory, pillar, stage, severity,
                          drug_id, project_a_id, project_b_id, consumable_id, diagnosis_codes, procedure_codes,
                          conditions, action, action_message, source_batch, source_reference
                   FROM rule_items
                   WHERE rule_code = ? AND is_active = 1 AND (expired_date IS NULL OR expired_date > ?)""",
                (rule_code, current_date)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"活跃规则不存在: {rule_code}")

            old_version = row["version"]
            new_version = old_version + 1

            conn.execute(
                "UPDATE rule_items SET is_active = 0, expired_date = ? WHERE id = ?",
                (current_date, row["id"])
            )

            new_effective_date = updates.get("effective_date", current_date)
            new_expired_date = updates.get("expired_date")

            conn.execute("""
                INSERT INTO rule_items (
                    rule_code, rule_name, rule_category, rule_subcategory, pillar, stage, severity,
                    drug_id, project_a_id, project_b_id, consumable_id, diagnosis_codes, procedure_codes,
                    conditions, action, action_message, source_batch, source_reference,
                    version, effective_date, expired_date, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_code,
                updates.get("rule_name", row["rule_name"]),
                updates.get("rule_category", row["rule_category"]),
                row["rule_subcategory"],
                updates.get("pillar", row["pillar"]),
                updates.get("stage", row["stage"]),
                updates.get("severity", row["severity"]),
                row["drug_id"], row["project_a_id"], row["project_b_id"], row["consumable_id"],
                row["diagnosis_codes"], row["procedure_codes"],
                updates.get("conditions", row["conditions"]),
                updates.get("action", row["action"]),
                updates.get("action_message", row["action_message"]),
                row["source_batch"], row["source_reference"],
                new_version, new_effective_date, new_expired_date, 1,
            ))

        return {"code": 0, "message": f"规则 {rule_code} 版本更新成功",
                "old_version": old_version, "new_version": new_version}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
