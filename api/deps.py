"""API 依赖注入与辅助函数"""

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from audit_engine import MedicareAuditEngine, ClaimEvent, ClaimLine, AuditResult

DB_PATH = os.environ.get("MEDICARE_DB_PATH", "medicare_engine.db")
API_VERSION = "1.0.0"

# 引擎单例 — 跨请求复用，避免重复创建连接和缓存
_engine: Optional[MedicareAuditEngine] = None


def get_engine() -> MedicareAuditEngine:
    """获取引擎实例（单例，首次调用时预热缓存）"""
    global _engine
    if _engine is None:
        _engine = MedicareAuditEngine(DB_PATH)
        _engine.warm_cache()
    return _engine


def model_to_claim_event(m) -> ClaimEvent:
    """Pydantic 模型 → dataclass"""
    return ClaimEvent(**m.model_dump())


def model_to_claim_line(m) -> ClaimLine:
    """Pydantic 模型 → dataclass"""
    return ClaimLine(**m.model_dump())


def result_to_dict(r: AuditResult) -> dict:
    """AuditResult dataclass → dict"""
    return {
        "claim_id": r.claim_id,
        "line_no": r.line_no,
        "rule_id": r.rule_id,
        "rule_code": r.rule_code,
        "rule_category": r.rule_category,
        "pillar": r.pillar,
        "stage": r.stage,
        "verdict": r.verdict,
        "severity": r.severity,
        "matched_facts": r.matched_facts,
        "rule_text": r.rule_text,
        "reasoning": r.reasoning,
        "action": r.action,
        "engine_version": r.engine_version,
    }


def get_db_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_cursor():
    """数据库游标上下文管理器"""
    conn = get_db_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
