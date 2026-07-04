"""目录查询接口 — 药品/诊疗项目/耗材目录查询与导入"""

from fastapi import APIRouter, Query
import sqlite3

from ..deps import db_cursor
from ..schemas import ConsumableImportRequest

router = APIRouter(tags=["目录"])


@router.get("/api/v1/catalog/drug", summary="药品目录查询")
def query_drug(
    keyword: str = Query("", description="名称关键词（模糊匹配）"),
    limit: int = Query(20, ge=1, le=200, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """查询药品目录，支持名称模糊搜索"""
    with db_cursor() as conn:
        if keyword:
            rows = conn.execute(
                """SELECT id, drug_name, dosage_form, atc_code, pharmacological_class,
                          payment_type, chs_code, label_indications
                   FROM YP
                   WHERE drug_name LIKE ? OR chs_code LIKE ?
                   ORDER BY drug_name LIMIT ? OFFSET ?""",
                (f"%{keyword}%", f"%{keyword}%", limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM YP WHERE drug_name LIKE ? OR chs_code LIKE ?",
                (f"%{keyword}%", f"%{keyword}%")
            ).fetchone()[0]
        else:
            rows = conn.execute(
                """SELECT id, drug_name, dosage_form, atc_code, pharmacological_class,
                          payment_type, chs_code, label_indications
                   FROM YP ORDER BY id DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM YP").fetchone()[0]

        return {"code": 0, "total": total, "items": [dict(r) for r in rows]}


@router.get("/api/v1/catalog/project", summary="诊疗项目目录查询")
def query_project(
    keyword: str = Query("", description="名称关键词"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询诊疗项目目录"""
    with db_cursor() as conn:
        if keyword:
            rows = conn.execute(
                """SELECT id, name, billing_unit, med_list_codg, service_output,
                          pricing_composition, evidence_source
                   FROM FW
                   WHERE name LIKE ? OR med_list_codg LIKE ?
                   ORDER BY name LIMIT ? OFFSET ?""",
                (f"%{keyword}%", f"%{keyword}%", limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM FW WHERE name LIKE ? OR med_list_codg LIKE ?",
                (f"%{keyword}%", f"%{keyword}%")
            ).fetchone()[0]
        else:
            rows = conn.execute(
                """SELECT id, name, billing_unit, med_list_codg, service_output,
                          pricing_composition, evidence_source
                   FROM FW ORDER BY id DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM FW").fetchone()[0]

        return {"code": 0, "total": total, "items": [dict(r) for r in rows]}


@router.get("/api/v1/catalog/consumable", summary="耗材目录查询")
def query_consumable(
    keyword: str = Query("", description="名称关键词"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询医用耗材目录"""
    with db_cursor() as conn:
        if keyword:
            rows = conn.execute(
                """SELECT * FROM HC
                   WHERE med_list_name LIKE ? OR ccode LIKE ? OR med_list_codg LIKE ?
                   ORDER BY med_list_name LIMIT ? OFFSET ?""",
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM HC WHERE med_list_name LIKE ? OR ccode LIKE ? OR med_list_codg LIKE ?",
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM HC ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM HC").fetchone()[0]

        return {"code": 0, "total": total, "items": [dict(r) for r in rows]}


@router.post("/api/v1/catalog/consumable/import", summary="耗材目录批量导入")
def import_consumables(req: ConsumableImportRequest):
    """批量导入耗材目录数据"""
    inserted = 0
    skipped = 0
    errors = []

    with db_cursor() as conn:
        for i, item in enumerate(req.consumables):
            try:
                if req.skip_existing:
                    exists = conn.execute(
                        "SELECT 1 FROM HC WHERE med_list_name = ?",
                        (item.generic_name,)
                    ).fetchone()
                    if exists:
                        skipped += 1
                        continue

                conn.execute(
                    """INSERT INTO HC
                       (material_type, med_list_name, ccode, category, payment_type, payment_ratio,
                        drug_loaded, drug_component, evidence_source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("normal", item.generic_name, item.ccode, item.category, item.payment_type,
                     item.payment_ratio, item.drug_loaded, item.drug_component,
                     item.evidence_source or "api_import")
                )
                inserted += 1
            except sqlite3.IntegrityError as e:
                errors.append({"index": i, "name": item.generic_name, "error": str(e)})
            except Exception as e:
                errors.append({"index": i, "name": item.generic_name, "error": str(e)})

    return {
        "code": 0,
        "message": f"导入完成: 新增 {inserted} 条, 跳过 {skipped} 条, 错误 {len(errors)} 条",
        "inserted": inserted, "skipped": skipped, "errors": errors,
    }
