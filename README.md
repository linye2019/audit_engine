# 医保智能审核引擎 (Medicare Audit Engine)

三阶段医保审核系统：事前（pre_check）、事中（end_check）、事后（post_audit），支持自定义 DSL 规则引擎。

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 初始化数据库
python -m audit_engine.cli medicare_engine.db --init

# 启动 API 服务
uvicorn api_server:app --reload

# 运行测试
python -m pytest tests/ -v
```

## 项目结构

```
audit_engine/
├── api_server.py                 # RESTful API 服务
├── audit_engine/
│   ├── core/
│   │   ├── engine.py             # 审核引擎主流程
│   │   ├── context.py            # 审核上下文构建
│   │   └── reasoning.py          # DRG 推理
│   ├── dsl/
│   │   ├── evaluator.py          # 条件求值器
│   │   └── operators.py          # DSL 运算符
│   ├── matcher/
│   │   └── catalog.py            # 医保目录匹配
│   ├── models/
│   │   ├── claim.py              # 结算/费用明细模型
│   │   └── result.py             # 审核结果模型
│   └── repo/
│       └── sqlite_repo.py        # 数据仓库
├── schema.sql                    # 数据库建表脚本
├── tests/                        # 测试套件
└── pyproject.toml                # 项目配置
```

## 三阶段审核

| 阶段 | API | SLA | 说明 |
|------|-----|-----|------|
| 事前 | `POST /api/v1/audit/precheck` | <200ms | 医生开立医嘱时实时检查 |
| 事中 | `POST /api/v1/audit/end_check` | <2s | 出科时全量审核 |
| 事后 | `POST /api/v1/audit/postaudit` | <5s | 结算后深度分析+DRG |

## 规则 DSL

DSL 支持 18 种运算符和 AND/OR/NOT 逻辑组合：

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_event.gend", "op": "eq", "value": "2"},
    {"field": "claim_event.age", "op": "gte", "value": 18},
    {"field": "claim_line.med_list_name", "op": "contains", "value": "XX药"}
  ]
}
```
