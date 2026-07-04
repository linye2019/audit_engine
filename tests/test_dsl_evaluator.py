import pytest
from audit_engine.dsl.evaluator import ConditionEvaluator
from audit_engine.dsl.operators import OPERATORS, register_operator


class TestConditionEvaluator:
    def setup_method(self):
        self.evaluator = ConditionEvaluator()

    def test_simple_eq_true(self):
        cond = '{"field": "age", "op": "gt", "value": 10}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_simple_eq_false(self):
        cond = '{"field": "age", "op": "gt", "value": 30}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_and_logic_all_true(self):
        cond = '''
        {
            "logic": "AND",
            "conditions": [
                {"field": "age", "op": "gt", "value": 10},
                {"field": "gend", "op": "eq", "value": "1"}
            ]
        }
        '''
        ctx = {"age": 20, "gend": "1"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_and_logic_one_false(self):
        cond = '''
        {
            "logic": "AND",
            "conditions": [
                {"field": "age", "op": "gt", "value": 10},
                {"field": "gend", "op": "eq", "value": "2"}
            ]
        }
        '''
        ctx = {"age": 20, "gend": "1"}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_or_logic_one_true(self):
        cond = '''
        {
            "logic": "OR",
            "conditions": [
                {"field": "age", "op": "gt", "value": 50},
                {"field": "gend", "op": "eq", "value": "1"}
            ]
        }
        '''
        ctx = {"age": 20, "gend": "1"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_or_logic_all_false(self):
        cond = '''
        {
            "logic": "OR",
            "conditions": [
                {"field": "age", "op": "gt", "value": 50},
                {"field": "gend", "op": "eq", "value": "2"}
            ]
        }
        '''
        ctx = {"age": 20, "gend": "1"}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_not_logic(self):
        cond = '''
        {
            "logic": "NOT",
            "conditions": [
                {"field": "age", "op": "gt", "value": 50}
            ]
        }
        '''
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_not_logic_empty_conditions(self):
        cond = '{"logic": "NOT", "conditions": []}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_nested_conditions(self):
        cond = '''
        {
            "logic": "AND",
            "conditions": [
                {"field": "age", "op": "gt", "value": 10},
                {
                    "logic": "OR",
                    "conditions": [
                        {"field": "gend", "op": "eq", "value": "1"},
                        {"field": "hosp_lv", "op": "eq", "value": "2"}
                    ]
                }
            ]
        }
        '''
        ctx = {"age": 20, "gend": "2", "hosp_lv": "2"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_invalid_json_returns_false(self):
        assert self.evaluator.evaluate("invalid json", {}) is False

    def test_empty_conditions_returns_true(self):
        cond = '{"logic": "AND", "conditions": []}'
        assert self.evaluator.evaluate(cond, {}) is True

    def test_no_logic_no_field_returns_false(self):
        cond = '{"foo": "bar"}'
        assert self.evaluator.evaluate(cond, {}) is False

    def test_unknown_operator_returns_false(self):
        cond = '{"field": "age", "op": "unknown_op", "value": 10}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_field_alias_resolution(self):
        cond = '{"field": "patient_gender", "op": "eq", "value": "1"}'
        ctx = {"gend": "1"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_field_alias_patient_age(self):
        cond = '{"field": "patient_age", "op": "gt", "value": 10}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_nested_field_path(self):
        cond = '{"field": "claim.age", "op": "gt", "value": 10}'
        ctx = {"claim": {"age": 20}}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_nested_field_not_found(self):
        cond = '{"field": "claim.age", "op": "gt", "value": 10}'
        ctx = {"claim": {}}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_condition_cache_hit(self):
        cond = '{"field": "age", "op": "gt", "value": 10}'
        ctx1 = {"age": 20}
        ctx2 = {"age": 5}
        r1 = self.evaluator.evaluate(cond, ctx1)
        r2 = self.evaluator.evaluate(cond, ctx2)
        assert r1 is True
        assert r2 is False
        assert cond in self.evaluator._condition_cache

    def test_field_path_missing_field(self):
        cond = '{"field": "nonexistent", "op": "eq", "value": "x"}'
        ctx = {"age": 20}
        assert self.evaluator.evaluate(cond, ctx) is False

    def test_in_operator(self):
        cond = '{"field": "code", "op": "in", "value": ["A", "B", "C"]}'
        ctx = {"code": "B"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_contains_operator(self):
        cond = '{"field": "name", "op": "contains", "value": "西林"}'
        ctx = {"name": "阿莫西林"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_regex_operator(self):
        cond = '{"field": "code", "op": "regex", "value": "^J\\\\d+"}'
        ctx = {"code": "J18.9"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_coexists_with_string(self):
        cond = '{"field": "co_claimed_names", "op": "coexists_with", "value": "阿司匹林"}'
        ctx = {"co_claimed_names": ["阿莫西林", "阿司匹林"]}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_coexists_with_dict(self):
        cond = '{"field": "co_claimed_names", "op": "coexists_with", "value": {"med_list_name": "阿司匹林"}}'
        ctx = {"co_claimed_names": ["阿莫西林", "阿司匹林"]}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_any_contains_operator(self):
        cond = '{"field": "items", "op": "any_contains", "value": "西林"}'
        ctx = {"items": ["阿莫西林胶囊", "头孢"]}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_len_gt_list(self):
        cond = '{"field": "items", "op": "len_gt", "value": 2}'
        ctx = {"items": ["a", "b", "c"]}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_len_gt_string(self):
        cond = '{"field": "name", "op": "len_gt", "value": 3}'
        ctx = {"name": "阿莫西林"}
        assert self.evaluator.evaluate(cond, ctx) is True

    def test_not_between_operator(self):
        cond = '{"field": "days", "op": "not_between", "value": [5, 10]}'
        ctx = {"days": 3}
        assert self.evaluator.evaluate(cond, ctx) is True
