#!/usr/bin/env python3
"""
规则变更影响分析 — 对比当前规则与历史快照，识别新增/修改/删除。
用法:
  python tools/audit-assistant/analysis/impact_analysis.py [--snapshot SNAPSHOT_ID]
  python tools/audit-assistant/analysis/impact_analysis.py --save-snapshot  # 保存当前为快照
"""

import json
import sqlite3
import sys
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../medicare_engine.db")
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "../snapshots")


def get_conn():
    return sqlite3.connect(DB_PATH)


def fetch_all_rules(conn) -> list[dict]:
    """获取当前所有活跃规则"""
    rows = conn.execute(
        "SELECT id, rule_code, rule_name, rule_category, pillar, stage, "
        "       severity, conditions, action, is_active, version "
        "FROM rule_items WHERE is_active = 1"
    ).fetchall()
    drg = conn.execute(
        "SELECT id, rule_name, rule_type, conditions, severity, stage "
        "FROM drg_rules WHERE is_active = 1"
    ).fetchall()
    rules = []
    for r in rows:
        rules.append({
            "id": r["id"], "code": r["rule_code"], "name": r["rule_name"],
            "category": r["rule_category"], "pillar": r["pillar"],
            "stage": r["stage"], "severity": r["severity"],
            "conditions": r["conditions"], "type": "rule_items",
        })
    for r in drg:
        rules.append({
            "id": f"DRG-{r['id']}", "code": f"DRG-{r['rule_name']}",
            "name": r["rule_name"], "category": r["rule_type"],
            "pillar": "BZ", "stage": r["stage"], "severity": r["severity"],
            "conditions": r["conditions"], "type": "drg_rules",
        })
    return rules


def save_snapshot(rules: list[dict]) -> str:
    """保存当前规则快照"""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SNAPSHOT_DIR, f"rules_{timestamp}.json")
    with open(path, "w") as f:
        json.dump({"timestamp": timestamp, "total": len(rules), "rules": rules}, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(path: str) -> dict:
    """加载规则快照"""
    with open(path) as f:
        return json.load(f)


def get_latest_snapshot() -> Optional[dict]:
    """获取最新的快照"""
    if not os.path.isdir(SNAPSHOT_DIR):
        return None
    files = sorted([f for f in os.listdir(SNAPSHOT_DIR) if f.startswith("rules_")], reverse=True)
    if not files:
        return None
    return load_snapshot(os.path.join(SNAPSHOT_DIR, files[0]))


def compare_rules(old: list[dict], new: list[dict]) -> dict:
    """对比新旧规则，返回变更集"""
    old_map = {r["code"]: r for r in old}
    new_map = {r["code"]: r for r in new}

    old_codes = set(old_map.keys())
    new_codes = set(new_map.keys())

    added = [new_map[c] for c in new_codes - old_codes]
    removed = [old_map[c] for c in old_codes - new_codes]

    modified = []
    for code in old_codes & new_codes:
        o, n = old_map[code], new_map[code]
        changes = {}
        for key in ("stage", "severity", "conditions", "pillar"):
            if o.get(key) != n.get(key):
                changes[key] = {"old": o.get(key), "new": n.get(key)}
        if changes:
            modified.append({"code": code, "name": o["name"], "changes": changes})

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "stats": {
            "old_total": len(old),
            "new_total": len(new),
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
        }
    }


def print_report(diff: dict):
    """输出可读的变更报告"""
    s = diff["stats"]
    print(f"\n{'='*60}")
    print(f"  规则变更影响分析报告")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"  原规则数: {s['old_total']}")
    print(f"  现规则数: {s['new_total']}")
    print(f"  ➕ 新增: {s['added_count']}")
    print(f"  ❌ 删除: {s['removed_count']}")
    print(f"  ✏️  修改: {s['modified_count']}")
    print(f"{'='*60}")

    if diff["added"]:
        print(f"\n  ➕ 新增规则:")
        for r in diff["added"]:
            print(f"    - {r['code']} ({r['name']}) [{r['pillar']}/{r['stage']}]")

    if diff["removed"]:
        print(f"\n  ❌ 删除规则:")
        for r in diff["removed"]:
            print(f"    - {r['code']} ({r['name']})")

    if diff["modified"]:
        print(f"\n  ✏️  修改规则:")
        for r in diff["modified"]:
            print(f"    - {r['code']} ({r['name']}):")
            for k, v in r["changes"].items():
                print(f"      {k}: {v['old']} → {v['new']}")


if __name__ == "__main__":
    if "--save-snapshot" in sys.argv:
        conn = get_conn()
        conn.row_factory = sqlite3.Row
        rules = fetch_all_rules(conn)
        path = save_snapshot(rules)
        print(f"✅ 快照已保存: {path} ({len(rules)} 条规则)")
        conn.close()
        sys.exit(0)

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    current = fetch_all_rules(conn)
    conn.close()

    snapshot = get_latest_snapshot()
    if not snapshot:
        print("⚠️ 没有历史快照。先执行 --save-snapshot 创建基线。")
        path = save_snapshot(current)
        print(f"✅ 已保存当前规则为基线: {path}")
        sys.exit(0)

    diff = compare_rules(snapshot["rules"], current)
    print_report(diff)
