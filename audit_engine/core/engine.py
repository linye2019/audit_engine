import json
from typing import Any, Optional, List

from ..models.claim import ClaimEvent, ClaimLine
from ..models.result import AuditResult
from ..dsl.evaluator import ConditionEvaluator
from ..matcher.catalog import CatalogMatcher
from ..repo.sqlite_repo import SQLiteRepository
from ..core.context import ContextBuilder
from ..core.reasoning import DRGReasoning

# list_type → pillar 映射
_LIST_TYPE_PILLAR = {"11": "YP", "12": "YP", "13": "YP",
                     "21": "FW", "31": "HC"}

# 住院医疗类别（柱4 BZ 只对住院生效）
_INPATIENT_TYPES = ("21", "24", "26", "28")


class MedicareAuditEngine:
    ENGINE_VERSION = "1.1.0"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.repo = SQLiteRepository(db_path)
        self.conn = self.repo.conn
        self.evaluator = ConditionEvaluator()
        self.matcher = CatalogMatcher(self.conn)
        self.context_builder = ContextBuilder(self.conn)
        self._rule_cache: dict[str, list[dict]] = {}
        self._rule_version_hash: str = ""

    def close(self):
        self.repo.close()

    def warm_cache(self):
        """预热全部规则缓存，避免首次请求慢"""
        for pillar in ("YP", "HC", "FW", "BZ"):
            for stage in ("pre_check", "mid_check", "end_check", "post_audit"):
                self._load_rules(pillar, stage)
        # CatalogMatcher 的 _ensure_loaded 由首次 match() 触发，惰性加载

    # ============================================================================
    # 统一审核入口
    # ============================================================================

    def audit_claim(self, claim: ClaimEvent, lines: List[ClaimLine],
                    stage: str = "post_audit",
                    audit_date: str = None) -> List[AuditResult]:
        results = []

        # 柱1-3：逐行审核（YP / HC / FW）
        for line in lines:
            pillar = _LIST_TYPE_PILLAR.get(line.list_type)
            if not pillar:
                continue

            match = self.matcher.match(line)
            if match:
                line.matched_catalog_id = match["id"]
                line.match_confidence = match["confidence"]
                line.match_method = match["method"]

            context = self.context_builder.build_line_context(claim, line, lines or [])
            rules = self._load_rules(pillar, stage, audit_date)

            for rule in rules:
                if not self._entity_matches(rule, line, match):
                    continue
                name_kw = rule.get("_name_keyword", "")
                if name_kw and name_kw not in line.med_list_name:
                    continue
                if self.evaluator.evaluate(rule["conditions"], context):
                    results.append(self._build_result(claim, line, rule, match, context))

        # 柱4：事件级审核（BZ — 仅住院且非事前/在院阶段）
        if claim.med_type in _INPATIENT_TYPES and stage in ("mid_check", "end_check", "post_audit"):
            context = self.context_builder.build_event_context(claim)
            rules = self._load_rules("BZ", stage, audit_date)
            for rule in rules:
                if self.evaluator.evaluate(rule["conditions"], context):
                    results.append(self._build_result(claim, None, rule, None, context))

        return results

    # ============================================================================
    # 统一规则加载（rule_items + drg_rules → 同一格式）
    # ============================================================================

    def _load_rules(self, pillar: str, stage: str, audit_date: str = None) -> List[dict]:
        cache_key = f"{pillar}_{stage}"

        # 规则版本号变更检查 — 轻量单行查询，规则更新后自动失效缓存
        current_hash = self.repo.get_rule_version_hash()
        if self._rule_version_hash != current_hash:
            self._rule_cache.clear()
            self._rule_version_hash = current_hash
        elif cache_key in self._rule_cache:
            return self._rule_cache[cache_key]

        if pillar == "BZ":
            # 从 drg_rules 加载，归一化为 rule_items 格式
            raw = self.repo.load_drg_rules(stage=stage, audit_date=audit_date)
            rules = []
            for r in raw:
                rules.append({
                    "id": r["id"],
                    "rule_code": r.get("rule_name", ""),
                    "rule_name": r.get("rule_name", ""),
                    "rule_category": r.get("rule_type", ""),
                    "pillar": "BZ",
                    "stage": stage,
                    "severity": r.get("severity", "suspicious"),
                    "conditions": r.get("conditions", "{}"),
                    "action": "tag",
                    "rule_code_cn": r.get("rule_name", ""),
                    "action_message": "",
                    "version": 1,
                    "_name_keyword": "",
                })
        else:
            rules = self.repo.load_rules(pillar=pillar, stage=stage, audit_date=audit_date)
            for rule in rules:
                rule["_name_keyword"] = self._extract_name_keyword(rule.get("conditions", ""))

        self._rule_cache[cache_key] = rules
        return rules

    # ============================================================================
    # 规则过滤辅助
    # ============================================================================

    @staticmethod
    def _extract_name_keyword(condition_json: str) -> str:
        if not condition_json:
            return ""
        try:
            node = json.loads(condition_json)
        except (json.JSONDecodeError, TypeError):
            return ""

        def _find_name_kw(n):
            if not isinstance(n, dict):
                return ""
            if (n.get("field", "").endswith("med_list_name")
                    and n.get("op") == "contains"
                    and isinstance(n.get("value"), str)):
                return n["value"]
            if "logic" in n:
                for c in n.get("conditions", []):
                    kw = _find_name_kw(c)
                    if kw:
                        return kw
            return ""

        return _find_name_kw(node)

    def _entity_matches(self, rule: dict, line: ClaimLine,
                        match: Optional[dict]) -> bool:
        # BZ 规则为事件级，无行级实体过滤
        if rule.get("pillar") == "BZ":
            return True
        if rule.get("yp_id") and line.list_type in ("11", "12", "13"):
            if not match or match.get("id") != rule["yp_id"]:
                return False
        if rule.get("xm_a_id") and line.list_type == "21":
            if not match or match.get("id") != rule["xm_a_id"]:
                return False
        if rule.get("hc_id") and line.list_type == "31":
            if not match or match.get("id") != rule["hc_id"]:
                return False
        return True

    # ============================================================================
    # 统一结果构建
    # ============================================================================

    def _build_result(self, claim: ClaimEvent, line: Optional[ClaimLine],
                      rule: dict, match: Optional[dict],
                      context: dict) -> AuditResult:
        # ---- BZ（柱4：事件级 DRG 规则） ----
        if rule.get("pillar") == "BZ":
            return AuditResult(
                claim_id=claim.setl_id,
                line_no=None,
                rule_id=rule["id"],
                rule_code=rule.get("rule_name", ""),
                rule_category=rule["rule_category"],
                pillar="BZ",
                stage=rule.get("stage", "post_audit"),
                verdict="warning",
                severity=rule.get("severity", "suspicious"),
                matched_facts=context,
                rule_text=rule.get("rule_code_cn", "") or rule.get("rule_name", ""),
                reasoning=DRGReasoning.generate(rule["rule_category"], claim),
                action="tag",
                engine_version=self.ENGINE_VERSION,
            )

        # ---- 柱1-3（行级规则） ----
        matched_facts = {}
        if rule.get("yp_id"):
            matched_facts["yp_id"] = rule["yp_id"]
        if rule.get("diagnosis_codes"):
            matched_facts["required_diagnoses"] = json.loads(rule["diagnosis_codes"])
        if rule.get("conditions"):
            try:
                conds = json.loads(rule["conditions"])
                if "conditions" in conds:
                    checked = []
                    for c in conds["conditions"]:
                        if isinstance(c, dict):
                            field = c.get("field")
                            actual_value = self._get_actual_value(field, claim, line, context)
                            checked.append({
                                "field": field,
                                "op": c.get("op"),
                                "actual": actual_value,
                                "expected": c.get("value")
                            })
                    if checked:
                        matched_facts["conditions_checked"] = checked
                else:
                    matched_facts["rule_type"] = conds.get("type", "unknown")
                    matched_facts["description"] = conds.get("description", "")
            except (json.JSONDecodeError, AttributeError):
                pass

        return AuditResult(
            claim_id=claim.setl_id,
            line_no=line.line_no,
            rule_id=rule["id"],
            rule_code=rule["rule_code"],
            rule_category=rule["rule_category"],
            pillar=rule["pillar"],
            stage=rule.get("stage", "post_audit"),
            verdict="violation" if rule.get("severity") == "violation" else
                    "info" if rule.get("severity") == "info" else "warning",
            severity=rule.get("severity", "suspicious"),
            matched_facts=matched_facts,
            rule_text=rule.get("rule_code_cn", "") or rule.get("rule_name", "") or rule.get("conditions", ""),
            reasoning=rule.get("action_message", "") or f"触发规则: {rule.get('rule_code_cn', '') or rule.get('rule_name', '')}",
            action=rule.get("action", "warn"),
            engine_version=self.ENGINE_VERSION,
            rule_version=rule.get("version", 1),
        )

    def _get_actual_value(self, field_path: str, claim: ClaimEvent,
                          line: ClaimLine, context: dict) -> Any:
        if not field_path:
            return None
        parts = field_path.split(".")
        if len(parts) < 2:
            return None
        entity, attr = parts[0], parts[1]
        if entity in context and isinstance(context[entity], dict) and attr in context[entity]:
            return context[entity][attr]
        if entity == "claim_line":
            return getattr(line, attr, None)
        elif entity == "claim_event":
            return getattr(claim, attr, None)
        return None

    # ============================================================================
    # 持久化
    # ============================================================================

    def save_results(self, results: List[AuditResult]):
        self.repo.save_results(results)

    def save_claim(self, claim: ClaimEvent):
        self.repo.save_claim(claim)

    def save_lines(self, lines: List[ClaimLine]):
        self.repo.save_lines(lines)
