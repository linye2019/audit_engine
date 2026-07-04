# audit_engine.py 规则引擎代码工程化改造计划

## 一、现状分析

### 1.1 代码规模
- 当前文件行数：约 1,300 行
- 单文件包含所有功能，缺乏模块化拆分

### 1.2 职责混同问题
| 功能模块 | 行数 | 当前位置 | 问题 |
|---------|------|---------|------|
| 数据模型 | ~200 | 文件顶部 | 与业务逻辑混在一起 |
| DSL解析器 | ~160 | 中间部分 | 缺少独立测试入口 |
| 目录匹配器 | ~120 | 中间部分 | 与引擎强耦合 |
| 审核引擎核心 | ~700 | 主体部分 | 方法过多，职责不清 |
| CLI入口 | ~80 | 文件底部 | 与核心逻辑混在一起 |

### 1.3 技术债
1. **单文件过大**：1300+ 行，难以维护和测试
2. **缺少配置管理**：硬编码的字段映射、运算符等
3. **缺少日志系统**：使用 print 输出
4. **异常处理薄弱**：仅在关键路径有 try-catch
5. **依赖硬编码**：SQLite 连接方式固定
6. **缺少类型提示**：部分方法缺少返回类型标注

---

## 二、改造目标

### 2.1 架构目标
- **模块化**：按职责拆分为独立模块
- **可测试**：每个模块可独立单元测试
- **可扩展**：支持替换数据源、规则引擎等
- **可配置**：外部化配置参数

### 2.2 目录结构
```
engine/
├── __init__.py
├── models/                 # 数据模型层
│   ├── __init__.py
│   ├── claim.py            # ClaimEvent, ClaimLine 结算数据模型
│   └── result.py           # AuditResult 审核结果模型
├── dsl/                    # 条件 DSL 解析层
│   ├── __init__.py
│   ├── evaluator.py        # ConditionEvaluator 条件评估器
│   └── operators.py        # 运算符定义与注册
├── matcher/                # 目录匹配层
│   ├── __init__.py
│   └── catalog.py          # CatalogMatcher 目录匹配器
├── core/                   # 审核引擎核心层
│   ├── __init__.py
│   ├── engine.py           # MedicareAuditEngine 主引擎
│   ├── context.py          # 上下文构建
│   └── reasoning.py        # 推理说明生成
├── repo/                   # 数据访问层
│   ├── __init__.py
│   └── sqlite_repo.py      # SQLite 数据访问实现
├── config.py               # 全局配置
├── logger.py               # 日志配置
├── exceptions.py           # 自定义异常
└── cli.py                  # CLI 入口
```

---

## 三、改造步骤

### 步骤 1：创建项目结构（低风险）
- 创建 `engine/` 目录及子模块目录
- 初始化 `__init__.py` 文件

### 步骤 2：提取数据模型（低风险）
- 将 `ClaimEvent`、`ClaimLine` 移至 `models/claim.py`
- 将 `AuditResult` 移至 `models/result.py`
- 保持原有字段和属性不变

### 步骤 3：提取 DSL 解析器（中风险）
- 将 `ConditionEvaluator` 移至 `dsl/evaluator.py`
- 将运算符定义提取至 `dsl/operators.py`（支持插件化扩展）
- 添加运算符注册机制

### 步骤 4：提取目录匹配器（中风险）
- 将 `CatalogMatcher` 移至 `matcher/catalog.py`
- 改为依赖注入模式，支持替换数据源

### 步骤 5：重构审核引擎核心（高风险）
- 将 `MedicareAuditEngine` 移至 `core/engine.py`
- 将 `_build_context`、`_build_event_context` 移至 `core/context.py`
- 将 `_drg_reasoning` 移至 `core/reasoning.py`
- 将数据库操作移至 `repo/sqlite_repo.py`

### 步骤 6：添加配置与日志（低风险）
- 创建 `config.py`：集中管理配置参数
- 创建 `logger.py`：统一日志输出
- 创建 `exceptions.py`：自定义异常类型

### 步骤 7：提取 CLI（低风险）
- 将 `main()` 函数移至 `cli.py`
- 使用 `click` 或 `argparse` 重构命令行接口

### 步骤 8：更新 api_server.py（中风险）
- 更新 import 路径以适配新结构
- 验证 API 功能正常

### 步骤 9：运行测试验证（关键）
- 运行 `e2e_test_v3.py` 验证所有测试通过

---

## 四、关键设计决策

### 4.1 依赖注入
```python
# 改造前：硬编码依赖
class MedicareAuditEngine:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.evaluator = ConditionEvaluator()
        self.matcher = CatalogMatcher(self.conn)

# 改造后：依赖注入
class MedicareAuditEngine:
    def __init__(self, repo, evaluator, matcher):
        self.repo = repo
        self.evaluator = evaluator
        self.matcher = matcher
```

### 4.2 运算符注册机制
```python
# operators.py
OPERATORS = {}

def register_operator(name: str, func):
    OPERATORS[name] = func

# 支持动态添加运算符
register_operator("eq", lambda a, b: a == b)
```

### 4.3 配置管理
```python
# config.py
from dataclasses import dataclass

@dataclass
class EngineConfig:
    db_path: str = "medicare_engine.db"
    log_level: str = "INFO"
    cache_enabled: bool = True
    field_aliases: dict = field(default_factory=dict)
```

---

## 五、风险评估

| 风险项 | 等级 | 应对措施 |
|-------|------|---------|
| API 兼容性 | 高 | 保持 `MedicareAuditEngine` 对外接口不变 |
| 测试失败 | 高 | 先运行现有测试，确保基线通过 |
| 路径问题 | 中 | 使用绝对导入路径 |
| 性能影响 | 低 | 保持原有逻辑不变，仅调整结构 |

---

## 六、验证标准

1. ✅ 所有文件拆分完成，单文件 ≤ 500 行
2. ✅ `e2e_test_v3.py` 全部通过（36/36）
3. ✅ API 服务正常运行（`python3 api_server.py`）
4. ✅ CLI 命令正常工作（`python3 -m engine.cli --stats`）
5. ✅ 审核性能无明显下降（100行 < 300ms）

---

## 七、里程碑

| 阶段 | 任务 | 交付物 |
|------|------|--------|
| 1 | 模块拆分 | `engine/` 目录结构 |
| 2 | 核心重构 | 审核引擎核心模块 |
| 3 | 基础设施 | 配置、日志、异常处理 |
| 4 | 集成测试 | 测试验证 |