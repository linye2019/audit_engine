"""系统接口 — 健康检查、数据库统计、前端页面"""

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, HTMLResponse

from ..deps import get_db_conn, DB_PATH
from ..schemas import StatsResponse

router = APIRouter(tags=["系统"])


@router.get("/api/v1/health", summary="健康检查")
def health_check():
    """检查 API 服务和数据库连接状态"""
    try:
        conn = get_db_conn()
        count = conn.execute("SELECT COUNT(*) FROM rule_items").fetchone()[0]
        conn.close()
        return {"code": 0, "status": "healthy", "db_path": DB_PATH, "rule_count": count}
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "status": "unhealthy", "error": str(e)})


@router.get("/api/v1/stats", summary="数据库统计", response_model=StatsResponse)
def stats():
    """获取各表记录数统计"""
    from ..deps import db_cursor
    with db_cursor() as conn:
        rows = conn.execute("SELECT * FROM v_catalog_stats").fetchall()
        tables = {row[0]: row[1] for row in rows}
        return {"code": 0, "tables": tables}


@router.get("/sandbox", summary="规则沙箱前端页面", response_class=HTMLResponse)
def sandbox_page():
    """返回规则沙箱前端HTML页面"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "..", "web", "rule_sandbox.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@router.get("/admin", summary="规则管理后台页面", response_class=HTMLResponse)
def admin_page():
    """返回规则管理后台HTML页面"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "..", "web", "rule_admin.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
