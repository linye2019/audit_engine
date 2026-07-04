"""ICD 编码查询接口 — ICD-10 诊断编码 + ICD-9-CM-3 手术编码"""

from fastapi import APIRouter, Query

from ..deps import db_cursor

router = APIRouter(tags=["编码"])


@router.get("/api/v1/icd10/search", summary="ICD-10诊断编码查询")
def search_icd10(
    keyword: str = Query(..., description="编码或名称关键词"),
    limit: int = Query(20, ge=1, le=100),
):
    """查询ICD-10诊断编码（支持编码或名称模糊匹配）"""
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT id, chs_code, name, is_gray_code, chapter, chapter_name,
                      is_mcc, is_cc, drg_group_type
               FROM icd_10
               WHERE chs_code LIKE ? OR name LIKE ?
               ORDER BY chs_code LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", limit)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM icd_10 WHERE chs_code LIKE ? OR name LIKE ?",
            (f"%{keyword}%", f"%{keyword}%")
        ).fetchone()[0]

        return {"code": 0, "total": total, "items": [dict(r) for r in rows]}


@router.get("/api/v1/icd9/search", summary="ICD-9-CM-3手术编码查询")
def search_icd9(
    keyword: str = Query(..., description="编码或名称关键词"),
    limit: int = Query(20, ge=1, le=100),
):
    """查询ICD-9-CM-3手术操作编码"""
    with db_cursor() as conn:
        rows = conn.execute(
            """SELECT id, chs_code, name, category, is_major, drg_effect
               FROM icd_9
               WHERE chs_code LIKE ? OR name LIKE ?
               ORDER BY chs_code LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", limit)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM icd_9 WHERE chs_code LIKE ? OR name LIKE ?",
            (f"%{keyword}%", f"%{keyword}%")
        ).fetchone()[0]

        return {"code": 0, "total": total, "items": [dict(r) for r in rows]}
