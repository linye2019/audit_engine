---
name: audit-assistant
description: AI 医保审核助手 — 自然语言交互、规则变更影响分析、冲突检测、覆盖率分析
allowed-tools: Read, Bash, Grep, Glob, Edit
user-invocable: true
disable-model-invocation: false
---

# audit-assistant — AI 医保审核助手

## 能力

### 1. 解释审核结果

用户: "为什么这个药品被拦截了？"
→ 查询审核结果 → 匹配对应规则 → 用自然语言解释

**数据源**: `audit_result` 表、`rule_items` 表、`RULE_BOOK.md`

### 2. 查询规则

用户: "YP_SYZ 规则限哪些适应症？"
→ 从 `rule_items` 表或 `RULE_BOOK.md` 查询规则详情

**数据源**: `rule_items` 表、`RULE_BOOK.md`、`docs/RULE_BOOK.md`

### 3. 查询目录

用户: "阿莫西林在不在药品目录里？"
→ 从 `YPML` 表查询药品目录

**数据源**: `YPML` 表、`FWXM` 表、`HCML` 表

### 4. 诊断测试失败

用户: "为什么 test_rules_from_rulebook 跑不过？"
→ 解析 JUnit XML → 分类失败 → 给出原因和建议

**数据源**: `reports/test_rules_results.xml`、`test_rules_history.log`

### 5. 规则变更影响分析 🆕

用户: "最近规则有什么变化？"
→ 对比当前规则与历史快照，输出新增/修改/删除

```bash
# 保存基线快照
python tools/audit-assistant/analysis/impact_analysis.py --save-snapshot

# 对比变更
python tools/audit-assistant/analysis/impact_analysis.py
```

### 6. 规则冲突检测 🆕

用户: "检查规则有没有冲突？"
→ 检测同一 pillar 内的性别互斥、阶段不一致、conditions 重复

```bash
# 全部 pillar
python tools/audit-assistant/analysis/conflict_detector.py

# 指定 pillar
python tools/audit-assistant/analysis/conflict_detector.py --pillar YP
```

### 7. 规则覆盖率分析 🆕

用户: "规则测试覆盖了多少？"
→ 分析哪些规则有测试覆盖，哪些没有

```bash
# 总览
python tools/audit-assistant/analysis/coverage_analysis.py

# JSON 格式（可集成）
python tools/audit-assistant/analysis/coverage_analysis.py --json
```

## 使用方式

```bash
# 对话查询
"为什么XXX被拦截了？"
"YP_SYZ 是什么规则？"
"查一下阿莫西林"
"测试为什么失败？"

# 主动分析
"最近规则有什么变化？"     # → 运行 impact_analysis.py
"检查规则有没有冲突？"      # → 运行 conflict_detector.py
"测试覆盖率多少？"          # → 运行 coverage_analysis.py
```

## 项目知识

- 项目路径: /Users/linye/atomcode/audit_engine
- 数据库: medicare_engine.db (SQLite, ~45MB)
- 规则总数: 3887 条 rule_items + 17 条 drg_rules
- 测试总数: 193 个
- 当前测试覆盖率: 17.4%（675/3887 条规则）
- 已知冲突: 10 个（含 378 条 conditions 完全相同）
- 四支柱: YP(药品) / HC(耗材) / FW(服务项目) / BZ(病种)
- 四阶段: pre_check / mid_check / end_check / post_audit
