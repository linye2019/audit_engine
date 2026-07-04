# 医保智能审核引擎 — AI 自动闭环设计方案（测试驱动版）

## 一、概述

### 1.1 什么是 AI 自动闭环

当规则新增或修改后，AI 自动完成"生成测试 → 运行测试 → 诊断失败 → 修复测试数据/字段映射 → 验证通过"的完整循环，无需人工介入。

> **关键约束**: AI 自动修复限于 **测试数据和字段映射层面**，引擎核心逻辑（engine.py、evaluator.py）发现问题则挂起人工。

### 1.2 闭环流程总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI 自动闭环流水线                               │
│                                                                 │
│  规则变更触发                                                      │
│    (RULE_BOOK.md / rule_items 更新)                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Step 1      │    │  Step 2      │    │  Step 3      │       │
│  │  测试生成     │──►│  自动运行     │──►│  结果诊断     │       │
│  │  /gen-tests  │    │  --run       │    │  analyse     │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬──────┘       │
│         │                  │                   │               │
│         ▼                  ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Step 4: AI 自动修复                                   │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │      │
│  │  │ 修复测试  │  │ 修复引擎  │  │ 补数据    │            │      │
│  │  │ 数据不对  │  │ 逻辑不对  │  │ 缺字段    │            │      │
│  │  └──────────┘  └──────────┘  └──────────┘            │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│                         ▼                                      │
│  ┌──────────────┐    ┌──────────────┐                         │
│  │  Step 5      │    │  Step 6      │                         │
│  │  再次运行     │──►│  记录结果     │──►  ✅ 闭环完成            │
│  │  --run       │    │  history     │                         │
│  └──────────────┘    └──────────────┘                         │
│                         │                                      │
│                         ▼                                      │
│                     ⚠️ 失败 (回到 Step 3)                      │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 与现有资产的关系

```
┌──────────────────────────────────────────────────────────────────┐
│  AI 自动闭环（新增）                                              │
│  docs/AI自动闭环设计方案.md                                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  gen-tests skill（已有）                                    │    │
│  │  tools/gen-audit-tests/SKILL.md                           │    │
│  │  ├── /gen-tests       → 生成测试                           │    │
│  │  ├── /gen-tests --run → 生成 + 运行 + 记录                 │    │
│  │  └── /test-history    → 查看历史结果                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                       │
│                           ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  测试框架（已有 193 个测试）                                │    │
│  │  tests/                                                   │    │
│  │  ├── test_engine.py              (17 个通过)              │    │
│  │  ├── test_rules_from_rulebook.py (49 个通过 — 自动生成)    │    │
│  │  ├── test_dsl_evaluator.py       (9 个通过)               │    │
│  │  └── ...                         (共 193 个通过)          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                       │
│                           ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  结果记录（新增）                                            │    │
│  │  reports/                                                 │    │
│  │  ├── test_rules_results.xml    (JUnit XML)                │    │
│  │  ├── coverage_rules/index.html (覆盖率)                   │    │
│  │  └── test_rules_history.log    (历史摘要)                  │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、六步闭环详解

### Step 1: 测试生成（已有）

由 `gen-tests` skill 完成:

```bash
/gen-tests              # 从 RULE_BOOK.md 生成测试
/gen-tests --update     # 增量更新
/gen-tests YP           # 只生成药品规则测试
```

**触发条件**:
- `RULE_BOOK.md` 被修改
- `tools/gen-audit-tests/SKILL.md` 中的测试模板更新
- 用户主动调用 `/gen-tests`

### Step 2: 自动运行并记录（已有）

```bash
# 每次运行自动生成 JUnit XML（不依赖用户指定）
/gen-tests --run
```

等价于:

```bash
python -m pytest tests/test_rules_from_rulebook.py \
  --junitxml=reports/test_rules_results.xml \
  --cov=audit_engine --cov-report=html:reports/coverage_rules \
  --cov-report=term 2>&1 | tee -a reports/test_rules_history.log
```

> 一次 pytest 调用同时完成: 运行、JUnit XML 输出、覆盖率报告、历史记录追加。

### Step 3: 结果诊断（新增）

当测试失败时，AI 自动执行以下诊断流程:

> **注意**: JUnit XML 由 Step 2 自动生成。若用户单独调用诊断时文件不存在，会自动触发一次 `/gen-tests --run` 先生成结果再诊断。

```python
def diagnose_failures(junit_xml_path: str) -> dict:
    """解析 JUnit XML，对每个 failure 诊断根因"""
    # 1. 读取失败测试列表
    # 2. 对每个失败: 提取 traceback、expected vs actual、上下文
    # 3. 分类诊断:
    #    - "测试数据错误" — 测试构造的 claim/line 与模型不匹配
    #    - "引擎逻辑错误" — audit_claim 未按预期触发规则
    #    - "DSL解析错误" — conditions JSON 格式/字段路径不对
    #    - "数据库缺失" — 找不到 rule_items 表或数据
    #    - "字段缺失" — claim_event 或 claim_line 缺少字段
    # 4. 生成修复建议和置信度
    pass
```

**诊断分类矩阵**:

| 失败模式 | 典型错误信息 | 根因 | 修复策略 |
|---------|-------------|------|---------|
| `fixture_error` | `TypeError: __init__() got an unexpected keyword argument` | ClaimEvent/ClaimLine 字段名与模型不匹配 | 修正测试数据字段名 |
| `assertion_false_positive` | `AssertionError: 规则不应触发但触发了` | 不匹配测试数据不符合预期 | 检查规则 conditions 或修正不匹配数据 |
| `assertion_false_negative` | `AssertionError: 规则未触发` | 匹配测试数据未触发规则 | 检查引擎/规则逻辑 |
| `db_error` | `sqlite3.OperationalError: no such table` | 数据库未初始化 | 确保 init_db fixture 正确 |
| `dsl_syntax` | `json.JSONDecodeError` | conditions JSON 语法错误 | 修正 DSL 格式 |
| `field_missing` | `KeyError` 或 `AttributeError` | 上下文字段缺失 | 检查字段路径映射 |
| `timeout` | `TimeoutError` | 规则执行超时 | 检查规则性能 |

### Step 4: AI 自动修复（新增）

根据诊断结果自动执行修复。**AI 自动修复仅限于测试数据和字段映射层面，引擎核心逻辑问题直接挂起人工。**

```python
def auto_fix(diagnosis: dict) -> list[dict]:
    """根据诊断结果自动执行修复"""
    fixes = []
    for failure in diagnosis["failures"]:
        if failure["mode"] == "fixture_error":
            # 修复测试数据字段名
            fix = fix_fixture_fields(failure)
        elif failure["mode"] == "assertion_false_positive":
            # 修正不匹配测试数据
            fix = fix_no_match_data(failure)
        elif failure["mode"] == "assertion_false_negative":
            # 检查引擎逻辑
            fix = fix_engine_logic(failure)
        elif failure["mode"] == "field_missing":
            # 补充上下文字段
            fix = add_context_field(failure)
        fixes.append(fix)
    return fixes
```

**修复策略详情**:

| 根因 | AI 操作 | 涉及文件 | 自动修复？ |
|------|---------|---------|-----------|
| 测试数据字段错 | 读取 ClaimEvent/ClaimLine 模型，修正字段名 | `test_rules_from_rulebook.py` | ✅ 自动 |
| 不匹配数据不够"干净" | 调整不匹配数据的值使其明确不触发 | `test_rules_from_rulebook.py` | ✅ 自动 |
| 匹配数据不够"匹配" | 调整匹配数据的值使其符合规则条件 | `test_rules_from_rulebook.py` | ✅ 自动 |
| 字段映射缺失 | 在 context_builder.py 中补充字段映射 | `audit_engine/core/context.py` | ✅ 自动 |
| DSL 语法错误 | 修正 conditions JSON | `test_rules_from_rulebook.py` 或规则数据 | ✅ 自动 |
| 引擎逻辑 bug | 分析 engine.py / evaluator.py 逻辑 | 核心引擎文件 | ❌ 挂起人工 |

### Step 5: 再次运行（复用已有）

```bash
/gen-tests --run
```

或:

```bash
python -m pytest tests/test_rules_from_rulebook.py \
  --junitxml=reports/test_rules_results.xml
```

### Step 6: 结果记录与告警（新增）

```bash
# 记录本次闭环
echo "=== $(date) [CLOSED] ===" >> reports/test_rules_history.log
python -m pytest tests/test_rules_from_rulebook.py --tb=no -q \
  | head -1 >> reports/test_rules_history.log

# 记录修复动作
echo "修复: xxx (3 files changed)" >> reports/test_rules_history.log

# 若仍然失败 → 回到 Step 3（自动循环）
# 最多循环 3 次 → 第 4 次失败 → 挂起人工
```

---

## 三、循环次数与熔断机制

### 3.1 最大循环次数

```
第1次: 生成测试 + 运行 → 失败 → 诊断 + 修复（测试/字段层面）
第2次: 再次运行 → 失败 → 诊断 + 修复（另一种根因）
第3次: 再次运行 → 失败 → 挂起人工

✅ 任意一次成功 → 记录 + 结束
⚠️ 连续 3 次运行失败 → 挂起，输出诊断报告等待人工

熔断规则: 最多尝试 2 次修复（即最多执行 3 次 pytest），之后必须挂起。

### 3.2 熔断条件

| 条件 | 行为 |
|------|------|
| 连续 3 次运行失败 | 挂起人工 |
| 修复导致手写测试（`test_engine.py` 等）失败 | 回滚 + 挂起 |
| 同一测试连续 2 次修复仍未通过 | 升级为高优先级 FixMe |
| 循环总耗时 > 5 分钟 | 挂起（防止无限循环） |

### 3.3 置信度计算

AI 修复置信度由以下因素加权计算:

```
confidence = pattern_match × 0.5 + fix_scope × 0.3 + traceback_clarity × 0.2
```

| 因素 | 权重 | 说明 |
|------|------|------|
| `pattern_match` | 50% | traceback 与已知失败模式的匹配度（关键词命中率） |
| `fix_scope` | 30% | 修复范围: 测试文件=1.0, 字段映射=0.7, 引擎逻辑=0（不自动修复） |
| `traceback_clarity` | 20% | 错误信息中字段名/行号/类型信息的完整度 |

**行为矩阵**:

| AI 置信度 | 行为 |
|-----------|------|
| >= 0.90 | 自动修复，无告警 |
| 0.70-0.89 | 自动修复，记录告警 |
| < 0.70 | 挂起人工审核 |

---

## 四、AI 闭环指令集

在现有 `gen-tests` skill 基础上扩展，新增以下命令:

| 命令 | 功能 | 已有/新增 |
|------|------|----------|
| `/gen-tests` | 生成测试文件 | ✅ 已有 |
| `/gen-tests --run` | 生成 + 运行 + 记录 | ✅ 已有 |
| `/gen-tests --fix` | 生成 + 运行 + 诊断 + 自动修复 | 🆕 新增 |
| `/gen-tests --loop` | 完整闭环（最多 3 次循环） | 🆕 新增 |
| `/test-diagnose` | 仅诊断上次失败 | 🆕 新增 |
| `/test-history` | 查看历史 | ✅ 已有 |
| `/test-fix <test_name>` | 指定修复某个失败的测试 | 🆕 新增 |
| `/gen-tests --resume` | 人工修复后继续闭环（从 Step 5 开始） | 🆕 新增 |

---

## 五、闭环成功率预估

基于当前项目状况:

| 失败模式 | 预估占比 | AI 修复成功率 | 说明 |
|---------|---------|-------------|------|
| `fixture_error` | 50% | 100% | 字段映射表已内置，确定性修复 |
| `assertion_false_negative` | 25% | 80% | 需理解规则逻辑，中高置信度 |
| `assertion_false_positive` | 15% | 90% | 不匹配数据调整，确定性高 |
| `field_missing` | 5% | 70% | 需补充字段映射 |
| `dsl_syntax` | 3% | 100% | JSON 格式校验，确定性 |
| `db_error` | 2% | 100% | fixture 问题，确定性 |

**综合预期**: 约 **90% 的测试失败可自动修复**，剩余 10% 需人工介入。

---

## 六、与其他系统的关系

### 6.1 与 ai_pipeline_design.md 的关系

| | ai_pipeline_design.md（规则生产管道） | 本方案（测试驱动闭环） |
|--|-----------------------------------|---------------------|
| **目标** | 新规则采集 → 解析 → 校验 → 入库 | 规则变更后测试生成 → 运行 → 修复 → 验证 |
| **触发** | 新批次规则发布（nhsa.gov.cn） | RULE_BOOK.md 更新 / 用户调用 |
| **AI 能力** | ICD-10 映射、语义校验、归类 | 失败诊断、自动修复、字段映射修正 |
| **人工环节** | CP1-CP4 四个 Checkpoint | 自动循环 3 次后挂起人工 |
| **输出** | 新入库的 rule_items | 通过的测试 + 修复报告 |

### 6.2 闭环串联（远期目标）

当前阶段本方案 **独立运行**，不依赖 `ai_pipeline_design.md` 的完成状态。串联作为远期目标:

```
ai_pipeline_design.md（尚未完成）
  └── 新规则入库 → RULE_BOOK.md 更新
        └── 触发 AI 自动闭环（远期目标，当前手动触发）

---

## 七、实施计划

### 第一阶段：诊断能力

在 `gen-tests` skill 中增加诊断命令:

```python
# tools/gen-audit-tests/diagnose.py（新增）
class TestFailureDiagnoser:
    """诊断测试失败根因"""
    def parse_junit_xml(self, path): ...
    def classify_failure(self, failure): ...
    def suggest_fix(self, failure): ...
```

```bash
/test-diagnose  # 诊断上次失败
```

**验收标准**: 至少积累 5 种失败模式的分类用例，分类准确率 > 80%。

### 第二阶段：自动修复

实现 `--fix` 模式:

| 修复类型 | 自动操作 | 置信度 |
|---------|---------|--------|
| 字段名错误 | 查模型定义自动修正 | 高 |
| 测试数据不对 | 根据 rule_code 的 conditions 重新构造 | 中 |
| 不匹配数据不够干净 | 确保所有字段取"不可能"值 | 高 |

```bash
/gen-tests --fix    # 生成 + 运行 + 自动修复
```

**验收标准**: fixture_error 和 dsl_syntax 修复成功率 100%，assertion 类 > 80%。

### 第三阶段：完整闭环

实现 `--loop` 模式，包含循环控制和熔断机制:

```bash
/gen-tests --loop   # 完整闭环
```

**验收标准**: 连续 10 次模拟失败中，至少 8 次自动修复成功（不触发挂起）。

---

## 八、风险与应对

| 风险 | 应对 |
|------|------|
| AI 修复引入新 bug | 自动修复后再跑全部 193 个测试，回归检测 |
| 循环无法终止 | 最大 3 次 + 5 分钟熔断 |
| 修复覆盖手写测试 | 只修改 `test_rules_from_rulebook.py`（自动生成），不碰 `test_engine.py` 等手写测试 |
| 字段映射表过时 | SKILL.md 中维护映射表，AI 更新时同步检查 |
