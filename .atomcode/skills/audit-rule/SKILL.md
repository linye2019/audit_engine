---
name: audit-rule
description: 医保智能审核规则开发辅助 - 理解 DSL 语法和规则编写规范。在编写或修改审核规则时使用。
disable-model-invocation: true
allowed-tools: Read, Write, Grep, Glob, Bash
---

## 项目规则引擎概述

audit_engine 的自定义 DSL 位于 `audit_engine/dsl/` 目录：
- `evaluator.py` — DSL 表达式求值器
- `operators.py` — 支持的运算符实现

审核流程三层架构：
1. **事前审核** (precheck) — 医生开立医嘱时实时检查，要求 <200ms
2. **事中审核** (concurrent) — 出科时全量审核，含拦截建议
3. **事后审核** (postaudit) — 结算后深度分析 + DRG

## 规则开发步骤

1. **理解领域** — 阅读 `docs/RULE_REGISTRY.md` 了解现有规则
2. **确定审核阶段** — 选择 precheck / concurrent / postaudit
3. **编写 DSL 表达式** — 参考 `tests/test_dsl_evaluator.py` 中的示例
4. **添加匹配逻辑** — 在 `audit_engine/matcher/catalog.py` 中扩展目录匹配
5. **编写测试** — 在 `tests/` 下添加对应的 `test_*` 文件
6. **验证** — 运行 `python -m pytest tests/ -x -v`

## 数据库 Schema

审核数据存储在 `medicare_engine.db` (SQLite)，建表语句在 `schema.sql`。
