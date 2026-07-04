# AI 医保智能审核智能体 — 产品说明

> **版本**: 1.1.0 · **最后更新**: 2026-07-03  
> **项目**: 医保智能审核规则引擎 (medicare-audit-engine)  
> **核心准则**: 严格输入 · 严谨输出

---

## 一、智能体简介

### 1.1 概述

AI 医保智能审核智能体是一套基于 **规则引擎 + AI 对话 + 自动闭环** 的医保审核系统。它围绕 3,510 条审核规则、4 柱 4 阶段的审核架构，提供从规则管理、审核执行、质量检查到自动修复的全链路智能化能力。

### 1.2 核心能力矩阵

| 能力层 | 名称 | 说明 |
|--------|------|------|
| 🎯 **审核执行** | MedicareAuditEngine | 四柱四阶段审核引擎，支持事前/在院/出科/事后 |
| 🧪 **测试验证** | gen-audit-tests | 从规则手册自动生成 pytest 测试用例 |
| 🔍 **质量检查** | rule-quality-checker | 9 项规则质量检查（重复、孤儿、ICD-10、字段路径等） |
| 📊 **影响分析** | impact-analysis | 规则变更前后对比，增量/修改/删除识别 |
| 🗣️ **对话交互** | audit-assistant | 自然语言解释审核结果、查询规则和目录 |
| 🔧 **自动修复** | auto-fix | 测试失败诊断 → 自动修复 → 循环验证 |
| 📈 **报告输出** | reports/ | JUnit XML + 覆盖率 + HTML 报告 + 历史日志 |

### 1.3 关键指标

| 指标 | 数值 |
|------|------|
| 活跃审核规则 | 3,510 条（4 支柱 × 4 阶段） |
| 测试用例 | 193 个（全部通过） |
| 规则质量检查项 | 9 项全覆盖 |
| 闭环循环上限 | 3 次（自动熔断） |
| 自动修复成功率 | ~90% |
| 交互通道 | 自然语言 / 命令 / API |

---

## 二、工作原理

### 2.1 审核引擎架构

```
用户请求（结算单 + 费用明细）
      │
      ▼
┌──────────────────────────────────────────────────┐
│              MedicareAuditEngine                  │
│                                                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ 目录匹配   │   │ 上下文构建 │   │ 条件评估器   │  │
│  │ Catalog   │──►│ Context  │──►│ Evaluator   │  │
│  │ Matcher   │   │ Builder  │   │ (DSL)       │  │
│  └──────────┘   └──────────┘   └──────┬───────┘  │
│                                        │          │
│  ┌─────────────────────────────────────▼────────┐ │
│  │              规则加载器                        │ │
│  │  rule_items (3,510) + drg_rules (17)         │ │
│  │  按 pillar × stage 缓存 + 版本哈希失效        │ │
│  └──────────────────────────────────────────────┘ │
│                                        │          │
│  ┌─────────────────────────────────────▼────────┐ │
│  │              结果构建器                        │ │
│  │  AuditResult → 持久化 → API 返回              │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
      │
      ▼
审核结果（违规/可疑/提示）
```

### 2.2 四柱四阶段

| 柱 | 编码 | 范围 | 规则数 |
|----|------|------|--------|
| 药品目录限制 | **YP** | 西药/中成药/中药饮片 | 1,917 |
| 服务项目合规 | **FW** | 诊疗项目收费合规 | 1,962 |
| 耗材使用合规 | **HC** | 基本物耗/特殊功能耗材 | 8 |
| 支付合规性 | **BZ** | DRG/DIP 入组准确性 | 17 |

| 阶段 | 业务名称 | 时机 |
|------|---------|------|
| `pre_check` | 事前医嘱审核 | 医生开立医嘱时 |
| `mid_check` | 在院日终审核 | 住院期间每晚 |
| `end_check` | 出科审核 | 患者出院时 |
| `post_audit` | 事后结算监管 | 结算完成后 |

### 2.3 DSL 条件表达式

规则使用 JSON 格式的 DSL 表达审核条件，支持 20 种运算符：

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "阿莫西林"},
    {"field": "claim_event.diag_codes", "op": "not_regex", "value": "E11|N18"}
  ]
}
```

---

## 三、循环机制

### 3.1 AI 自动闭环

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI 自动闭环流水线                               │
│                                                                 │
│  Step 1: 测试生成 ← RULE_BOOK.md 更新                            │
│    /gen-tests                                                    │
│         │                                                        │
│         ▼                                                        │
│  Step 2: 自动运行 + 记录 ← JUnit XML + 覆盖率                    │
│    /gen-tests --run                                              │
│         │                                                        │
│    ┌────┴────┐                                                   │
│    │ 通过 ✅  │  失败 ❌                                          │
│    └────┬────┘   │                                               │
│         │        ▼                                               │
│         │   Step 3: 结果诊断 ← 10 种失败模式分类                  │
│         │     /test-diagnose                                     │
│         │        │                                               │
│         │        ▼                                               │
│         │   Step 4: 自动修复 ← 字段名/测试数据/字段映射           │
│         │     /gen-tests --fix                                   │
│         │        │                                               │
│         │    ┌────┴────┐                                         │
│         │    │ 再次运行 │   ← 循环计数 + 1                        │
│         │    └────┬────┘                                         │
│         │    ┌────┴────┐                                         │
│         │    │ ≤3 次   │  >3 次 → 挂起人工 ⚠️                   │
│         │    └────┬────┘                                         │
│         │         ▼                                              │
│         │   Step 5: 验证通过                                     │
│         │         │                                              │
│         ▼         ▼                                              │
│  Step 6: 记录闭环结果 ← reports/test_rules_history.log           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 熔断机制

| 条件 | 行为 |
|------|------|
| 连续 3 次运行失败 | 挂起人工 |
| 修复导致手写测试失败 | 回滚 + 挂起 |
| 同一测试连续 2 次修复未通过 | 升级为高优先级 FixMe |
| 循环总耗时 > 5 分钟 | 挂起（防无限循环） |

### 3.3 置信度决策矩阵

| AI 置信度 | 行为 |
|-----------|------|
| ≥ 0.90 | 自动修复，无告警 |
| 0.70–0.89 | 自动修复，记录告警 |
| < 0.70 | 挂起人工审核 |

置信度计算公式:

```
confidence = pattern_match × 0.5 + fix_scope × 0.3 + traceback_clarity × 0.2
```

---

## 四、适配场景

### 4.1 定点医疗机构

| 场景 | 说明 | 适用阶段 |
|------|------|---------|
| 医生开立医嘱时实时审核 | 事前拦截不合理用药/检查 | pre_check |
| 住院期间每日累计审核 | 在院费用监控，超量预警 | mid_check |
| 患者出院前全量审核 | 出科终审，拦截违规计费 | end_check |
| 结算后深度分析 + DRG | 事后监管，DRG 入组校验 | post_audit |

### 4.2 医保监管部门

| 场景 | 说明 |
|------|------|
| 新批次规则入库 | 从国家两库/立项指南自动解析、校验、入库 |
| 规则质量审计 | 9 项质量检查，自动发现重复/孤儿/过期规则 |
| 审核结果分析 | 覆盖率分析、规则触发统计、异常模式检测 |
| 政策变更影响评估 | 规则变更前后对比，识别影响范围 |

### 4.3 规则运维团队

| 场景 | 说明 |
|------|------|
| 规则开发 | `/audit-rule` skill 指导 DSL 编写 |
| 规则测试 | `/gen-tests` 自动生成测试，验证规则正确性 |
| 问题诊断 | `/test-diagnose` 自动定位失败根因 |
| 自动修复 | `/gen-tests --fix` 自动修复常见问题 |

---

## 五、调用方式

### 5.1 自然语言对话

在 AtomCode 环境中直接提问：

```
"为什么这个药品被拦截了？"
"YP_SYZ 规则限哪些适应症？"
"查一下阿莫西林在不在药品目录里"
"测试为什么失败？"
"最近规则有什么变化？"
"检查规则有没有冲突？"
"测试覆盖率多少？"
```

### 5.2 命令调用

| 命令 | 功能 | 所属 Skill |
|------|------|-----------|
| `/gen-tests` | 从 RULE_BOOK.md 生成测试 | gen-audit-tests |
| `/gen-tests --run` | 生成 + 运行 + 记录结果 | gen-audit-tests |
| `/gen-tests --fix` | 生成 + 运行 + 诊断 + 自动修复 | auto-fix |
| `/gen-tests --loop` | 完整闭环（最多 3 次循环） | auto-fix |
| `/test-diagnose` | 诊断上次测试失败 | auto-fix |
| `/test-fix <name>` | 指定修复某个失败的测试 | auto-fix |
| `/test-history` | 查看历史测试结果 | gen-audit-tests |

### 5.3 命令行脚本

```bash
# 规则质量检查
python tools/audit-assistant/analysis/rule_quality_checker.py
python tools/audit-assistant/analysis/rule_quality_checker.py --pillar YP

# 规则变更影响分析
python tools/audit-assistant/analysis/impact_analysis.py --save-snapshot
python tools/audit-assistant/analysis/impact_analysis.py

# 规则覆盖率分析
python tools/audit-assistant/analysis/coverage_analysis.py
python tools/audit-assistant/analysis/coverage_analysis.py --json

# 测试失败诊断
python tools/auto-fix/diagnose.py
python tools/auto-fix/diagnose.py --json

# 自动修复 fixture 字段
python tools/auto-fix/fixers/fix_fixture_fields.py
```

### 5.4 API 调用

审核引擎提供 Python API：

```python
from audit_engine import MedicareAuditEngine
from audit_engine.models.claim import ClaimEvent, ClaimLine

# 初始化引擎
engine = MedicareAuditEngine("medicare_engine.db")

# 构造审核请求
claim = ClaimEvent(setl_id="SETL001", med_type="21", ...)
line = ClaimLine(setl_id="SETL001", list_type="11", ...)

# 执行审核
results = engine.audit_claim(claim, [line], stage="post_audit")

# 输出结果
for r in results:
    print(f"{r.rule_code}: {r.verdict} ({r.severity})")
```

### 5.5 报告查看

```bash
# 覆盖率 HTML 报告
open reports/coverage_rules/index.html

# 主动能力分析报告
open reports/active_capabilities_report.html

# 历史测试日志
cat reports/test_rules_history.log

# JUnit XML 详细结果（CI 集成）
cat reports/test_rules_results.xml
```

---

## 六、技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 审核引擎 | Python | ≥ 3.9 |
| 规则存储 | SQLite | 内置 |
| 测试框架 | pytest + coverage | 8.4+ |
| AI 对话 | AtomCode Skills | — |
| DSL 评估 | 自研表达式引擎 | 20 种运算符 |
| 报告输出 | HTML / XML / 终端 | — |

---

## 七、质量保障

### 7.1 测试覆盖

| 测试套件 | 数量 | 通过率 |
|---------|------|--------|
| 引擎核心测试 | 17 | 100% |
| 规则手册自动测试 | 49 | 100% |
| DSL 评估器测试 | 9 | 100% |
| 上下文构建测试 | 12 | 100% |
| 目录匹配测试 | 12 | 100% |
| 数据模型测试 | 11 | 100% |
| 操作符测试 | 16 | 100% |
| 数据访问测试 | 24 | 100% |
| **总计** | **193** | **100%** |

### 7.2 规则质量

| 检查项 | 状态 |
|--------|------|
| 重复规则 | ✅ 0 组真重复（已清理 377 条） |
| 孤儿目录引用 | 🟡 919 条（目录表覆盖率问题，不影响执行） |
| ICD-10 编码 | ✅ 全部有效 |
| 字段路径 | ✅ 全部支持 |
| 空 conditions | ✅ 0 条 |
| 阶段错配 | ✅ 0 条 |
| Severity 一致性 | 🟢 4 类建议优化 |
| 规则密度 | 🟢 8 类建议参数化 |
| 停用目录引用 | ✅ 0 条 |

---

> **严格输入 · 严谨输出**  
> 医保智能审核规则引擎 — AI 智能体  
> 文档路径: `docs/AI审核智能体设计方案.md`  
> 闭环设计: `docs/AI自动闭环设计方案.md`  
> 规则手册: `docs/RULE_BOOK.md`
