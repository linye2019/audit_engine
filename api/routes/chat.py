"""AI 审核助手聊天接口 — 意图路由 + 多工具调用"""

import json
import re
import sqlite3
import os
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import db_cursor

router = APIRouter(tags=["AI 助手"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    source: str = ""
    data: dict = {}
    intent: str = ""


INTENTS = [
    {
        "pattern": r"(为什么|怎么|为何).*(拦截|拒绝|警告|不通过|失败)",
        "intent": "explain_audit",
        "description": "解释审核结果",
    },
    {
        "pattern": r"(pre_check|mid_check|end_check|post_audit|事前|事中|事后).*(有哪些|列出)|(有哪些|列出).*(pre_check|mid_check|end_check|post_audit|事前|事中|事后)",
        "intent": "list_stage_rules",
        "description": "按阶段列出规则",
    },
    {
        "pattern": r"([A-Z]+_[A-Z0-9]+)",
        "intent": "query_rule",
        "description": "查询规则",
        "extract_group": 1,
    },
    {
        "pattern": r"(是什么|查询|解释).*(规则|限定)",
        "intent": "query_rule",
        "description": "查询规则",
    },
    {
        "pattern": r"(在不在|有没有|查一下|查).*(目录|药品|耗材|项目|中药)",
        "intent": "query_catalog",
        "description": "查询目录",
    },
    {
        "pattern": r"(测试|pytest|test).*(失败|错误|不过|挂了|报错)",
        "intent": "diagnose_test",
        "description": "诊断测试失败",
    },
    {
        "pattern": r"(有哪些|列出|枚举|都有).*(规则|YP|HC|FW|BZ|药品|项目|耗材)",
        "intent": "list_rules",
        "description": "列出规则",
    },
    {
        "pattern": r"(修改|修复|修正|更改|改进).*(测试|数据|规则)",
        "intent": "suggest_fix",
        "description": "建议修复",
    },
    {
        "pattern": r"(冲突|重复|矛盾)",
        "intent": "check_conflicts",
        "description": "检查冲突",
    },
    {
        "pattern": r"(覆盖率|覆盖)",
        "intent": "check_coverage",
        "description": "检查覆盖率",
    },
    {
        "pattern": r"(变化|变更|新增|删除|修改)",
        "intent": "check_impact",
        "description": "检查变更影响",
    },
    {
        "pattern": r"(帮助|help|/?)$",
        "intent": "show_help",
        "description": "显示帮助",
    },
]


def classify_intent(text: str) -> dict:
    """意图分类"""
    for intent_def in INTENTS:
        match = re.search(intent_def["pattern"], text, re.IGNORECASE)
        if match:
            result = {"intent": intent_def["intent"], "description": intent_def["description"]}
            if intent_def.get("extract_group"):
                result["extracted"] = match.group(intent_def["extract_group"])
            return result
    return {"intent": "unknown", "description": "未知意图"}


def _query_rule(code: str) -> ChatResponse:
    """查询规则详情"""
    with db_cursor() as conn:
        row = conn.execute(
            "SELECT rule_code, rule_name, rule_category, pillar, stage, "
            "       severity, action_message "
            "FROM rule_items WHERE rule_category = ? AND is_active = 1 LIMIT 1",
            (code,)
        ).fetchone()

        if row:
            count = conn.execute(
                "SELECT COUNT(*) FROM rule_items WHERE rule_category = ? AND is_active = 1",
                (code,)
            ).fetchone()[0]

            sev_map = {"violation": "违规", "suspicious": "可疑", "info": "提示"}
            sev_cn = sev_map.get(row["severity"], row["severity"])

            reply = (
                f"**{row['rule_code']}** — {row['rule_name']}\n"
                f"柱: {row['pillar']} · 阶段: {row['stage']} · "
                f"级别: {row['severity']}（{sev_cn}）\n"
                f"同类规则: {count} 条\n"
                f"说明: {row['action_message'] or '无额外说明'}"
            )

            example = conn.execute(
                "SELECT conditions FROM rule_items "
                "WHERE rule_category = ? AND is_active = 1 LIMIT 1",
                (code,)
            ).fetchone()
            example_cond = ""
            if example and example["conditions"]:
                try:
                    node = json.loads(example["conditions"])
                    conds = node.get("conditions", [])
                    parts = []
                    for c in conds[:3]:
                        if isinstance(c, dict) and "field" in c:
                            parts.append(f"{c['field']} {c['op']} {c['value']}")
                    if parts:
                        example_cond = "\n条件示例: " + " 且 ".join(parts)
                except (json.JSONDecodeError, TypeError):
                    pass

            return ChatResponse(
                reply=reply + example_cond,
                source="规则库",
                data={"rule_code": code, "count": count},
                intent="query_rule"
            )

        return ChatResponse(
            reply=f"未找到规则 **{code}**。\n"
                  f"试试: YP_SYZ, YP_XB, YP_ETZY, HC_SP, FW_XMHC",
            source="规则库",
            intent="query_rule"
        )


def _query_catalog(keyword: str) -> ChatResponse:
    """查询目录"""
    results = []
    with db_cursor() as conn:
        drugs = conn.execute(
            "SELECT drug_name, chs_code FROM YPML "
            "WHERE drug_name LIKE ? LIMIT 5",
            (f"%{keyword}%",)
        ).fetchall()
        for d in drugs:
            results.append(f"💊 {d['drug_name']}　`{d['chs_code'] or ''}`")

        services = conn.execute(
            "SELECT name, med_list_codg FROM FWXM "
            "WHERE name LIKE ? LIMIT 5",
            (f"%{keyword}%",)
        ).fetchall()
        for s in services:
            results.append(f"📋 {s['name']}　`{s['med_list_codg'] or ''}`")

        consumables = conn.execute(
            "SELECT hc_list_name, hc_list_codg FROM HCML "
            "WHERE hc_list_name LIKE ? LIMIT 5",
            (f"%{keyword}%",)
        ).fetchall()
        for c in consumables:
            results.append(f"🔧 {c['hc_list_name']}　`{c['hc_list_codg'] or ''}`")

    if results:
        return ChatResponse(
            reply=f"🔍 目录查询: **{keyword}**\n" + "\n".join(results),
            source="目录表",
            data={"keyword": keyword, "count": len(results)},
            intent="query_catalog"
        )

    return ChatResponse(
        reply=f"未在目录中找到 **{keyword}**。\n请尝试其他关键词，或检查名称是否准确。",
        source="目录表",
        intent="query_catalog"
    )


def _list_rules(pillar: str = None) -> ChatResponse:
    """列出规则"""
    with db_cursor() as conn:
        if pillar:
            rows = conn.execute(
                "SELECT DISTINCT rule_category, pillar, COUNT(*) as cnt "
                "FROM rule_items WHERE is_active = 1 AND pillar = ? "
                "GROUP BY rule_category, pillar ORDER BY cnt DESC LIMIT 10",
                (pillar,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT rule_category, pillar, COUNT(*) as cnt "
                "FROM rule_items WHERE is_active = 1 "
                "GROUP BY rule_category, pillar ORDER BY cnt DESC LIMIT 10",
            ).fetchall()

        if rows:
            lines = []
            total = 0
            for r in rows:
                lines.append(f"• **{r['rule_category']}** ({r['pillar']}) — {r['cnt']} 条")
                total += r["cnt"]

            reply = f"📋 规则列表（共 {total} 条）:\n" + "\n".join(lines)
            if len(rows) >= 10:
                reply += "\n... 显示前10个类别，更多请指定柱别"

            return ChatResponse(
                reply=reply,
                source="规则库",
                data={"total": total, "categories": len(rows)},
                intent="list_rules"
            )

        return ChatResponse(
            reply="暂无规则数据",
            source="规则库",
            intent="list_rules"
        )


def _list_stage_rules(stage: str = None) -> ChatResponse:
    """按阶段列出规则"""
    with db_cursor() as conn:
        if stage:
            rows = conn.execute(
                "SELECT DISTINCT rule_category, pillar, COUNT(*) as cnt "
                "FROM rule_items WHERE is_active = 1 AND stage = ? "
                "GROUP BY rule_category, pillar ORDER BY cnt DESC LIMIT 10",
                (stage,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT stage, COUNT(*) as cnt FROM rule_items WHERE is_active = 1 "
                "GROUP BY stage ORDER BY cnt DESC",
            ).fetchall()

        if rows:
            if stage:
                lines = []
                total = 0
                for r in rows:
                    lines.append(f"• **{r['rule_category']}** ({r['pillar']}) — {r['cnt']} 条")
                    total += r["cnt"]
                reply = f"📋 {stage} 阶段规则（共 {total} 条）:\n" + "\n".join(lines)
            else:
                stage_map = {"pre_check": "事前提醒", "mid_check": "在院日终", "end_check": "出科审核", "post_audit": "事后监管"}
                lines = [f"• **{stage_map.get(r['stage'], r['stage'])}** ({r['stage']}) — {r['cnt']} 条" for r in rows]
                reply = f"📋 各阶段规则分布:\n" + "\n".join(lines)

            return ChatResponse(
                reply=reply,
                source="规则库",
                intent="list_stage_rules"
            )

        return ChatResponse(
            reply="暂无阶段规则数据",
            source="规则库",
            intent="list_stage_rules"
        )


def _diagnose_test() -> ChatResponse:
    """诊断测试失败"""
    log_file = os.path.join(os.path.dirname(__file__), "../../reports/test_rules_history.log")
    xml_file = os.path.join(os.path.dirname(__file__), "../../reports/test_rules_results.xml")

    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()[-20:]
            content = "".join(lines)
            if "FAILED" in content:
                fail_count = content.count("FAILED")
                reply = f"🔍 测试失败诊断（最近记录）:\n\n"
                reply += f"检测到 {fail_count} 个失败测试。\n\n"
                reply += "最近日志片段:\n"
                for line in lines:
                    if "FAILED" in line or "ERROR" in line or "test_" in line:
                        reply += line
                reply += "\n💡 建议: 运行 /test-diagnose 查看详细诊断"
            else:
                reply = "✅ 最近测试全部通过！"

        return ChatResponse(
            reply=reply,
            source="测试日志",
            intent="diagnose_test"
        )

    return ChatResponse(
        reply="未找到测试日志，请先运行 /gen-tests --run 生成测试结果。",
        source="系统",
        intent="diagnose_test"
    )


def _explain_audit() -> ChatResponse:
    """解释审核结果"""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_result ORDER BY audited_at DESC LIMIT 5"
        ).fetchall()

        if rows:
            lines = []
            for r in rows:
                rule_code = r["rule_code"] or r["rule_category"]
                lines.append(f"• **{rule_code}** — {r['verdict']}")
                if r["reasoning"]:
                    lines.append(f"  原因: {r['reasoning']}")
                if r["matched_facts"]:
                    try:
                        facts = json.loads(r["matched_facts"])
                        if isinstance(facts, dict) and "description" in facts:
                            lines.append(f"  详情: {facts['description']}")
                    except:
                        pass

            reply = f"📊 最近审核结果（前5条）:\n" + "\n".join(lines)
            reply += "\n💡 如果您想了解具体某条规则的拦截原因，请告诉我规则编码。"

            return ChatResponse(
                reply=reply,
                source="审核结果表",
                intent="explain_audit"
            )

        return ChatResponse(
            reply="暂无审核结果记录。请先在规则沙箱中执行测试，或调用审核API。",
            source="系统",
            intent="explain_audit"
        )


def _call_analysis_api(endpoint: str, params: dict = {}) -> ChatResponse:
    """调用分析API"""
    try:
        import urllib.request
        import urllib.parse

        url = f"http://localhost:8000/api/v1/agent/{endpoint}?" + urllib.parse.urlencode(params)
        resp = urllib.request.urlopen(url, timeout=30)
        data = json.loads(resp.read().decode())

        return ChatResponse(
            reply=data.get("result", "分析完成"),
            source="分析API",
            data=data.get("data", {}),
            intent=endpoint
        )
    except Exception as e:
        return ChatResponse(
            reply=f"分析调用失败: {str(e)}",
            source="系统错误",
            intent=endpoint
        )


def _show_help() -> ChatResponse:
    """显示帮助"""
    return ChatResponse(
        reply="""
🤖 **AI 医保审核智能体 — 使用帮助**

💬 **对话查询**
• `规则编码 是什么？` — 查询规则详情（如: YP_SYZ）
• `查一下 药品名称` — 查询目录（如: 查一下阿莫西林）
• `为什么被拦截？` — 解释审核结果
• `测试为什么失败？` — 诊断测试问题

📊 **主动分析**
• `检查规则有没有冲突？` — 冲突检测
• `规则测试覆盖了多少？` — 覆盖率分析
• `最近规则有什么变化？` — 变更影响分析

📋 **规则列表**
• `YP有哪些规则？` — 按柱别列出
• `pre_check有哪些规则？` — 按阶段列出

⚡ **快捷操作**
• 点击左侧面板能力卡片快速查询
• 查看右侧系统概览统计

🔗 **相关链接**
• 规则沙箱 — /rule_sandbox.html
• 规则管理 — /rule_admin.html
• API文档 — /docs
""",
        source="帮助中心",
        intent="show_help"
    )


@router.post("/api/v1/chat", summary="AI 审核助手对话")
def chat(req: ChatRequest) -> ChatResponse:
    """AI 审核助手 — 意图路由 + 多工具调用"""
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "消息不能为空")

    intent_info = classify_intent(text)
    intent = intent_info["intent"]

    if intent == "query_rule":
        code = intent_info.get("extracted")
        if code:
            return _query_rule(code)
        match = re.search(r'([A-Z]+_[A-Z0-9]+)', text)
        if match:
            return _query_rule(match.group(1))
        return ChatResponse(
            reply="请提供规则编码，例如: YP_SYZ 是什么？",
            source="引导",
            intent="query_rule"
        )

    if intent == "query_catalog":
        keyword = re.sub(r'查(一下|询)?', '', text)
        keyword = re.sub(r'在不在|有没有|目录|药品|耗材|项目|中药|里', '', keyword).strip()
        if keyword:
            return _query_catalog(keyword)
        return ChatResponse(reply="你想查什么？例如：查一下阿莫西林", source="引导", intent="query_catalog")

    if intent == "list_rules":
        match = re.search(r'(YP|HC|FW|BZ)', text.upper())
        pillar = match.group(1) if match else None
        return _list_rules(pillar)

    if intent == "list_stage_rules":
        match = re.search(r'(pre_check|mid_check|end_check|post_audit)', text)
        stage = match.group(1) if match else None
        return _list_stage_rules(stage)

    if intent == "diagnose_test":
        return _diagnose_test()

    if intent == "explain_audit":
        return _explain_audit()

    if intent == "check_conflicts":
        return _call_analysis_api("conflicts")

    if intent == "check_coverage":
        return _call_analysis_api("coverage")

    if intent == "check_impact":
        return _call_analysis_api("impact")

    if intent == "suggest_fix":
        return ChatResponse(
            reply="💡 测试修复建议:\n\n"
                  "1. 运行 `/test-diagnose` 诊断失败原因\n"
                  "2. 使用 `/gen-tests --fix` 自动修复\n"
                  "3. 运行 `/gen-tests --run` 验证修复结果\n"
                  "4. 如果失败次数超过3次，请手动检查测试数据",
            source="系统",
            intent="suggest_fix"
        )

    if intent == "show_help":
        return _show_help()

    return ChatResponse(
        reply=f"我是 AI 医保审核智能体。您的问题意图是: **{intent_info['description']}**\n\n"
              f"我可以帮您:\n"
              f"• 查询规则（如: YP_SYZ）\n"
              f"• 查询目录（如: 查一下阿莫西林）\n"
              f"• 检查规则冲突\n"
              f"• 分析测试覆盖率\n"
              f"• 查看规则变更影响\n\n"
              f"请输入更具体的问题，或输入「帮助」查看完整功能列表。",
        source="引导",
        intent="unknown"
    )