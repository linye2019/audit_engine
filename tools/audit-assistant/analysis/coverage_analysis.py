#!/usr/bin/env python3
"""
规则覆盖率分析 — 检查哪些规则有测试覆盖，哪些未被覆盖。
用法:
  python tools/audit-assistant/analysis/coverage_analysis.py
  python tools/audit-assistant/analysis/coverage_analysis.py --pillar YP
  python tools/audit-assistant/analysis/coverage_analysis.py --json
"""

import json
import sqlite3
import os
import sys
import re
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../medicare_engine.db")
TEST_FILE = os.path.join(os.path.dirname(__file__), "../../../tests/test_rules_from_rulebook.py")
TEST_ENGINE = os.path.join(os.path.dirname(__file__), "../../../tests/test_engine.py")
ALL_TEST_FILES = [
    TEST_FILE,
    TEST_ENGINE,
    os.path.join(os.path.dirname(__file__), "../../../tests/test_dsl_evaluator.py"),
    os.path.join(os.path.dirname(__file__), "../../../tests/test_context_builder.py"),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_rules(conn) -> list[dict]:
    """获取所有活跃规则"""
    rows = conn.execute(
        "SELECT id, rule_code, rule_name, rule_category, pillar, stage, severity "
        "FROM rule_items WHERE is_active = 1"
    ).fetchall()
    return [dict(r) for r in rows]


def get_drg_rules(conn) -> list[dict]:
    """获取所有 DRG 规则"""
    rows = conn.execute(
        "SELECT id, rule_name, rule_type, severity, stage "
        "FROM drg_rules WHERE is_active = 1"
    ).fetchall()
    return [dict(r) for r in rows]


def extract_tested_codes(filepath: str) -> set:
    """从测试文件中提取所有被测试的 rule_code"""
    if not os.path.exists(filepath):
        return set()
    codes = set()
    with open(filepath) as f:
        content = f.read()
        # 匹配 RULE_CASES 中的 rule_code
        for m in re.finditer(r'"([A-Z]+_[A-Z0-9_]+)"', content):
            codes.add(m.group(1))
        # 匹配函数名中的 rule_code
        for m in re.finditer(r'test_rule_([a-z_0-9]+)', content):
            codes.add(m.group(1).upper())
    return codes


def extract_test_names(filepath: str) -> set:
    """从测试文件中提取测试的规则类别名称"""
    if not os.path.exists(filepath):
        return set()
    names = set()
    with open(filepath) as f:
        content = f.read()
        for m in re.finditer(r'rule_category\s*[=:]\s*["\']([^"\']+)["\']', content):
            names.add(m.group(1))
        for m in re.finditer(r'"rule_category":\s*"([^"]+)"', content):
            names.add(m.group(1))
    return names


def analyze_coverage(conn, pillar: str = None) -> dict:
    """分析规则覆盖率"""
    rules = get_all_rules(conn)
    if pillar:
        rules = [r for r in rules if r["pillar"] == pillar]

    drg = get_drg_rules(conn)
    categories = defaultdict(list)
    for r in rules:
        categories[r["rule_category"]].append(r)

    # 从测试文件提取已覆盖的类别
    covered_codes = set()
    for f in ALL_TEST_FILES:
        covered_codes |= extract_tested_codes(f)
    covered_names = set()
    for f in ALL_TEST_FILES:
        covered_names |= extract_test_names(f)

    # 计算覆盖率
    total = len(rules)
    covered = 0
    uncovered_rules = []
    covered_by_category = defaultdict(int)
    total_by_category = defaultdict(int)

    for r in rules:
        total_by_category[r["rule_category"]] += 1
        if r["rule_code"] in covered_codes or r["rule_category"] in covered_names:
            covered += 1
            covered_by_category[r["rule_category"]] += 1
        else:
            uncovered_rules.append(r)

    return {
        "total_rules": total,
        "covered": covered,
        "uncovered": total - covered,
        "coverage_pct": round(covered / total * 100, 1) if total > 0 else 0,
        "by_pillar": dict((p, len([r for r in rules if r["pillar"] == p])) for p in set(r["pillar"] for r in rules)),
        "by_category": [
            {
                "category": cat,
                "total": total_by_category[cat],
                "covered": covered_by_category.get(cat, 0),
                "coverage_pct": round(covered_by_category.get(cat, 0) / total_by_category[cat] * 100, 1),
            }
            for cat in sorted(total_by_category.keys())
        ],
        "uncovered_rules": [
            {"code": r["rule_code"], "category": r["rule_category"],
             "pillar": r["pillar"], "stage": r["stage"]}
            for r in uncovered_rules[:20]  # 最多显示 20 条
        ],
        "drg_total": len(drg),
        "note": "覆盖率按 rule_code 和 rule_category 双重匹配计算",
    }


def print_report(stats: dict):
    """输出可读报告"""
    print(f"\n{'='*60}")
    print(f"  规则覆盖率分析报告")
    print(f"  RULE_BOOK.md 规则数: {stats['total_rules']}")
    print(f"  DRG 规则数: {stats['drg_total']}")
    print(f"{'='*60}")
    print(f"  ✅ 已覆盖: {stats['covered']}")
    print(f"  ❌ 未覆盖: {stats['uncovered']}")
    print(f"  📊 覆盖率: {stats['coverage_pct']}%")
    print(f"{'='*60}")
    print(f"\n  按支柱分布:")
    for p, c in sorted(stats["by_pillar"].items()):
        print(f"    {p}: {c} 条")

    print(f"\n  按规则类别覆盖率:")
    for cat in stats["by_category"]:
        bar = "█" * int(cat["coverage_pct"] / 10) + "░" * (10 - int(cat["coverage_pct"] / 10))
        print(f"    {bar} {cat['category']:15s} {cat['covered']:4d}/{cat['total']:<4d} ({cat['coverage_pct']:5.1f}%)")

    if stats["uncovered_rules"]:
        print(f"\n  未覆盖规则示例 (前 {len(stats['uncovered_rules'])} 条):")
        for r in stats["uncovered_rules"]:
            print(f"    - {r['code']} ({r['category']}) [{r['pillar']}/{r['stage']}]")
        print(f"\n  建议: 运行 /gen-tests 从 RULE_BOOK.md 补全测试")


if __name__ == "__main__":
    pillar = None
    if "--pillar" in sys.argv:
        idx = sys.argv.index("--pillar")
        if idx + 1 < len(sys.argv):
            pillar = sys.argv[idx + 1]

    output_json = "--json" in sys.argv

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    stats = analyze_coverage(conn, pillar)
    conn.close()

    if output_json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print_report(stats)
