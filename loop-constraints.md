---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 8584983581cff71c15107d5026ec0e62_4a262431774711f1a7da5254006c9bbf
    ReservedCode1: YUW9AKvhkTaXbBeq2dL23TWXjueQ83TQhj/1JCErzNLgbUa/w4yOxPjnyNypsra9+7+s7n5bJnZb+cLQ3Iz5siCtSRZCUno5Y/ryL85zD23zJMiyhhzgclPb/akEF+DN1eFi9nk2yXWeCJjizHFlyFRBw+R06/IFllEMKWn6iFR4ovqhRjgb+pd4usc=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 8584983581cff71c15107d5026ec0e62_4a262431774711f1a7da5254006c9bbf
    ReservedCode2: YUW9AKvhkTaXbBeq2dL23TWXjueQ83TQhj/1JCErzNLgbUa/w4yOxPjnyNypsra9+7+s7n5bJnZb+cLQ3Iz5siCtSRZCUno5Y/ryL85zD23zJMiyhhzgclPb/akEF+DN1eFi9nk2yXWeCJjizHFlyFRBw+R06/IFllEMKWn6iFR4ovqhRjgb+pd4usc=
---

# Loop Constraints — Medicare Audit Engine

> 本文件由 loop-constraints skill 在每次循环启动时读取。
> 以下规则对 Agent **具有强制约束力**，不可绕过。

## Push & Merge
- 禁止未经人工审批直接 push 到 main 分支
- 禁止自动 merge，必须先创建 draft PR，人工 review 后手动合入
- 所有代码变更必须在隔离的 git worktree 中执行，禁止直接修改工作区

## Path Denylist（禁止自动修改）

### 核心引擎 — 必须人工
- `audit_engine/core/engine.py`       # 审核主流程
- `audit_engine/core/context.py`      # 审核上下文构建
- `audit_engine/core/reasoning.py`    # DRG 推理逻辑
- `audit_engine/dsl/evaluator.py`     # 条件求值器
- `audit_engine/dsl/operators.py`     # DSL 运算符定义

### 数据库 & 部署 — 必须人工
- `schema.sql`                        # 数据库建表脚本
- `docker-compose.yml`                # 容器编排
- `Dockerfile`                        # 镜像构建
- `.dockerignore`                     # 构建排除规则

### API 入口 — 必须人工
- `api_server.py`                     # API 服务入口
- `api/deps.py`                       # 依赖注入

### 配置 & 密钥
- `.env`、`.env.*`                    # 环境变量
- `pyproject.toml`                    # 项目元数据（依赖版本除外）
- `.atomcode/`                        # IDE 配置
- 任何包含 credentials、secrets、tokens 的文件

## Path Allowlist（Agent 可自动修改）

- `tests/`                            # 测试文件（新增/修复测试）
- `docs/`                             # 文档更新
- `web/`                              # 前端静态资源
- `README.md`                         # 项目说明
- `api/routes/agent.py`              # Agent 相关路由（非核心业务）
- `api/schemas.py`                   # Pydantic schema（非破坏性扩展）

## Dependency Updates（依赖升级规则）

- **Patch 版本**：允许自动升级，必须跑 `pytest` 全部通过
- **Minor 版本**：允许自动升级，跑 `pytest` + `ruff check` 通过后 draft PR
- **Major 版本**：禁止自动升级，仅生成升级建议报告，人工决策
- `pyproject.toml` 中 dependencies 的版本号变更属于此规则管辖

## Code Rules
- 每次修改前必须先跑现有测试套件确认基线通过
- 禁止通过 skip/mock/注释来让 CI 变绿
- 禁止在同一个 worktree 里修改不相关的模块
- 每次循环最多尝试修复同一个 item 3 次，超过后升级给人工
- DSL 运算符的行为变更禁止自动执行

## Communication
- 每次操作前在 STATE.md 中记录意图
- 禁止自行关闭 Issue 或 PR
- 遇到不确定的决策必须 human gate，附带完整上下文

## Budget
- 每日 token 消耗达预算上限 80% 时，自动切换为 report-only 模式
- 若 `STATE.md` 中激活 `loop-pause-all` 标记，立即退出本次循环
- 每次运行结束必须将 token 消耗追加到 `loop-run-log.md`

## Safety Gates
- 涉及 `audit_engine/core/` 的任何变更：强制 human gate
- 涉及 `schema.sql` 的任何变更：强制 human gate
- 涉及 `Dockerfile` / `docker-compose.yml`：强制 human gate
- Patch 依赖升级 + 测试全绿：可自动 draft PR（无自动 merge）
- 文档/测试/web 变更：允许自动 draft PR
*（内容由AI生成，仅供参考）*
