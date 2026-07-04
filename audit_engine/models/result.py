from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditResult:
    """审核结果 — 引擎输出"""
    claim_id: str
    line_no: Optional[int] = None
    rule_id: Optional[int] = None
    rule_code: str = ""
    rule_category: str = ""
    pillar: str = ""
    stage: str = "post_audit"
    verdict: str = "pass"        # pass / warning / violation
    severity: str = ""           # violation / suspicious / info
    matched_facts: dict = field(default_factory=dict)
    rule_text: str = ""
    reasoning: str = ""
    action: str = "warn"          # block / warn / tag / pass
    engine_version: str = "1.1.0"
    rule_version: int = 1