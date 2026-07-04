"""
gen-audit-tests 测试模板

由 SKILL.md 驱动自动生成。每条规则生成一个参数化测试条目，
覆盖匹配（应触发）和不匹配（不应触发）两个场景。

依赖: pytest, conftest.py 中的 fixture
运行: python -m pytest tests/test_rules_from_rulebook.py -v
"""

import json
import pytest
from audit_engine.models.claim import ClaimEvent, ClaimLine


# ============================================================
# 规则条目：从 RULE_BOOK.md 解析生成
# 每个 tuple: (rule_code, pillar, stage, conditions, severity, description)
# ============================================================
RULE_CASES = [
    # （占位 — 运行 /gen-tests 后自动填充）
]


def _build_context(claim_event_kw: dict, claim_line_kw: dict) -> dict:
    """根据字段映射构建审计上下文"""
    context = {}
    if claim_event_kw:
        context["claim_event"] = claim_event_kw
    if claim_line_kw:
        context["claim_line"] = claim_line_kw
    return context


def _make_line(list_type: str, **overrides) -> ClaimLine:
    """快速构造 ClaimLine，参数同 conftest.py 的 sample_drug_line"""
    defaults = dict(
        setl_id="TEST001", feedetl_sn="L001", med_list_name="测试项目",
        cnt=1.0, pric=100.0, det_amt=100.0, line_no=1,
    )
    defaults.update(overrides)
    defaults["list_type"] = list_type
    return ClaimLine(**defaults)


class TestRulesFromRulebook:
    @pytest.mark.parametrize(
        "rule_code, pillar, stage, conditions, severity, desc",
        RULE_CASES,
        ids=[c[0] for c in RULE_CASES],
    )
    def test_rule_matches(self, engine, sample_claim, rule_code, pillar, stage,
                          conditions, severity, desc):
        """测试规则匹配场景（应触发）"""
        pytest.skip("运行 /gen-tests 后自动填充")

    @pytest.mark.parametrize(
        "rule_code, pillar, stage, conditions, severity, desc",
        RULE_CASES,
        ids=[f"{c[0]}_no_match" for c in RULE_CASES],
    )
    def test_rule_no_match(self, engine, sample_claim, rule_code, pillar, stage,
                           conditions, severity, desc):
        """测试规则不匹配场景（不应触发）"""
        pytest.skip("运行 /gen-tests 后自动填充")

    def test_rules_summary(self):
        """汇总统计"""
        total = len(RULE_CASES)
        pillars = set(c[1] for c in RULE_CASES)
        stages = set(c[2] for c in RULE_CASES)
        print(f"\n规则总数: {total}")
        print(f"支柱: {', '.join(sorted(pillars))}")
        print(f"阶段: {', '.join(sorted(stages))}")
        assert total > 0, "RULE_CASES 为空，请先运行 /gen-tests"
