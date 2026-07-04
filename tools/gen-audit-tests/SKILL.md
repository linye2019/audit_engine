---
name: gen-audit-tests
description: 从 RULE_BOOK.md 自动生成/更新 pytest 测试用例，覆盖所有规则条目。RULE_BOOK.md 更新后建议运行。
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, Edit
---

# gen-audit-tests — 规则手册测试自动生成

## 用途

解析 `docs/RULE_BOOK.md`，为每条规则自动生成对应的 `pytest` 测试用例，写入 `tests/test_rules_from_rulebook.py`。

## 执行流程

### 步骤 1: 读取规则手册

读取 `docs/RULE_BOOK.md`，识别所有规则条目。每条规则应包含:

- `rule_code` / 规则编号（如 `YP_001`）
- `pillar`（YP / FW / HC / BZ）
- `stage`（pre_check / mid_check / end_check / post_audit）
- `conditions`（DSL 条件 JSON）
- `severity`（violation / warning / info / suspicious）
- `description`（中文描述）

### 步骤 2: 解析 DSL conditions 推断测试数据

根据 `conditions` 中的字段路径，自动构造匹配/不匹配的上下文数据。

**字段路径 ↔ 模型字段映射:**

| DSL 字段路径 | 模型字段 | 测试数据类型 |
|-------------|---------|------------|
| `claim_event.age` | `brdy`（通过 property 计算） | 整数 |
| `claim_event.gend` | `gend`（"1"=男 "2"=女） | 字符串 |
| `claim_event.med_type` | `med_type`（"11"/"21"） | 字符串 |
| `claim_event.medfee_sumamt` | `medfee_sumamt` | 浮点数 |
| `claim_event.inhosp_days` | `inhosp_days` | 整数 |
| `claim_event.dept` | `dept` | 字符串 |
| `claim_event.hosp_lv` | `hosp_lv`（"1"~"11"） | 字符串 |
| `claim_line.list_type` | `list_type`（"11"/"12"/"13"/"21"/"31"） | 字符串 |
| `claim_line.med_list_name` | `med_list_name` | 字符串 |
| `claim_line.med_list_codg` | `med_list_codg` | 字符串 |
| `claim_line.cnt` | `cnt` | 浮点数 |
| `claim_line.pric` | `pric` | 浮点数 |
| `claim_line.det_amt` | `det_amt` | 浮点数 |
| `claim_line.bilg_dept_name` | `bilg_dept_name` | 字符串 |
| `claim_line.exec_dept_name` | `exec_dept_name` | 字符串 |
| `claim_line.bilg_drord_dr_name` | `bilg_drord_dr_name` | 字符串 |
| `claim_line.orders_dr_name` | `orders_dr_name` | 字符串 |
| `staff.staff_qualification` | 外部资质表 | 字符串 |
| `staff.department` | 外部资质表 | 字符串 |

### 步骤 3: 生成测试文件

生成 `tests/test_rules_from_rulebook.py`，使用 `@pytest.mark.parametrize` 实现数据驱动:

- 每条规则一个参数化条目
- 至少包含 **匹配场景**（应触发规则）和 **不匹配场景**（不应触发规则）
- 使用 `tests/conftest.py` 中已有的 `sample_claim`、`sample_drug_line` 等 fixture

### 步骤 4: 运行并记录结果

```bash
cd $PROJECT_ROOT

# 运行测试 + 生成 JUnit XML 报告
python -m pytest tests/test_rules_from_rulebook.py -v \
  --junitxml=reports/test_rules_results.xml \
  --cov=audit_engine --cov-report=html:reports/coverage_rules \
  --cov-report=term

# 记录历史摘要
echo "=== $(date '+%Y-%m-%d %H:%M') ===" >> reports/test_rules_history.log
python -m pytest tests/test_rules_from_rulebook.py --tb=no -q \
  | tail -3 >> reports/test_rules_history.log
```

### 步骤 5: 查看历史

```bash
cat reports/test_rules_history.log
```

## 命令

| 命令 | 功能 |
|------|------|
| `/gen-tests` | 生成测试文件 |
| `/gen-tests --run` | 生成 + 运行 + 记录结果 |
| `/gen-tests --fix` | 生成 + 运行 + 诊断 + 自动修复 |
| `/gen-tests --loop` | 完整闭环（最多 3 次循环） |
| `/gen-tests --update` | 增量更新（不覆盖已有） |
| `/test-diagnose` | 诊断上次测试失败 |
| `/test-fix <name>` | 指定修复某个失败的测试 |
| `/test-history` | 查看历史测试结果 |

## 报告输出

运行后生成:

| 文件 | 说明 |
|------|------|
| `reports/test_rules_results.xml` | JUnit XML 格式详细结果（CI 可读） |
| `reports/coverage_rules/index.html` | 规则测试覆盖率报告 |

## 输出格式

```
tests/test_rules_from_rulebook.py
├── test_rule_<pillar>_<rule_code>  # 匹配场景
│   ├── 设置匹配数据
│   ├── 执行 audit_claim
│   └── 断言结果 severity/verdict
├── test_rule_<pillar>_<rule_code>_no_match  # 不匹配场景
│   ├── 设置不匹配数据
│   ├── 执行 audit_claim
│   └── 断言结果为空
└── test_rules_summary  # 汇总统计
```

## 注意事项

- **不要覆盖** 已有的 `tests/test_engine.py` 等手写测试
- 生成的测试仅依赖 `conftest.py` 中的 fixture 和 `RULE_BOOK.md`
- 若模型字段变更，需同步更新上面的字段映射表
