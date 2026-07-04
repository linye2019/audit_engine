"""
医保智能审核引擎 — Python 审核引擎核心框架
版本: 1.1.0
日期: 2026-07-03
对应文档: ARCHITECTURE.md

四柱审核框架:
  柱1: 药品目录限制 (drug)
  柱2: 耗材使用合规 (consumable)
  柱3: 项目收费合规 (project)
  柱4: 支付合规性   (drg)

三阶段执行:
  pre_check  → 事前提醒（明确违规 + 高置信度规则）
  end_check → 事中审核（全量规则）
  post_audit → 事后监管（全量规则 + 统计分析规则）
"""

from .core.engine import MedicareAuditEngine
from .models.claim import ClaimEvent, ClaimLine
from .models.result import AuditResult

__all__ = ["MedicareAuditEngine", "ClaimEvent", "ClaimLine", "AuditResult"]
__version__ = "1.1.0"