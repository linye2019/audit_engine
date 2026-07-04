#!/usr/bin/env python3
"""
Fixture 字段名修复器 — 自动修正 test_rules_from_rulebook.py 中
ClaimEvent/ClaimLine 字段名与模型不匹配的问题。
"""

import json
import os
import re
import sys
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_FILE = os.path.join(PROJECT_ROOT, "tests/test_rules_from_rulebook.py")
MODEL_FILE = os.path.join(PROJECT_ROOT, "audit_engine/models/claim.py")


def get_model_fields() -> dict:
    """从 ClaimModel 中提取合法的字段名"""
    if not os.path.exists(MODEL_FILE):
        return {"ClaimEvent": set(), "ClaimLine": set()}

    fields = {"ClaimEvent": set(), "ClaimLine": set()}
    current_class = None
    with open(MODEL_FILE) as f:
        for line in f:
            m = re.match(r'class\s+(ClaimEvent|ClaimLine)', line)
            if m:
                current_class = m.group(1)
                continue
            m = re.match(r'\s+(\w+):', line)
            if m and current_class:
                fields[current_class].add(m.group(1))
    return fields


def fix_claim_event_fields(content: str, valid_fields: set) -> tuple[str, list]:
    """修复 ClaimEvent 实例化中的字段名"""
    fixes = []
    # 匹配 ClaimEvent( 到 ) 的调用
    pattern = r'(ClaimEvent\s*\([^)]*\))'
    def replace_call(m):
        call = m.group(1)
        # 提取所有 keyword=value
        def fix_kw(kw_m):
            kw = kw_m.group(1)
            if kw not in valid_fields:
                fixes.append(f"  {kw} → ? (不在 ClaimEvent 中)")
                # 尝试猜测正确字段名
                alt = guess_alternative(kw, valid_fields)
                if alt:
                    fixes[-1] = f"  {kw} → {alt}"
                    return f"{alt}={kw_m.group(2)}"
            return kw_m.group(0)
        call = re.sub(r'(\w+)\s*=', fix_kw, call)
        return call
    content = re.sub(pattern, replace_call, content)
    return content, fixes


def guess_alternative(wrong: str, valid: set) -> Optional[str]:
    """猜测正确的字段名"""
    mapping = {
        # 常见错误映射
        "audit_date": None,  # 是 audit_claim 的参数，不是 ClaimEvent 字段
        "patient_age": "brdy",  # age 是 property，由 brdy 计算
        "patient_sex": "gend",
        "bill_type": None,
        "department": "dept",
        "exec_dept": None,
        "staff_id": None,
        "staff_name": None,
        "staff_qualification": None,
        "hospital_name": None,
        "hp_id": None,
        "amount": "cnt",
        "price": "pric",
        "total": "det_amt",
        "unit": "pric_ut",
        "icd_codes": None,
        "diagnosis_codes": "diag_codes",  # 别名，在 FIELD_ALIASES 中
    }
    result = mapping.get(wrong)
    if result and result in valid:
        return result
    # 不在映射表中，找最接近的
    import difflib
    candidates = difflib.get_close_matches(wrong, valid, n=1, cutoff=0.6)
    return candidates[0] if candidates else None


def fix_claim_line_fields(content: str, valid_fields: set) -> tuple[str, list]:
    """修复 ClaimLine 实例化中的字段名"""
    fixes = []
    pattern = r'(ClaimLine\s*\([^)]*\))'
    def replace_call(m):
        call = m.group(1)
        def fix_kw(kw_m):
            kw = kw_m.group(1)
            if kw not in valid_fields:
                fixes.append(f"  {kw} → ? (不在 ClaimLine 中)")
                alt = guess_alternative(kw, valid_fields)
                if alt:
                    fixes[-1] = f"  {kw} → {alt}"
                    return f"{alt}={kw_m.group(2)}"
            return kw_m.group(0)
        call = re.sub(r'(\w+)\s*=', fix_kw, call)
        return call
    content = re.sub(pattern, replace_call, content)
    return content, fixes


def fix():
    """执行修复"""
    if not os.path.exists(TEST_FILE):
        print(f"⚠️ 测试文件不存在: {TEST_FILE}")
        return False

    models = get_model_fields()
    print(f"ClaimEvent 合法字段: {len(models['ClaimEvent'])} 个")
    print(f"ClaimLine 合法字段: {len(models['ClaimLine'])} 个")

    with open(TEST_FILE) as f:
        content = f.read()

    all_fixes = []

    content, ce_fixes = fix_claim_event_fields(content, models["ClaimEvent"])
    all_fixes.extend(ce_fixes)

    content, cl_fixes = fix_claim_line_fields(content, models["ClaimLine"])
    all_fixes.extend(cl_fixes)

    if all_fixes:
        # 写回文件
        with open(TEST_FILE, 'w') as f:
            f.write(content)
        print(f"\n✅ 已修复 {len(all_fixes)} 个字段名:")
        for fix in all_fixes:
            print(f"  {fix}")
        return True
    else:
        print("\n✅ 未发现字段名错误")
        return True


if __name__ == "__main__":
    success = fix()
    sys.exit(0 if success else 1)
