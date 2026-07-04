# AI 医保智能审核智能体 — 设计方案

## 一、概述

### 1.1 什么是审核智能体

在现有审核引擎（原子能力）之上封装一层 **AI 对话层**，让用户用自然语言与审核系统交互，AI 理解意图后自动调用原子能力完成任务。

```
用户自然语言 → AI 理解意图 → 调用引擎/测试/规则 → 返回解释结果
```

### 1.2 智能体三层次

```
┌─────────────────────────────────────────────────────────────────┐
│  第3层: 自主智能体                                                │
│  用户一句话 → AI 自主规划 → 多步执行 → 验证 → 报告                 │
│  例: "帮我看下为什么HC_FY在end_check没触发"                         │
│      → 查规则 → 看测试 → 诊断 → 修复 → 验证 → 解释                │
├─────────────────────────────────────────────────────────────────┤
│  第2层: 主动能力                                                   │
│  AI 主动告警、推荐、分析，不等待用户提问                             │
│  例: 规则变更后自动提醒影响范围                                      │
├─────────────────────────────────────────────────────────────────┤
│  第1层: 对话助手                                                   │
│  AI 回答问题、解释结果、查询规则，被动响应                           │
│  例: "为什么这条被拦截了？"                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、第 1 层：对话助手

### 2.1 目录结构

```
tools/audit-assistant/
├── SKILL.md                          # subagent 定义
├── intents.yaml                      # 意图映射表
└── prompts/
    ├── explain_result.txt            # 审核结果解释
    ├── query_rule.txt                # 规则查询
    ├── query_catalog.txt             # 目录查询
    └── diagnose_failure.txt          # 测试失败诊断
```

### 2.2 SKILL.md

```markdown
---
name: audit-assistant
description: AI 医保审核助手 — 自然语言交互，解释审核结果、查询规则、诊断问题
allowed-tools: Read, Bash, Grep, Glob
user-invocable: true
disable-model-invocation: false
---

# audit-assistant

## 能力

### 1. 解释审核结果

用户: "为什么这个药品被拦截了？"
→ 查询审核结果 → 匹配对应规则 → 用自然语言解释

### 2. 查询规则

用户: "YP_SYZ 规则限哪些适应症？"
→ 从 rule_items 表或 RULE_BOOK.md 查询

### 3. 查询目录

用户: "阿莫西林在不在药品目录里？"
→ 从 YPML 表查询

### 4. 诊断测试失败

用户: "为什么 test_rules_from_rulebook 跑不过？"
→ 解析 JUnit XML → 分类失败 → 给出原因和建议
```

### 2.3 意图映射表

| 用户问题模式 | 意图 | 执行动作 | 数据源 |
|------------|------|---------|--------|
| "为什么被拦截/拒绝/警告" | `explain_audit` | 查询审核结果 → 匹配规则 → 翻译 | `audit_result` 表 |
| "XX 规则是什么/限什么" | `query_rule` | 按 rule_code 查规则 | `rule_items` 表 / `RULE_BOOK.md` |
| "XX 在不在目录" | `query_catalog` | 按名称查目录 | `YPML` / `FWXM` / `HCML` 表 |
| "测试为什么失败/跑不过" | `diagnose_test` | 解析 JUnit XML → 分类 | `reports/test_rules_results.xml` |
| "帮我改/修复/修正" | `suggest_fix` | 诊断 + 生成修改建议 | 同上 + 模型定义 |
| "YP/HC/FW 有哪些规则" | `list_rules` | 按 pillar 查询 | `rule_items` 表 |
| "pre_check 有哪些规则" | `list_stage_rules` | 按 stage 查询 | `rule_items` 表 |

### 2.4 关键 Prompt 设计

#### 审核结果解释 prompt

```
你是一个医保审核专家助手。用户提交了一份审核结果，请用自然语言解释。

审核结果:
- 药品: {med_list_name}
- 拦截规则: {rule_code} ({rule_category})
- 规则描述: {rule_text}
- 匹配事实: {matched_facts}

解释要点:
1. 什么被拦截了（药品/项目）
2. 为什么被拦截（规则原因）
3. 触发条件是什么（匹配到的具体事实）
4. 如果需要申诉，建议补充什么材料

语言: 简洁易懂，避免技术术语
```

#### 规则查询 prompt

```
你是医保规则知识库。用户查询规则 {rule_code}。

规则信息（来自 rule_items）:
{rule_data}

规则手册描述（来自 RULE_BOOK.md）:
{rulebook_context}

请用自然语言回答:
1. 这条规则属于哪个分类（pillar）
2. 在哪个阶段生效（stage）
3. 触发条件是什么
4. 严重级别
```

---

## 三、第 2 层：主动能力

### 3.1 规则变更影响分析

当 `RULE_BOOK.md` 或 `rule_items` 变更时，AI 自动执行:

```bash
# 1. 运行测试
/gen-tests --run

# 2. 对比历史
cat reports/test_rules_history.log | tail -5

# 3. 分析影响范围
python -c "
import json, sqlite3
# 对比新旧 rules，识别新增/修改/删除的规则
# 输出影响报告
"
```

**输出示例**:
```
📢 规则变更提醒

检测到 RULE_BOOK.md 更新:
  ➕ 新增 3 条规则: YP_NEW01, YP_NEW02, HC_NEW01
  ✏️ 修改 2 条规则: FW_XMHC (stage: end_check → pre_check)
  ❌ 删除 1 条规则: HC_OLD01

测试结果: 49 passed / 0 failed
覆盖率: 53% (与上次持平)
```

### 3.2 规则冲突检测

```python
def detect_rule_conflicts(pillar: str) -> list[dict]:
    """检测同一 pillar 内规则的逻辑冲突"""
    rules = load_rules(pillar)
    conflicts = []
    for i, a in enumerate(rules):
        for b in rules[i+1:]:
            if is_mutually_exclusive(a["conditions"], b["conditions"]):
                conflicts.append({
                    "rule_a": a["rule_code"],
                    "rule_b": b["rule_code"],
                    "type": "mutual_exclusion",
                    "fields": find_conflicting_fields(a, b)
                })
    return conflicts
```

### 3.3 规则覆盖率分析

```python
def coverage_analysis(engine) -> dict:
    """分析哪些规则从未被测试覆盖"""
    all_rules = engine.repo.load_rules()
    tested_rules = extract_tested_rules("tests/test_rules_from_rulebook.py")
    return {
        "total": len(all_rules),
        "covered": len(tested_rules),
        "uncovered": [r for r in all_rules if r["rule_code"] not in tested_rules],
        "coverage_pct": len(tested_rules) / len(all_rules) * 100
    }
```

---

## 四、第 3 层：自主智能体

### 4.1 多步自主规划

用户一句指令，AI 自动分解为多步执行:

```
用户: "帮我看下为什么 HC_FY 在 end_check 阶段没触发"
                                 │
                                 ▼
  AI 自主规划:
  ┌─────────────────────────────────────────────────────┐
  │ Step 1: 查询规则 HC_FY 的定义                        │
  │   → rule_items: pillar=HC, stage=end_check          │
  │   → conditions: cnt>1 且 名称含"一次性"             │
  │                                                     │
  │ Step 2: 查看测试中 HC_FY 的测试数据                  │
  │   → test_rules_from_rulebook.py:                    │
  │     list_type=31, med_list_name=一次性输液器, cnt=2 │
  │                                                     │
  │ Step 3: 手动运行单条测试                             │
  │   → pytest -k hc_fy -v                              │
  │                                                     │
  │ Step 4: 诊断失败原因                                 │
  │   → 测试用例用的是 sample_claim, med_type=21 (住院)  │
  │   → 但 HC_FY 在 end_check 阶段                      │
  │   → BZ 规则只在 mid_check/end_check/post_audit 生效  │
  │   → HC_FY 是行级规则，不受此限制                     │
  │   → 真正原因: 测试数据中 cnt=1 但条件要求 cnt>1     │
  │                                                     │
  │ Step 5: 修复测试数据                                 │
  │   → 将 cnt 从 1 改为 2                              │
  │                                                     │
  │ Step 6: 运行验证                                    │
  │   → pytest -k hc_fy -v → PASSED                     │
  │                                                     │
  │ Step 7: 报告                                        │
  │   → "已修复。原因是测试数据中 cnt=1 不满足 cnt>1 条件" │
  └─────────────────────────────────────────────────────┘
```

### 4.2 与现有系统的集成

```
第 3 层 自主智能体
    │
    ├── → 调用 第 2 层 主动能力（规则分析/冲突检测/覆盖率）
    │       │
    │       └── → 调用 第 1 层 对话助手（解释结果）
    │               │
    │               └── → 调用 原子能力
    │                       ├── audit_engine（审核执行）
    │                       ├── gen-tests（测试生成）
    │                       ├── pytest（测试运行）
    │                       └── reports/（结果记录）
    │
    └── → 集成 AI自动闭环设计方案.md
            └── 失败诊断 + 自动修复 + 循环控制
```

### 4.3 自主规划 Prompt 模板

```
你是一个医保审核智能体。用户的问题是: {user_query}

可用工具:
1. /gen-tests --run        - 生成并运行测试
2. /test-diagnose          - 诊断测试失败
3. /gen-tests --fix        - 自动修复测试
4. /gen-tests --loop       - 完整闭环
5. sqlite3 数据库查询       - 直接查 rule_items/YPML 等表
6. grep/glob 文件搜索       - 搜索代码和文档

请分析用户问题，分解为 2-5 个步骤，逐步执行。
每步执行后检查结果，根据结果决定下一步。
最多尝试 3 次修复，之后挂起人工。

当前项目状态:
- 规则数: 3887 条 (+ 17 DRG)
- 测试数: 193 个
- 已启用技能: gen-audit-tests, audit-assistant
```

---

## 五、目录结构总览

```
tools/
├── gen-audit-tests/                    # 已有: 测试生成技能
│   ├── SKILL.md
│   └── test_rules_from_rulebook.py     # 模板
│
├── audit-assistant/                    # 🆕 新增: 审核助手
│   ├── SKILL.md
│   ├── intents.yaml
│   └── prompts/
│       ├── explain_result.txt
│       ├── query_rule.txt
│       ├── query_catalog.txt
│       └── diagnose_failure.txt
│
└── auto-fix/                           # 🆕 新增: 自动修复
    ├── SKILL.md                        # 引用 AI自动闭环设计方案.md
    ├── diagnose.py
    └── fixers/
        ├── fix_fixture_fields.py
        ├── fix_test_data.py
        └── fix_field_mapping.py

.atomcode/skills/
├── gen-audit-tests → ../../tools/gen-audit-tests/
├── audit-assistant → ../../tools/audit-assistant/    # 🆕
└── auto-fix → ../../tools/auto-fix/                  # 🆕
```

---

## 六、实施计划

### 第 1 步：对话助手（audit-assistant）

创建 `tools/audit-assistant/`，实现 4 个核心对话能力：
- 解释审核结果
- 查询规则
- 查询目录
- 诊断测试失败

**验收**: 用户说"为什么被拦截"可得到自然语言解释

### 第 2 步：主动能力

在 audit-assistant 中增加：
- 规则变更影响分析（对比历史）
- 基础冲突检测
- 覆盖率报告

**验收**: RULE_BOOK.md 变更后 AI 自动输出影响报告

### 第 3 步：自主智能体

创建 `tools/auto-fix/` 并集成 `AI自动闭环设计方案.md`：
- 多步自主规划（Step 1-7 流程）
- 与 gen-tests 和 audit-assistant 联动

**验收**: 用户说"HC_FY 在 end_check 没触发"→ AI 自动诊断修复验证报告

---

## 七、与现有文档的关系

| 现有文档 | 与本方案的关系 |
|---------|--------------|
| `RULE_BOOK.md` | 知识源，注入所有对话 prompt |
| `AI自动闭环设计方案.md` | 第 3 层的技术实现基础 |
| `ai_pipeline_design.md` | 远期补充（规则生产端自动化） |
| `gen-tests skill` | 第 3 层的测试生成工具 |
| `test_rules_from_rulebook.py` | 第 3 层的验证对象 |
