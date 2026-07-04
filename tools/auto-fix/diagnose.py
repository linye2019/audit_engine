#!/usr/bin/env python3
"""
测试失败诊断器 — 解析 JUnit XML，分类失败根因，生成修复建议。
用法:
  python tools/auto-fix/diagnose.py
  python tools/auto-fix/diagnose.py --junit-xml reports/test_rules_results.xml
  python tools/auto-fix/diagnose.py --json
"""

import json
import os
import sys
import re
import xml.etree.ElementTree as ET
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_JUNIT = os.path.join(PROJECT_ROOT, "reports/test_rules_results.xml")

# 失败模式分类规则
FAILURE_PATTERNS = [
    {
        "mode": "fixture_error",
        "pattern": r"TypeError: __init__\(\) got an unexpected keyword argument '(\w+)'",
        "severity": "high",
        "description": "ClaimEvent/ClaimLine 字段名与模型不匹配",
    },
    {
        "mode": "fixture_error",
        "pattern": r"TypeError: __init__\(\) missing \d+ required positional argument: '(\w+)'",
        "severity": "high",
        "description": "ClaimEvent/ClaimLine 缺少必填字段",
    },
    {
        "mode": "assertion_false_negative",
        "pattern": r"AssertionError: 规则 (\S+) 未触发",
        "severity": "high",
        "description": "测试数据应触发规则但未触发",
    },
    {
        "mode": "assertion_false_positive",
        "pattern": r"AssertionError: 规则 (\S+) 不应触发但触发了",
        "severity": "medium",
        "description": "测试数据不应触发规则但触发了",
    },
    {
        "mode": "assertion_false_negative",
        "pattern": r"assert len\(matching\) >= 0",
        "severity": "medium",
        "description": "匹配结果数量不足",
    },
    {
        "mode": "db_error",
        "pattern": r"sqlite3\.OperationalError: no such table: (\w+)",
        "severity": "high",
        "description": "数据库表不存在，检查 init_db fixture 或 schema.sql",
    },
    {
        "mode": "dsl_syntax",
        "pattern": r"json\.JSONDecodeError",
        "severity": "high",
        "description": "conditions JSON 语法错误",
    },
    {
        "mode": "field_missing",
        "pattern": r"KeyError: '(\w+)'",
        "severity": "medium",
        "description": "上下文字段缺失",
    },
    {
        "mode": "field_missing",
        "pattern": r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        "severity": "medium",
        "description": "模型对象缺少属性",
    },
    {
        "mode": "timeout",
        "pattern": r"TimeoutError|timeout",
        "severity": "medium",
        "description": "测试执行超时",
    },
]


def parse_junit_xml(path: str) -> dict:
    """解析 JUnit XML 文件，返回测试结果"""
    if not os.path.exists(path):
        return {"error": f"JUnit XML 文件不存在: {path}", "testsuite": None}

    tree = ET.parse(path)
    root = tree.getroot()

    testsuite = root if root.tag == "testsuite" else root.find("testsuite")
    if testsuite is None:
        return {"error": "未找到 testsuite 元素", "testsuite": None}

    result = {
        "name": testsuite.get("name", ""),
        "tests": int(testsuite.get("tests", 0)),
        "failures": int(testsuite.get("failures", 0)),
        "errors": int(testsuite.get("errors", 0)),
        "time": float(testsuite.get("time", 0)),
        "testcases": [],
    }

    for tc in testsuite.findall("testcase"):
        case = {
            "name": tc.get("name", ""),
            "classname": tc.get("classname", ""),
            "time": float(tc.get("time", 0)),
            "status": "passed",
            "failure": None,
            "error": None,
        }
        failure = tc.find("failure")
        if failure is not None:
            case["status"] = "failed"
            case["failure"] = {
                "message": failure.get("message", ""),
                "type": failure.get("type", ""),
                "text": failure.text or "",
            }
        error = tc.find("error")
        if error is not None:
            case["status"] = "error"
            case["error"] = {
                "message": error.get("message", ""),
                "type": error.get("type", ""),
                "text": error.text or "",
            }
        result["testcases"].append(case)

    return result


def classify_failure(text: str) -> dict:
    """根据错误文本分类失败模式"""
    for pattern in FAILURE_PATTERNS:
        m = re.search(pattern["pattern"], text)
        if m:
            return {
                "mode": pattern["mode"],
                "severity": pattern["severity"],
                "description": pattern["description"],
                "matched_groups": m.groups(),
            }
    return {
        "mode": "unknown",
        "severity": "high",
        "description": "未分类的失败模式，需人工分析",
        "matched_groups": (),
    }


def generate_fix_suggestion(failure: dict) -> str:
    """根据失败模式生成修复建议"""
    mode = failure["mode"]
    groups = failure.get("matched_groups", ())

    suggestions = {
        "fixture_error": (
            f"字段名 '{groups[0] if groups else '?'}' 不在模型中。"
            f"请读取 `audit_engine/models/claim.py` 查看实际字段名，"
            f"然后修正 `test_rules_from_rulebook.py` 中的对应键名。"
        ),
        "assertion_false_negative": (
            "测试数据未触发规则。检查 conditions 中字段路径与 context 的映射关系。"
            "可以尝试调整测试数据的值使其符合规则条件。"
        ),
        "assertion_false_positive": (
            '测试数据不应触发但触发了。检查不匹配测试数据的值是否过于「干净」，'
            '确保所有字段取不可能值。'
        ),
        "db_error": (
            f"数据库表 '{groups[0] if groups else '?'}' 不存在。"
            f"检查 `init_db` fixture 是否正确应用了 `schema.sql`。"
        ),
        "dsl_syntax": (
            "conditions JSON 格式错误。检查 JSON 是否合法，"
            "特别注意引号、逗号、括号是否匹配。"
        ),
        "field_missing": (
            f"字段 '{groups[0] if groups else '?'}' 未在 context 中。"
            f"检查 `context_builder.py` 是否已实现该字段，或调整测试数据。"
        ),
        "timeout": (
            "测试超时。可能是规则执行过慢或存在死循环。"
            "检查 conditions 是否有递归逻辑。"
        ),
    }

    return suggestions.get(mode, "请人工分析失败原因。")


def diagnose(path: str = None) -> dict:
    """完整诊断流程：解析 XML → 分类失败 → 生成建议"""
    path = path or DEFAULT_JUNIT
    result = parse_junit_xml(path)

    if "error" in result:
        print(f"⚠️ {result['error']}")
        return result

    print(f"\n{'='*60}")
    print(f"  测试失败诊断报告")
    print(f"  文件: {path}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"  总计: {result['tests']} 个测试")
    print(f"  ✅ 通过: {result['tests'] - result['failures'] - result['errors']}")
    print(f"  ❌ 失败: {result['failures']}")
    print(f"  ⚠️  错误: {result['errors']}")
    print(f"  耗时: {result['time']:.2f}s")

    if result["failures"] == 0 and result["errors"] == 0:
        print(f"\n  🎉 全部通过，无需诊断！")
        return result

    diagnosed = []
    for tc in result["testcases"]:
        if tc["status"] == "passed":
            continue
        err_text = ""
        if tc["failure"]:
            err_text = tc["failure"]["text"] or tc["failure"]["message"]
        elif tc["error"]:
            err_text = tc["error"]["text"] or tc["error"]["message"]

        classification = classify_failure(err_text)
        suggestion = generate_fix_suggestion(classification)
        diagnosed.append({
            "test": tc["name"],
            "status": tc["status"],
            "mode": classification["mode"],
            "severity": classification["severity"],
            "description": classification["description"],
            "suggestion": suggestion,
        })

        print(f"\n  {'🔴' if classification['severity'] == 'high' else '🟡'} {tc['name']}")
        print(f"     模式: {classification['mode']}")
        print(f"     原因: {classification['description']}")
        print(f"     建议: {suggestion}")

    result["diagnosed"] = diagnosed
    print(f"\n{'='*60}")
    print(f"  共诊断 {len(diagnosed)} 个失败，"
          f"{sum(1 for d in diagnosed if d['severity'] == 'high')} 个高风险，"
          f"{sum(1 for d in diagnosed if d['severity'] == 'medium')} 个中风险")
    return result


if __name__ == "__main__":
    path = DEFAULT_JUNIT
    if "--junit-xml" in sys.argv:
        idx = sys.argv.index("--junit-xml")
        if idx + 1 < len(sys.argv):
            path = sys.argv[idx + 1]

    output_json = "--json" in sys.argv
    result = diagnose(path)

    if output_json and "error" not in result:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
