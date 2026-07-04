#!/usr/bin/env python3
"""
规则冲突检测 — 检测同一 pillar 内规则的潜在逻辑冲突。
用法:
  python tools/audit-assistant/analysis/conflict_detector.py
  python tools/audit-assistant/analysis/conflict_detector.py --pillar YP
"""

import json
import sqlite3
import sys
import os
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../medicare_engine.db")

# 冲突类型定义
CONFLICT_PATTERNS = {
    "gender_conflict": {
        "description": "性别互斥 — 同一药品同时限男和限女",
        "field": "patient_gender",
        "check": lambda a, b: (a.get("value") == "男" and b.get("value") == "女")
                           or (a.get("value") == "女" and b.get("value") == "男"),
    },
    "age_range_conflict": {
        "description": "年龄区间冲突 — 年龄上下限矛盾",
        "field": "patient_age",
        "check": lambda a, b: False,  # 需要解析 gt/lt 组合
    },
    "stage_mismatch": {
        "description": "阶段不匹配 — 同规则编码但 stage 不同",
        "field": None,
    },
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_rules_by_pillar(conn, pillar: str = None) -> list[dict]:
    """按支柱加载规则"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, rule_category, pillar, stage, "
            "       severity, conditions, action "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, rule_category, pillar, stage, "
            "       severity, conditions, action "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()
    return [dict(r) for r in rows]


def parse_conditions(conditions_str: str) -> dict:
    """解析 conditions JSON"""
    if not conditions_str:
        return {}
    try:
        return json.loads(conditions_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_fields(conditions: dict) -> list[dict]:
    """从 conditions 中提取所有 field/op/value 三元组"""
    fields = []
    if not conditions or not isinstance(conditions, dict):
        return fields
    if "conditions" in conditions and isinstance(conditions["conditions"], list):
        for c in conditions["conditions"]:
            if isinstance(c, dict) and "field" in c:
                fields.append({"field": c["field"], "op": c.get("op"), "value": c.get("value")})
            if isinstance(c, dict) and "conditions" in c:
                fields.extend(extract_fields(c))
    return fields


def detect_gender_conflicts(rules: list[dict]) -> list[dict]:
    """检测性别冲突"""
    conflicts = []
    # 按名称关键词分组
    groups = defaultdict(list)
    for r in rules:
        conds = parse_conditions(r["conditions"])
        fields = extract_fields(conds)
        for f in fields:
            if "gend" in f["field"] or "gender" in f["field"]:
                groups.setdefault(r["rule_code"], []).append({
                    "rule": r,
                    "gender_cond": f,
                })

    for code, entries in groups.items():
        values = set()
        for e in entries:
            values.add(str(e["gender_cond"].get("value")))
        if "男" in values and "女" in values:
            conflicts.append({
                "type": "gender_conflict",
                "severity": "high",
                "rules": [e["rule"]["rule_code"] for e in entries],
                "description": f"规则 {code} 同时限男和限女",
                "values": list(values),
            })
    return conflicts


def detect_stage_mismatches(rules: list[dict]) -> list[dict]:
    """检测同 rule_code 的 stage 不一致"""
    conflicts = []
    code_stages = defaultdict(set)
    code_names = {}
    for r in rules:
        code_stages[r["rule_code"]].add(r["stage"])
        code_names[r["rule_code"]] = r["rule_name"]
    for code, stages in code_stages.items():
        if len(stages) > 1:
            conflicts.append({
                "type": "stage_mismatch",
                "severity": "medium",
                "rules": [code],
                "description": f"规则 {code} 存在多个阶段: {', '.join(sorted(stages))}",
                "stages": sorted(stages),
            })
    return conflicts


def detect_condition_overlap(rules: list[dict]) -> list[dict]:
    """检测 conditions 完全相同的规则（用哈希加速）"""
    from collections import defaultdict
    hash_map = defaultdict(list)
    for r in rules:
        cond_str = r.get("conditions", "").strip()
        if not cond_str or cond_str == "{}":
            continue
        # 用 conditions 字符串的哈希作为 key（相同 conditions 哈希相同）
        h = hash(cond_str)
        hash_map[h].append(r)

    conflicts = []
    for h, group in hash_map.items():
        if len(group) > 1:
            codes = [r["rule_code"] for r in group]
            # 跳过同 rule_code 不同 stage 的正常情况
            unique_codes = list(set(codes))
            if len(unique_codes) > 1:
                conflicts.append({
                    "type": "duplicate_conditions",
                    "severity": "medium",
                    "rules": unique_codes[:10],  # 最多列 10 条
                    "description": f"{len(unique_codes)} 条规则 conditions 完全相同: {', '.join(unique_codes[:5])}...",
                    "count": len(unique_codes),
                })
    return conflicts


def detect_all(conn, pillar: str = None) -> list[dict]:
    """执行全部冲突检测"""
    rules = load_rules_by_pillar(conn, pillar)
    all_conflicts = []
    all_conflicts.extend(detect_gender_conflicts(rules))
    all_conflicts.extend(detect_stage_mismatches(rules))
    all_conflicts.extend(detect_condition_overlap(rules))
    return all_conflicts


def print_report(conflicts: list[dict], pillar: str = None):
    """输出可读报告"""
    title = f"规则冲突检测报告" if not pillar else f"规则冲突检测 — {pillar}"
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"  时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    if not conflicts:
        print(f"\n  ✅ 未发现冲突")
        return

    by_severity = {"high": [], "medium": [], "low": []}
    for c in conflicts:
        by_severity.setdefault(c["severity"], []).append(c)

    for sev, label in [("high", "🔴 高风险"), ("medium", "🟡 中风险"), ("low", "🟢 低风险")]:
        items = by_severity.get(sev, [])
        if items:
            print(f"\n  {label} ({len(items)} 个):")
            for c in items:
                print(f"    - {c['type']}: {c['description']}")

    print(f"\n  📊 总计: {len(conflicts)} 个冲突")
    print(f"    🔴 高风险: {len(by_severity.get('high', []))}")
    print(f"    🟡 中风险: {len(by_severity.get('medium', []))}")
    print(f"    🟢 低风险: {len(by_severity.get('low', []))}")


if __name__ == "__main__":
    pillar = None
    if "--pillar" in sys.argv:
        idx = sys.argv.index("--pillar")
        if idx + 1 < len(sys.argv):
            pillar = sys.argv[idx + 1]

    conn = get_conn()
    conflicts = detect_all(conn, pillar)
    conn.close()
    print_report(conflicts, pillar)
