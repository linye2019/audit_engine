#!/usr/bin/env python3
"""
规则质量检查器 — 9 项全面检查，替代原来的 conflict_detector.py。
检测重复、孤儿引用、ICD-10 失效、空 conditions、字段路径错误等。

用法:
  python tools/audit-assistant/analysis/rule_quality_checker.py
  python tools/audit-assistant/analysis/rule_quality_checker.py --pillar YP
  python tools/audit-assistant/analysis/rule_quality_checker.py --json
  python tools/audit-assistant/analysis/rule_quality_checker.py --fix-duplicates
"""

import json
import re
import sqlite3
import sys
import os
from collections import defaultdict
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../../../medicare_engine.db")

# ============================================================
# 引擎支持的字段路径（来自 evaluator.py + context_builder.py）
# 注意：字段别名（如 patient_gender→gend）会在 resolove_field 时处理
SUPPORTED_FIELDS = {
    # claim_event（来自 ClaimEvent 模型 + ContextBuilder 计算字段）
    "claim_event.setl_id", "claim_event.mdtrt_id", "claim_event.gend",
    "claim_event.age", "claim_event.brdy", "claim_event.med_type",
    "claim_event.hosp_lv", "claim_event.dept", "claim_event.insutype",
    "claim_event.main_diag_code", "claim_event.main_diag_name",
    "claim_event.diag_codes", "claim_event.all_diagnoses",
    "claim_event.main_oprn_code", "claim_event.oprn_codes",
    "claim_event.adm_date", "claim_event.dscg_date",
    "claim_event.los", "claim_event.medfee_sumamt", "claim_event.drg_codg",
    "claim_event.co_claimed_names", "claim_event.claim_lines",
    "claim_event.is_internet", "claim_event.same_incision_group_count",
    "claim_event.ward_type", "claim_event.same_surcharge_category_count",
    "claim_event.same_session_modes_count", "claim_event.same_body_site",
    # claim_line（来自 ClaimLine 模型 + ContextBuilder 计算字段）
    "claim_line.feedetl_sn", "claim_line.mdtrt_id", "claim_line.fee_ocur_time",
    "claim_line.list_type", "claim_line.med_list_name", "claim_line.med_list_codg",
    "claim_line.medins_list_codg", "claim_line.cnt", "claim_line.pric",
    "claim_line.det_amt", "claim_line.bilg_dept_codg", "claim_line.bilg_dr_codg",
    "claim_line.acord_dept_codg", "claim_line.orders_dr_codg",
    "claim_line.exec_dept_codg", "claim_line.exec_dept_name",
    "claim_line.oprn_code_used", "claim_line.used_qty",
    "claim_line.hosp_appr_flag", "claim_line.chrgitm_lv",
    "claim_line.etip_flag", "claim_line.dscg_tkdrug_flag",
    "claim_line.matn_fee_flag", "claim_line.clr_type", "claim_line.comb_no",
    "claim_line.daily_quantity", "claim_line.usage_days",
    "claim_line.period_quantity", "claim_line.is_discounted",
    "claim_line.duration_hours", "claim_line.has_multiple_surcharges",
    "claim_line.calculation_method", "claim_line.is_highest_price",
    "claim_line.is_charged_separately", "claim_line.price_margin",
    "claim_line.is_basic_material", "claim_line.is_special_function",
    "claim_line.is_clinically_necessary", "claim_line.is_procurement_platform_listed",
    "claim_line.scan_type", "claim_line.has_informed_consent",
    # staff（来自 StaffQualification 表）
    "staff.bilg_dr.staff_codg", "staff.bilg_dr.title",
    "staff.bilg_dr.qualifications", "staff.bilg_dr.cert_levels",
}

# evaluator.py FIELD_ALIASES — 路径最后一段匹配这些别名即有效
FIELD_ALIASES = {
    "patient_gender", "patient_age", "hospital_level", "insurance_type",
    "diagnosis_codes", "med_list_code", "project_code", "visit_type", "prescription_type",
}


def is_field_supported(field_path: str) -> bool:
    """检查字段路径是否被引擎支持（含别名解析）"""
    if field_path in SUPPORTED_FIELDS:
        return True
    # 检查最后一段是否是别名
    last_part = field_path.split(".")[-1] if "." in field_path else field_path
    if last_part in FIELD_ALIASES:
        return True
    # 检查去掉 claim_event/claim_line 前缀后的别名
    for prefix in ("claim_event.", "claim_line."):
        if field_path.startswith(prefix):
            remainder = field_path[len(prefix):]
            if remainder in FIELD_ALIASES:
                return True
    return False

# 每个 pillar 的典型阶段
PILLAR_STAGES = {
    "YP": {"pre_check", "end_check"},
    "HC": {"pre_check", "end_check", "post_audit"},
    "FW": {"pre_check", "end_check", "post_audit"},
    "BZ": {"mid_check", "end_check", "post_audit"},
}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# 工具函数
# ============================================================

def extract_fields_from_conditions(conditions_str: str) -> list[str]:
    """从 conditions JSON 中提取所有 field 路径"""
    if not conditions_str or conditions_str.strip() in ("{}", ""):
        return []
    try:
        node = json.loads(conditions_str)
    except (json.JSONDecodeError, TypeError):
        return []
    fields = []
    def _walk(n):
        if isinstance(n, dict):
            if "field" in n and isinstance(n["field"], str):
                fields.append(n["field"])
            for v in n.values():
                _walk(v)
        elif isinstance(n, list):
            for item in n:
                _walk(item)
    _walk(node)
    return fields


def extract_icd10_from_conditions(conditions_str: str) -> list[str]:
    """从 conditions 中提取 ICD-10 编码值（只从 contains/not_contains 提取，跳过 regex 和 in）"""
    if not conditions_str:
        return []
    try:
        node = json.loads(conditions_str)
    except (json.JSONDecodeError, TypeError):
        return []
    codes = []
    def _walk(n):
        if isinstance(n, dict):
            op = n.get("op", "")
            value = n.get("value")
            # 只从 contains/not_contains 提取（值如 "E11|N18"）
            # 跳过 regex（值是正则模式）和 in（值是药品编码，非 ICD-10）
            if op in ("contains", "not_contains") and isinstance(value, str):
                for m in re.finditer(r'\b([A-Z]\d+(?:\.\d*)?)\b', value):
                    codes.append(m.group(1))
            # 不处理 dict 的子节点，避免重复
            for k, v in n.items():
                if k != "conditions":
                    _walk(v)
        elif isinstance(n, list):
            for item in n:
                _walk(item)
    _walk(node)
    return codes


def extract_catalog_codes(conditions_str: str) -> list[str]:
    """从 conditions 中提取目录编码（跳过 regex/not_regex 操作符）"""
    if not conditions_str:
        return []
    try:
        node = json.loads(conditions_str)
    except (json.JSONDecodeError, TypeError):
        return []
    codes = []
    def _walk(n):
        if isinstance(n, dict):
            field = n.get("field", "")
            value = n.get("value")
            op = n.get("op", "eq")
            # 跳过正则操作符——value 是模式不是编码
            if op in ("regex", "not_regex"):
                pass  # 不提取
            elif ("med_list_codg" in field or "med_list_code" in field or "project_code" in field) and value:
                if isinstance(value, list):
                    codes.extend(value)
                elif isinstance(value, str) and not value.startswith("\\"):
                    codes.append(value)
            for v in n.values():
                _walk(v)
        elif isinstance(n, list):
            for item in n:
                _walk(item)
    _walk(node)
    return codes


# ============================================================
# 9 项检查
# ============================================================

def check_duplicates(conn, pillar: str = None) -> list[dict]:
    """① 检测 conditions 完全相同的规则"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, rule_category, pillar, stage, severity, conditions, action_message "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, rule_category, pillar, stage, severity, conditions, action_message "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    hash_map = defaultdict(list)
    for r in rows:
        cond_str = (r["conditions"] or "").strip()
        if not cond_str or cond_str == "{}":
            continue
        h = hash(cond_str)
        hash_map[h].append(dict(r))

    findings = []
    for h, group in hash_map.items():
        if len(group) > 1:
            # 区分"真重复"（全部字段相同）和"假重复"（仅 action_message 不同）
            action_msgs = set(g["action_message"] for g in group)
            is_true_duplicate = len(action_msgs) <= 1
            codes = [g["rule_code"] for g in group]
            findings.append({
                "check": "duplicate_conditions",
                "severity": "high" if is_true_duplicate else "medium",
                "count": len(group),
                "rules": codes[:10],
                "description": f"{len(group)} 条规则 conditions 完全相同"
                             + ("" if is_true_duplicate else "（但 action_message 不同，可能来自不同来源）"),
                "true_duplicate": is_true_duplicate,
                "pillar": group[0]["pillar"],
                "category": group[0]["rule_category"],
                "sample_conditions": group[0]["conditions"][:120] if group[0]["conditions"] else "",
            })
    return findings


def check_orphan_catalog_refs(conn, pillar: str = None) -> list[dict]:
    """② 检测孤儿引用 — 规则的目录编码在目录表中不存在"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    # 加载目录编码（多字段匹配）
    yp_codes = set()
    for row in conn.execute("SELECT chs_code, atc_code FROM YPML").fetchall():
        if row[0] and row[0].strip():
            yp_codes.add(row[0].strip())
        if row[1] and row[1].strip():
            yp_codes.add(row[1].strip())
    yp_coverage = len(yp_codes)  # 非空编码数

    fw_codes = set()
    for row in conn.execute("SELECT med_list_codg, national_code FROM FWXM").fetchall():
        if row[0] and row[0].strip():
            fw_codes.add(row[0].strip())
        if row[1] and row[1].strip():
            fw_codes.add(row[1].strip())

    hc_codes = set()
    for row in conn.execute("SELECT hc_list_codg, ccode FROM HCML").fetchall():
        if row[0] and row[0].strip():
            hc_codes.add(row[0].strip())
        if row[1] and row[1].strip():
            hc_codes.add(row[1].strip())

    findings = []
    for r in rows:
        cond = r["conditions"]
        codes = extract_catalog_codes(cond)
        if not codes:
            continue
        pillar_codes = {"YP": yp_codes, "FW": fw_codes, "HC": hc_codes}.get(r["pillar"], set())
        missing = [c for c in codes if c not in pillar_codes]
        if missing:
            severity = "medium" if r["pillar"] == "YP" else "high"
            note = ""
            if r["pillar"] == "YP":
                note = f"（YPML.chs_code 覆盖率约 {yp_coverage}/4567，缺失可能因目录表未录入而非规则错误）"
            findings.append({
                "check": "orphan_catalog_ref",
                "severity": severity,
                "count": len(missing),
                "rules": [r["rule_code"]],
                "description": f"规则引用 {len(missing)} 个目录编码不存在: {', '.join(missing[:5])}{note}",
                "missing_codes": missing[:5],
                "pillar": r["pillar"],
            })
    return findings


def check_icd10_validity(conn, pillar: str = None) -> list[dict]:
    """③ 检测 ICD-10 编码在 icd_10 表中不存在"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, conditions "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, conditions "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    # 加载 ICD-10 编码（用于前缀匹配）
    valid_icd10_prefixes = set()
    for row in conn.execute("SELECT chs_code FROM icd_10 WHERE chs_code IS NOT NULL").fetchall():
        code = row[0]
        valid_icd10_prefixes.add(code)
        # 也加入前缀版本（如 E11.000 → E11, E11.0）
        parts = code.split(".")
        if len(parts) == 2:
            valid_icd10_prefixes.add(parts[0])
            valid_icd10_prefixes.add(f"{parts[0]}.{parts[1][0]}")

    findings = []
    seen = set()
    for r in rows:
        cond = r["conditions"]
        codes = extract_icd10_from_conditions(cond)
        for code in codes:
            # 前缀匹配：规则中的 E11 匹配 icd_10 中的 E11.000 / E11.900
            is_valid = code in valid_icd10_prefixes
            if not is_valid:
                for v in valid_icd10_prefixes:
                    if v.startswith(code) or code.startswith(v):
                        is_valid = True
                        break
            if not is_valid and code not in seen:
                seen.add(code)
                findings.append({
                    "check": "invalid_icd10",
                    "severity": "high",
                    "count": 1,
                    "rules": [r["rule_code"]],
                    "description": f"ICD-10 编码 {code} 在 icd_10 表中不存在（含前缀匹配）",
                    "icd10_code": code,
                    "pillar": r["pillar"],
                })
    return findings


def check_empty_conditions(conn, pillar: str = None) -> list[dict]:
    """④ 检测空 conditions — 只有 type+description 或空 JSON"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    findings = []
    for r in rows:
        cond = (r["conditions"] or "").strip()
        if not cond or cond == "{}":
            findings.append({
                "check": "empty_conditions",
                "severity": "high",
                "count": 1,
                "rules": [r["rule_code"]],
                "description": f"规则 conditions 为空 ({cond})",
                "pillar": r["pillar"],
            })
            continue
        try:
            node = json.loads(cond)
            if isinstance(node, dict) and "type" in node and "description" in node and "logic" not in node:
                findings.append({
                    "check": "text_only_conditions",
                    "severity": "high",
                    "count": 1,
                    "rules": [r["rule_code"]],
                    "description": f"规则 conditions 只有 type+description，无可执行逻辑: {node.get('description', '')[:60]}",
                    "pillar": r["pillar"],
                })
        except (json.JSONDecodeError, TypeError):
            findings.append({
                "check": "invalid_json_conditions",
                "severity": "high",
                "count": 1,
                "rules": [r["rule_code"]],
                "description": f"规则 conditions 不是合法 JSON",
                "pillar": r["pillar"],
            })
    return findings


def check_stage_mismatch(conn, pillar: str = None) -> list[dict]:
    """⑤ 检测阶段错配 — 规则的 stage 不在其 pillar 的典型阶段中"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    findings = []
    for r in rows:
        p = r["pillar"]
        s = r["stage"]
        if p in PILLAR_STAGES and s not in PILLAR_STAGES[p]:
            findings.append({
                "check": "stage_mismatch",
                "severity": "medium",
                "count": 1,
                "rules": [r["rule_code"]],
                "description": f"规则 stage={s} 不在 {p} 的典型阶段 {PILLAR_STAGES[p]} 中",
                "pillar": p,
                "actual_stage": s,
                "expected_stages": sorted(PILLAR_STAGES[p]),
            })
    return findings


def check_field_path_validity(conn, pillar: str = None) -> list[dict]:
    """⑥ 检测字段路径错误 — conditions 引用的 field 不是引擎支持的路径"""
    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, stage, conditions "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    findings = []
    for r in rows:
        fields = extract_fields_from_conditions(r["conditions"])
        for f in fields:
            if not is_field_supported(f):
                findings.append({
                    "check": "invalid_field_path",
                    "severity": "medium",
                    "count": 1,
                    "rules": [r["rule_code"]],
                    "description": f"字段路径 '{f}' 不是引擎支持的字段（含别名）",
                    "field_path": f,
                    "pillar": r["pillar"],
                })
    return findings


def check_severity_consistency(conn, pillar: str = None) -> list[dict]:
    """⑦ 检测 severity 不一致 — 同类规则用了不同 severity"""
    if pillar:
        rows = conn.execute(
            "SELECT rule_category, pillar, severity, COUNT(*) as cnt "
            "FROM rule_items WHERE is_active = 1 AND pillar = ? "
            "GROUP BY rule_category, severity", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT rule_category, pillar, severity, COUNT(*) as cnt "
            "FROM rule_items WHERE is_active = 1 "
            "GROUP BY rule_category, severity"
        ).fetchall()

    cat_map = defaultdict(dict)
    for r in rows:
        cat_map[(r["pillar"], r["rule_category"])][r["severity"]] = r["cnt"]

    findings = []
    for (p, cat), sev_map in cat_map.items():
        if len(sev_map) > 1:
            total = sum(sev_map.values())
            main_sev = max(sev_map, key=sev_map.get)
            others = {k: v for k, v in sev_map.items() if k != main_sev}
            findings.append({
                "check": "severity_inconsistency",
                "severity": "low",
                "count": sum(others.values()),
                "rules": [],
                "description": f"{cat} 类规则中 {sum(others.values())}/{total} 条 severity 不一致："
                             f"主流 {main_sev}={sev_map[main_sev]}，其他 {dict(others)}",
                "pillar": p,
                "category": cat,
                "main_severity": main_sev,
                "other_severities": dict(others),
            })
    return findings


def check_rule_density(conn, pillar: str = None) -> list[dict]:
    """⑧ 检测规则密度 — 同一来源、同一类别的高密度（可能规则粒度太细）"""
    if pillar:
        rows = conn.execute(
            "SELECT rule_category, pillar, COUNT(*) as cnt "
            "FROM rule_items WHERE is_active = 1 AND pillar = ? "
            "GROUP BY rule_category ORDER BY cnt DESC", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT rule_category, pillar, COUNT(*) as cnt "
            "FROM rule_items WHERE is_active = 1 "
            "GROUP BY rule_category ORDER BY cnt DESC"
        ).fetchall()

    findings = []
    for r in rows:
        if r["cnt"] > 100:
            findings.append({
                "check": "high_rule_density",
                "severity": "low",
                "count": r["cnt"],
                "rules": [],
                "description": f"{r['rule_category']} 类有 {r['cnt']} 条规则，密度较高，建议检查是否可参数化",
                "pillar": r["pillar"],
                "category": r["rule_category"],
                "rule_count": r["cnt"],
            })
    return findings


def check_expired_refs(conn, pillar: str = None) -> list[dict]:
    """⑨ 检测规则引用的目录条目已停用"""
    # 目录表如果没有 is_deleted 字段则跳过
    has_deleted_flag = conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('YPML') WHERE name='is_deleted'"
    ).fetchone()[0]
    if not has_deleted_flag:
        return []

    if pillar:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, conditions "
            "FROM rule_items WHERE is_active = 1 AND pillar = ?", (pillar,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, rule_code, rule_name, pillar, conditions "
            "FROM rule_items WHERE is_active = 1"
        ).fetchall()

    expired = set(r[0] for r in conn.execute(
        "SELECT chs_code FROM YPML WHERE is_deleted = 1 AND chs_code IS NOT NULL"
    ).fetchall())

    findings = []
    for r in rows:
        codes = extract_catalog_codes(r["conditions"])
        found = [c for c in codes if c in expired]
        if found:
            findings.append({
                "check": "expired_catalog_ref",
                "severity": "medium",
                "count": len(found),
                "rules": [r["rule_code"]],
                "description": f"规则引用 {len(found)} 个已停用的目录编码: {', '.join(found[:5])}",
                "expired_codes": found[:5],
                "pillar": r["pillar"],
            })
    return findings


# ============================================================
# 汇总与报告
# ============================================================

def run_all_checks(conn, pillar: str = None) -> dict:
    """运行全部 9 项检查"""
    checks = [
        ("duplicate_conditions", "重复规则检测", check_duplicates),
        ("orphan_catalog_ref", "孤儿目录引用", check_orphan_catalog_refs),
        ("invalid_icd10", "ICD-10 编码失效", check_icd10_validity),
        ("empty_conditions", "空 conditions 检测", check_empty_conditions),
        ("stage_mismatch", "阶段错配检测", check_stage_mismatch),
        ("invalid_field_path", "字段路径错误", check_field_path_validity),
        ("severity_inconsistency", "Severity 不一致", check_severity_consistency),
        ("high_rule_density", "规则密度过高", check_rule_density),
        ("expired_catalog_ref", "停用目录引用", check_expired_refs),
    ]

    results = {}
    total_findings = 0
    for key, name, func in checks:
        findings = func(conn, pillar)
        results[key] = {"name": name, "findings": findings, "count": len(findings)}
        total_findings += len(findings)

    sev_count = {"high": 0, "medium": 0, "low": 0}
    for key, data in results.items():
        for f in data["findings"]:
            sev_count[f["severity"]] = sev_count.get(f["severity"], 0) + 1

    return {
        "pillar": pillar or "ALL",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_findings": total_findings,
        "severity_summary": sev_count,
        "checks": results,
    }


def print_report(report: dict):
    """输出彩色可读报告"""
    print(f"\n{'='*60}")
    title = "规则质量检查报告" if report["pillar"] == "ALL" else f"规则质量检查 — {report['pillar']}"
    print(f"  {title}")
    print(f"  时间: {report['timestamp']}")
    print(f"{'='*60}")
    print(f"  检查项: 9 项")
    print(f"  发现问题: {report['total_findings']} 个")
    print(f"    {'🔴' if report['severity_summary'].get('high',0) > 0 else '  '} 高风险: {report['severity_summary'].get('high', 0)}")
    print(f"    {'🟡' if report['severity_summary'].get('medium',0) > 0 else '  '} 中风险: {report['severity_summary'].get('medium', 0)}")
    print(f"    {'🟢' if report['severity_summary'].get('low',0) > 0 else '  '} 低风险: {report['severity_summary'].get('low', 0)}")
    print(f"{'='*60}")

    for key, data in report["checks"].items():
        if data["count"] == 0:
            continue
        sev = "🔴" if any(f["severity"] == "high" for f in data["findings"]) else \
              "🟡" if any(f["severity"] == "medium" for f in data["findings"]) else "🟢"
        print(f"\n  {sev} [{data['count']}个] {data['name']}")
        for f in data["findings"][:5]:  # 最多显示 5 条
            rules_str = ", ".join(f["rules"][:3]) if f["rules"] else ""
            print(f"    - {f['description']}")
            if rules_str:
                print(f"      规则: {rules_str}")
        if data["count"] > 5:
            print(f"      ... 还有 {data['count'] - 5} 个")


if __name__ == "__main__":
    pillar = None
    if "--pillar" in sys.argv:
        idx = sys.argv.index("--pillar")
        if idx + 1 < len(sys.argv):
            pillar = sys.argv[idx + 1]

    output_json = "--json" in sys.argv

    conn = get_conn()
    report = run_all_checks(conn, pillar)
    conn.close()

    if output_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(report)

    # 出口码：有问题返回 1
    if report["severity_summary"].get("high", 0) > 0:
        sys.exit(1)
