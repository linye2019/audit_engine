---
name: auto-fix
description: 自动诊断并修复测试失败 — 检测 fixture 字段错误、测试数据不匹配、字段映射缺失
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
user-invocable: true
disable-model-invocation: false
---

# auto-fix — 测试自动修复

## 能力

### 诊断测试失败

```bash
/test-diagnose
```
→ 读取 `reports/test_rules_results.xml`，对每个 failure 分类诊断根因

### 自动修复

```bash
/gen-tests --fix
```
→ 生成测试 → 运行 → 诊断 → 自动修复测试数据/字段映射 → 再次运行 → 验证通过

### 完整闭环

```bash
/gen-tests --loop
```
→ 最多 3 次循环：失败→诊断→修复→运行，成功后记录

### 指定修复

```bash
/test-fix <test_name>
```
→ 只修复指定的测试用例

### 人工修复后继续

```bash
/gen-tests --resume
```
→ 从 Step 5（再次运行）继续闭环

## 修复范围

| 修复类型 | 置信度 | 自动执行？ |
|---------|--------|-----------|
| fixture 字段名错误 | 高 | ✅ 自动 |
| 测试数据不匹配 | 高 | ✅ 自动 |
| 字段映射缺失 | 中 | ✅ 自动（记录告警） |
| DSL 语法错误 | 高 | ✅ 自动 |
| 引擎逻辑错误 | 中 | ❌ 挂起人工 |

## 项目知识

- 测试文件: tests/test_rules_from_rulebook.py
- JUnit 报告: reports/test_rules_results.xml
- 历史记录: reports/test_rules_history.log
- 诊断脚本: tools/auto-fix/diagnose.py
- 修复脚本: tools/auto-fix/fixers/
