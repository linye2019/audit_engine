import json
from typing import Any, Optional
from .operators import OPERATORS


class ConditionEvaluator:
    """
    解析并执行 rule_items.conditions 中的 JSON 条件 DSL。
    支持的运算符: eq, ne, !=, gt, gte, lt, lte, in, not_in, contains,
                 not_contains, regex, not_regex, is_null, is_not_null,
                 any_contains, none_contains, coexists_with, not_exists,
                 not_between, len_gt, len_gte
    """

    FIELD_ALIASES = {
        "patient_gender": "gend",
        "patient_age": "age",
        "hospital_level": "hosp_lv",
        "insurance_type": "insutype",
        "diagnosis_codes": "diag_codes",
        "med_list_code": "med_list_codg",
        "project_code": "med_list_codg",
        "visit_type": "med_type",
        "prescription_type": "med_type",
    }

    def __init__(self):
        self._condition_cache: dict[str, Optional[dict]] = {}

    def evaluate(self, condition_json: str, context: dict) -> bool:
        try:
            if condition_json not in self._condition_cache:
                node = json.loads(condition_json)
                if "logic" not in node and "field" not in node:
                    self._condition_cache[condition_json] = None
                else:
                    self._condition_cache[condition_json] = node

            node = self._condition_cache[condition_json]
            if node is None:
                return False
            return self._evaluate_node(node, context)
        except (json.JSONDecodeError, KeyError, TypeError):
            return False

    def _evaluate_node(self, node: dict, context: dict) -> bool:
        if "logic" in node:
            logic = node["logic"].upper()
            conditions = node.get("conditions", [])
            if not conditions:
                return True

            if logic == "AND":
                return all(self._evaluate_node(c, context) for c in conditions)
            elif logic == "OR":
                return any(self._evaluate_node(c, context) for c in conditions)
            elif logic == "NOT":
                return not self._evaluate_node(conditions[0], context) if conditions else True

        field_path = node.get("field", "")
        op = node.get("op", "eq")
        value = node.get("value")

        actual = self._resolve_field(field_path, context)
        op_func = OPERATORS.get(op)
        if not op_func:
            return False

        return op_func(actual, value)

    def _resolve_field(self, field_path: str, context: dict) -> Any:
        parts = field_path.split(".")
        current = context
        for i, part in enumerate(parts):
            if i == len(parts) - 1 and part in self.FIELD_ALIASES:
                part = self.FIELD_ALIASES[part]
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current