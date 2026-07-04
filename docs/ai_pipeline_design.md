# 医保智能审核规则引擎 — AI 自动闭环设计方案

## 一、现状分析与核心痛点

### 1.1 现有资产

| 资产 | 能力 |
|------|------|
| parse_rules.py | 4 种文件类型解析、10 项校验、3 种 CLI 模式、自修复+人工确认+再复查闭环 |
| rulebook.md | 11 种药品规则子类 + 7 种项目规则子类的 DSL 模板映射 |
| audit_engine.py | 四柱审核引擎、条件 DSL 解析器、目录匹配器（精确/编码/别名/模糊 4 级） |
| rule_items 表 | 3887 条活跃规则（两库GJ01~GJ17共3487条 + 立项指南LXZN共218条 + 目录限定MLXD共226条），另含17条drg_rules |
| 三阶段分布 | pre_check(事前医嘱) 2155条 / end_check(事中出科) 1727条 / post_audit(事后结算) 5条，向下级联 |
| YP 表 | 4567 条药品（ATC编码覆盖率98.3%） |
| FW 表 | 2141 条项目 |
| icd_10 表 | 32189 条疾病诊断 |
| icd_9 表 | 13518 条手术操作 |
| e2e测试 | V3: 36组用例覆盖31个规则类别+7个DRG场景, 35/36通过(97%) |

### 1.2 核心痛点

**痛点1：药品限适应症规则的 ICD-10 编码缺失**

当前 510 条"药品限适应症"规则的 conditions 中，ICD-10 编码是占位符 `[适应症ICD-10待补充]`。药品代码已从 Excel 解析完成，但"限法布雷病"这类逻辑依据文本需要人工映射为 ICD-10 编码，这正是 LLM 最擅长的语义理解任务。

**痛点2：新批次规则全手工录入**

当前流程：手工下载 Excel → 手工运行 parse_rules.py → 手工修正 → 手工复查 → 手工入库。全程人工干预。

**痛点3：校验维度不足**

现有 10 项校验均为格式/结构层面，缺乏语义交叉验证（ICD-10 映射是否正确、药品代码是否真实存在、规则间是否有逻辑冲突）。

---

## 二、总体架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI 自动闭环流水线                            │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │
│  │  采集层   │──►│  解析层   │──►│  校验层   │──►│  入库层   │    │
│  │Collector │   │ Parser   │   │Validator │   │ Importer │    │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘    │
│       │              │              │              │           │
│       ▼              ▼              ▼              ▼           │
│  ┌──────────────────────────────────────────────────────┐      │
│  │            人工 Checkpoint 层                         │      │
│  │  CP1: 采集确认  CP2: 归类确认  CP3: 校验确认  CP4: 入库审批 │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │            支撑设施层                                 │      │
│  │  置信度引擎  ·  回滚快照  ·  审计日志                  │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
         │ 无缝衔接（包裹不修改）
┌─────────────────────────────────────────────────────────────────┐
│                      现有系统（不变）                              │
│  parse_rules.py  ·  rulebook.md  ·  audit_engine.py            │
│  rule_items(3887)  ·  YP  ·  icd_10  ·  icd_9        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

**确定性优先、AI 增强、人工兜底**

每一步都先尽可能用确定性代码处理（SQL 查询、关键词匹配、JSON 解析），只在需要语义理解时才调用 LLM，且每个 AI 环节都有人工 Checkpoint 和置信度标记作为安全保障。

### 2.3 与现有系统的衔接

| 衔接点 | 方式 | 说明 |
|--------|------|------|
| parse_rules.py | **包裹调用，不修改原文件** | AI 管道调用其 `parse_all_files()` 和 `verify_and_fix()` 作为第一步 |
| rulebook.md | **读取为知识源** | LLM prompt 中注入 rulebook 的 DSL 模板，按现有模板生成 conditions |
| audit_engine.py | **不修改** | AI 闭环只负责规则生产，不负责规则执行 |
| schema.sql | **新增表，不修改现有表** | 新增 pipeline_runs、ai_validation_results、pipeline_snapshots |

---

## 三、各层详细设计

### 3.1 采集层（Collector）

**职责**：自动发现国家医保局发布的新批次规则 Excel，下载到本地。

**技术方案**：定时轮询 + 网页变更检测（纯确定性，不用 LLM）

```
采集流程：
  1. APScheduler 每日 08:00 执行
  2. 请求 nhsa.gov.cn 通知公告，搜索"智能监管""两库""规则""知识点"关键词
  3. 与上次快照对比，检测新文章
  4. 若发现新文章：提取附件下载链接 → 下载 Excel → 生成采集报告
  5. 触发 CP1 人工 Checkpoint
```

**输出**：采集报告 JSON + 下载的 Excel 文件

**人工 Checkpoint CP1 — 采集确认**

| 检查项 | 说明 |
|--------|------|
| 批次号识别正确 | 采集到的批次号与文章标题一致 |
| 文件完整性 | 下载的文件可正常打开 |
| 是否误报 | 文章确实是规则发布 |
| 操作 | 人工确认后，pipeline 状态 collecting → parsing |

### 3.2 解析层（Parser）

**职责**：在 parse_rules.py 基础上增加 AI 智能归类和 conditions 草稿生成。

**三步处理**：

#### STEP 1：结构化解析（复用 parse_rules.py）

```python
# 直接调用现有脚本，不修改原文件
from parse_rules import parse_all_files, verify_and_fix
all_rules = parse_all_files(excel_directory)  # 解析 + 10项校验
```

#### STEP 2：规则归类（增强现有 classify_rule_category）

```
归类策略：
  1. 先用现有 classify_rule_category() 关键词匹配（覆盖 17 种已知子类）
  2. 匹配结果为"未分类"的，调用 LLM 归类
  3. LLM prompt 注入 rulebook.md 规则分类体系
  4. 输出：{subcategory, confidence, reasoning}
  5. confidence < 0.8 标记为低置信度，优先人工审核
```

#### STEP 3：conditions DSL 草稿生成（核心 AI 能力）

这是 AI 闭环最关键的一步。将"逻辑依据"文本映射为 ICD-10 编码并生成完整 conditions。

**预检索策略（降低 LLM 成本）**：

不让 LLM 在 32189 条 ICD-10 中"大海捞针"，而是先用 SQL 预检索候选集：

```python
def presearch_icd10(keywords):
    """从 icd_10 表预检索候选编码"""
    for kw in keywords:
        rows = conn.execute(
            "SELECT chs_code, name FROM icd_10 WHERE name LIKE ?",
            (f"%{kw}%",)
        ).fetchall()
    return results[:20]  # 限制候选集大小
```

**LLM Prompt 设计**：

```
系统: 你是医保规则编码专家。根据以下信息，将"逻辑依据"映射为 ICD-10 编码。

规则类型: 药品-适应症限定
检出逻辑: 使用药品的疾病诊断不符合限定支付适应症
逻辑依据: 限法布雷病患者的长期酶替代治疗
药品名称: 阿加糖酶α注射用浓溶液
药品说明书适应症: 法布雷病的长期酶替代治疗

ICD-10 候选编码（预检索）:
  - E75.2: 其他鞘脂贮积症（含法布雷病）

DSL 模板（来自 rulebook.md）:
  {"logic": "AND", "conditions": [
    {"field": "claim_line.med_list_code", "op": "in", "value": [药品代码]},
    {"field": "claim_event.diagnosis_codes", "op": "not_contains", "value": [ICD-10]}
  ]}

请输出: ICD-10 编码列表、完整 conditions DSL、映射置信度、推理说明
```

**LLM 输出**：

```json
{
  "icd10_codes": ["E75.2"],
  "conditions_dsl": {"logic": "AND", "conditions": [...]},
  "confidence": 0.95,
  "reasoning": "法布雷病在 ICD-10 中归类于 E75.2 其他鞘脂贮积症",
  "alternative_codes": ["E75.24"]
}
```

**人工 Checkpoint CP2 — 归类与 DSL 确认**

| 置信度 | 处理策略 | 人工操作 |
|--------|----------|----------|
| >= 0.95 | 自动通过 | 抽查 10% |
| 0.80-0.94 | 自动通过 | 抽查 30% |
| 0.60-0.79 | 挂起待审 | 逐条审核 |
| < 0.60 | 拒绝 | 逐条审核 + 可能需专家介入 |

### 3.3 校验层（Validator）

**职责**：在现有 10 项格式校验基础上，增加 4 项 AI 语义校验。

```
双层校验架构：
  第一层：现有 10 项格式校验（确定性，复用 verify_and_fix）
    → 全部通过后进入第二层
  
  第二层：AI 语义交叉验证（新增）
    A. ICD-10 映射验证
    B. 药品代码验证
    C. 逻辑冲突检测
    D. DSL 语法验证
```

#### 校验 A：ICD-10 映射验证

```
1. 确定性：检查 ICD-10 编码是否存在于 icd_10 表
2. AI 语义：验证编码与逻辑依据文本的语义一致性
   → "限法布雷病" + "E75.2: 其他鞘脂贮积症" → 是否覆盖？
3. AI 建议：是否存在更精确的子编码（如 E75.24）
```

#### 校验 B：药品代码验证

```
1. 确定性：检查药品代码是否存在于 YP.chs_code
2. 确定性：检查代码前缀与规则类型是否匹配（X/Z/T 开头）
3. AI 语义：药品名称与代码的药理分类是否一致
```

#### 校验 C：逻辑冲突检测

```
1. 确定性：同一药品被不同规则限定为互斥条件
   → 规则1 限男性 vs 规则2 限女性
2. 确定性：conditions value 数组的包含关系检测（子集/超集）
3. AI 语义：判断两条件是否逻辑互斥
```

#### 校验 D：DSL 语法验证

```
1. 确定性：json.loads() 解析成功
2. 确定性：field 路径在 audit_engine.py 支持的路径中
3. 确定性：op 在 ConditionEvaluator.OPERATORS 支持列表中
4. 确定性：logic 字段为 AND/OR/NOT
```

**人工 Checkpoint CP3 — 校验确认**

| 检查项 | 处理方式 |
|--------|----------|
| FAIL 项审查 | 所有校验状态为 FAIL 的规则必须逐条审查 |
| 低置信度审查 | 整体置信度 < 0.8 的规则需人工确认 |
| 冲突解决 | 逻辑冲突检测发现的问题需人工裁决 |
| 修改后重验 | 人工修改后需重新跑校验层 |

### 3.4 入库层（Importer）

**职责**：将校验通过的规则安全导入 rule_items，生成审计报告，支持回滚。

**四步处理**：

#### STEP 1：入库前 AI 预检

```
1. 批次完整性：确认本批次所有规则均通过校验，无遗漏
2. 增量对比：与已入库规则对比，检查重复导入
3. 变更影响评估：LLM 评估本次变更对审核引擎的影响
4. 生成入库预检报告
```

#### STEP 2：创建回滚快照

```python
# 备份受影响的 rule_items 数据
# 物理备份 SQLite 文件
# 记录到 pipeline_snapshots 表
```

#### STEP 3：执行入库（is_active=0 先入库）

```python
# 新规则全部以 is_active=0（未启用）状态入库
# 待 CP4 审批通过后再批量启用
INSERT INTO rule_items (..., is_active=0) VALUES (...)
```

#### STEP 4：生成审计报告

```
报告内容：
  1. 入库统计（新增/修改/跳过条数、按规则大类分布）
  2. 置信度分布（高/中/低/拒绝）
  3. AI 校验结果汇总（各项校验通过/警告/失败数）
  4. 变更明细（每条规则的 before/after 对比）
  5. 回滚信息（快照 ID、回滚命令）
```

**人工 Checkpoint CP4 — 入库审批**

| 检查项 | 处理方式 |
|--------|----------|
| 审计报告审查 | 人工审查入库预检报告的统计数据 |
| 风险评估 | 确认变更影响评估可接受 |
| 批量启用 | 审批通过后 `UPDATE rule_items SET is_active=1` |
| 回滚决策 | 发现问题执行回滚命令 |

**回滚机制**：

```python
def rollback_pipeline(run_id, reason):
    # 1. 加载快照
    # 2. 恢复 rule_items 数据
    # 3. 删除本次新增的规则
    # 4. 更新 pipeline 状态为 rolled_back
    # 5. 触发器自动记录 changelog
```

---

## 四、置信度标记机制

### 4.1 置信度计算

每条规则的最终置信度由多因素加权：

| 因素 | 权重 | 说明 |
|------|------|------|
| LLM 自评分 | 30% | LLM 对自身映射结果的置信度 |
| ICD-10 精确匹配 | 25% | LLM 输出的编码是否在预检索候选集中精确匹配 |
| 药品代码验证 | 20% | 代码是否真实存在于 YP |
| DSL 语法验证 | 15% | JSON 格式+字段路径+运算符全部合法 |
| 无逻辑冲突 | 10% | 与其他规则无逻辑矛盾 |

### 4.2 置信度处理矩阵

| 置信度 | 入库策略 | 人工操作 |
|--------|----------|----------|
| >= 0.95 | 自动入库 is_active=1 | 抽查 10% 验证 AI 准确率 |
| 0.80-0.94 | 自动入库 is_active=1 | 抽查 30% |
| 0.60-0.79 | 入库 is_active=0 | 逐条审核后启用 |
| < 0.60 | 拒绝入库 | 逐条审核 + 可能需专家介入 |

---

## 五、LLM 成本与可靠性

### 5.1 成本控制：分层调用

| 场景 | 调用 LLM？ | 理由 |
|------|-----------|------|
| 格式校验（10 项） | 否 | 确定性代码，零成本 |
| 规则归类（已知类型） | 否 | 关键词匹配 |
| 规则归类（未知类型） | 是，量少 | 仅"未分类"才调用 |
| ICD-10 预检索 | 否 | SQL LIKE 查询 |
| ICD-10 映射生成 | **是** | 核心场景，需语义理解 |
| 药品代码验证 | 否 | SQL 查询 |
| 逻辑冲突检测 | 部分 | 先确定性检测，仅疑似冲突才调 LLM |
| DSL 语法验证 | 否 | JSON 解析+字段检查 |
| 入库前预检 | 是，1 次 | 全局检查，每批次 1 次 |

**预估**：新批次 200 条规则 → 约 210-220 次 LLM 调用 → 约 $0.04/批次（GPT-4o-mini）

### 5.2 可靠性保障

```
多级降级：
  1. 主模型 GPT-4o-mini → 备用 DeepSeek-V3 → 兜底人工
  2. 超时重试 3 次，指数退避（1s, 2s, 4s）
  3. Structured Output + Pydantic 校验输出格式
  4. 相同输入结果缓存 24 小时
  5. 多条规则合并为一次调用（batch prompt）
```

### 5.3 LLM 输出校验链

```
LLM 原始输出
  → JSON 解析（失败重试）
  → Pydantic 模型校验（失败标记格式错误）
  → 确定性交叉验证（ICD-10 编码是否在 icd_10 表中）
  → 置信度评估
  → 置信度 < 阈值 → 人工审核队列
  → 置信度 >= 阈值 → 自动通过队列
```

---

## 六、新增数据表设计

在现有 schema.sql 基础上新增（不修改现有表）：

### pipeline_runs — 流水线运行记录

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT UNIQUE | 运行唯一标识（如 RUN-20260630-001） |
| trigger_source | TEXT | scheduled / manual / webhook |
| status | TEXT | pending→collecting→parsing→validating→importing→done/failed/rolled_back |
| collect_result / parse_result / validate_result / import_result | TEXT | 各层结果 JSON |
| total_rules / auto_passed / manual_needed / rejected | INTEGER | 统计 |
| cp1~cp4_status / cp1~cp4_reviewer / cp1~cp4_at | TEXT | 4 个人工 Checkpoint 状态 |
| started_at / completed_at / rolled_back_at | TEXT | 时间戳 |

### ai_validation_results — AI 校验结果明细

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT | 关联 pipeline_runs |
| rule_code | TEXT | 关联的规则编码 |
| check_type | TEXT | icd10_mapping / drug_code_verify / logic_conflict / dsl_syntax |
| check_status | TEXT | pass / warning / fail |
| ai_confidence | REAL | 置信度 0.0-1.0 |
| human_review | TEXT | approved / rejected / modified |
| llm_model / llm_tokens_used | TEXT/INTEGER | LLM 调用元数据 |

### pipeline_snapshots — 回滚快照

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT | 关联 pipeline_runs |
| snapshot_type | TEXT | pre_import / post_import |
| affected_rule_ids | TEXT | JSON 数组，受影响的 rule_items.id |
| rule_items_backup | TEXT | JSON，变更前的完整数据 |
| db_backup_path | TEXT | SQLite 物理备份路径 |

---

## 七、目录结构

```
/Users/linye/zykj/engine/
├── ai_pipeline/                    # 新增：AI 闭环管道
│   ├── __init__.py
│   ├── config.py                   # 配置（LLM 模型、置信度阈值、API Key）
│   ├── models.py                   # Pydantic 数据模型
│   ├── collector.py                # 采集层
│   ├── parser_enhanced.py           # 解析层增强
│   ├── icd10_mapper.py             # ICD-10 映射核心模块
│   ├── validator.py                # 校验层
│   ├── importer.py                 # 入库层
│   ├── rollback.py                 # 回滚机制
│   ├── confidence.py               # 置信度计算引擎
│   ├── llm_client.py               # LLM 客户端
│   ├── report_generator.py         # 审计报告生成
│   ├── cli.py                      # CLI 入口
│   └── prompts/                    # LLM Prompt 模板
│       ├── icd10_mapping.txt
│       ├── rule_classification.txt
│       ├── logic_conflict.txt
│       └── pre_import_check.txt
├── parse_rules.py                  # 现有：不修改
├── audit_engine.py                 # 现有：不修改
├── rulebook.md                     # 现有：不修改（作为 AI 知识源）
├── schema.sql                      # 现有：追加新表定义
└── ...
```

---

## 八、分阶段实施路径

### 第一阶段：解决核心痛点 — ICD-10 映射闭环

**目标**：解决 510 条规则的 `[适应症ICD-10待补充]` 占位符

**范围**：
- 实现解析层 STEP 3（AI DSL 生成）
- 实现校验层校验 A（ICD-10 映射验证）和校验 D（DSL 语法验证）
- 实现置信度标记机制
- 不需要采集层（已有 Excel）
- 不需要入库层（规则已在 rule_items，只需 UPDATE conditions）

**步骤**：
1. 新增 `ai_pipeline/` 目录，创建 `icd10_mapper.py`
2. 实现预检索函数：从"逻辑依据"提取疾病关键词 → SQL 查询候选集
3. 实现 LLM 调用：构建 prompt（注入 rulebook 模板 + 候选集 + 药品说明书）
4. 实现结构化输出解析：Pydantic 模型校验
5. 实现置信度计算
6. 实现回滚机制：更新前备份原 conditions
7. 对 510 条规则批量执行，生成映射报告
8. 人工审核低置信度项

**验收标准**：
- 510 条规则不再有占位符
- 高置信度（>=0.80）占比 > 70%
- 人工抽查准确率 > 95%

### 第二阶段：全量校验层建设

**目标**：建立完整 AI 语义校验体系

**范围**：
- 实现校验层全部 4 项 AI 校验（A/B/C/D）
- 新增 `ai_validation_results` 表
- 对现有 3887 条规则全量跑校验

**验收标准**：
- 3887 条规则全部通过 4 项 AI 校验
- 历史问题已修复或标记

### 第三阶段：采集层 + 入库层建设

**目标**：端到端自动化

**范围**：
- 实现采集层（定时轮询 + 下载）
- 实现入库层（预检 + 快照 + 入库 + 审计报告）
- 实现 4 个人工 Checkpoint 交互
- 新增 `pipeline_runs` 和 `pipeline_snapshots` 表

**验收标准**：
- 模拟新批次可端到端自动处理
- 4 个 Checkpoint 可正常交互
- 回滚机制 30 秒内恢复

### 第四阶段：优化与监控

**目标**：提升自动化率，降低人工干预

**范围**：
- AI 准确率监控看板
- prompt 调优
- 批量处理性能优化
- （可选）Web UI 建设

**验收标准**：
- 高置信度规则自动入库准确率 > 98%
- 人工干预比例 < 20%
- 端到端处理新批次 < 30 分钟（含人工审核）

---

## 九、技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| LLM 主模型 | GPT-4o-mini | 成本低，Structured Output 可靠 |
| LLM 备用模型 | DeepSeek-V3 | 国内 API，稳定性好 |
| LLM 调用框架 | Instructor | 结构化输出校验，自动重试 |
| 结构化输出校验 | Pydantic v2 | 与 FastAPI 一致 |
| 定时任务 | APScheduler | 纯 Python，无额外基础设施 |
| HTML 解析 | BeautifulSoup4 | 轻量 |
| Excel 解析 | pandas（现有） | 复用 parse_rules.py |
| 数据库 | SQLite（现有） | 新增表与现有共存 |
| 缓存 | diskcache | 纯 Python 磁盘缓存 |

### 新增依赖

```
instructor>=1.0.0           # LLM 结构化输出
openai>=1.0.0               # OpenAI API 客户端
beautifulsoup4>=4.12.0      # HTML 解析
apscheduler>=3.10.0         # 定时任务
diskcache>=5.6.0            # LLM 结果缓存
```

---

## 十、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM 幻觉生成不存在的 ICD-10 编码 | 规则误判 | 确定性校验：编码必须在 icd_10 表中存在 |
| LLM 映射不准确 | 规则误判 | 置信度阈值 + 人工审核 + 双模型交叉验证 |
| 医保局官网改版 | 采集失败 | 告警通知人工，支持手工上传 Excel |
| 批量 LLM 调用超时 | 处理中断 | 指数退避重试 + 断点续传 |
| 入库后发现错误 | 已启用规则误判 | 回滚机制 + is_active=0 先入库 |
| LLM API 成本超预期 | 预算超支 | 分层调用 + 结果缓存 + GPT-4o-mini 为主 |

---

## 十一、与现有系统的衔接说明

核心原则：**包裹不修改**

```python
# ai_pipeline/parser_enhanced.py 中的衔接方式

from parse_rules import parse_all_files, verify_and_fix

# STEP 1: 直接调用现有解析（不修改原文件）
all_rules = parse_all_files(excel_directory)

# STEP 2: 在现有解析结果上增强
for rule in all_rules:
    for kp in rule['knowledge_points']:
        # 现有 classify_rule_category 做确定性归类
        category = classify_rule_category(rule['rule_name'])

        if category == '未分类':
            # AI 兜底归类（仅对未分类的调用 LLM）
            category = ai_classify(rule, kp)

        # 现有 verify_and_fix 已做过格式校验
        # AI 增加语义校验
        ai_validate(kp, category)

        # 生成/补全 conditions DSL
        if needs_icd10_mapping(kp):
            conditions = generate_conditions_with_ai(kp, category)
        else:
            conditions = generate_conditions_from_template(kp, category)
```

与 rulebook.md 的衔接：

```python
# 读取 rulebook.md 作为 LLM 的知识上下文
with open('rulebook.md', 'r') as f:
    rulebook_content = f.read()

# 在 LLM prompt 中注入 rulebook 的 DSL 模板
prompt = f"""
你是医保规则编码专家。请根据以下信息生成 conditions DSL。

规则分类体系与 DSL 模板（来自 rulebook.md）:
{rulebook_content}

当前规则信息:
- 规则类型: {category}
- 检出逻辑: {detection_logic}
- 逻辑依据: {policy_basis}
"""
```

**保障**：
1. parse_rules.py 的 10 项校验仍然全部执行，AI 校验是增量
2. rulebook.md 的 DSL 模板仍作为权威参考
3. audit_engine.py 不需要任何修改
4. AI 管道出问题可随时回退到纯手工流程

---

## 十二、存量僵尸规则激活 — 132 条不可执行 DSL 的 AI 闭环扩展

### 12.1 问题发现

对 3943 条规则全量扫描后发现：**132 条规则（3.3%）的 conditions 不可执行**。它们的 DSL 只有 `{"type":"xxx", "description":"文字描述"}` 结构，没有 `logic/conditions/field/op/value`，引擎无法从费用明细中检出任何东西。

```
3943 条规则
├── ✅ 3811 条（96.7%）— 可执行（有 logic+conditions 结构）
└── ❌ 132 条（3.3%）— 不可执行（只有 type+description 文本）
      ├── 107 条 — 立项指南（LG-* 前缀，按科室分类的项目互斥/定价规则）
      └──  25 条 — 项目规则模板（PROJ-* 前缀，通用计价规则）
```

### 12.2 17 种业务模式详细分析

#### 模式 1：text_rule — 立项指南文本规则（107 条）

**最大的一类**，来自立项指南解读辅导，按科室分类。每条规则有 `source_project_code`（项目编码）和 `source_project_name`（项目名称），但未转化为可执行条件。

| 子类型 | 数量 | 典型规则 | description 示例 |
|--------|------|---------|-----------------|
| 互斥（MUTU） | ~40 | LG-MUTU-0001 睡眠呼吸监测互斥 | 不可同时收取睡眠呼吸监测和多次睡眠潜伏期试验 |
| 定价（PRIC） | ~35 | LG-PRIC-0002 阴道异物取出费定价 | 阴道异物取出费不含宫腔镜检查费 |
| 频次（FREQ） | ~12 | LG-FREQ-0005 意识功能训练频次 | 每日限计费60分钟 |
| 条件（COND） | ~10 | LG-COND-0094 血液辐照费条件 | 使用血库提供的辐照血时不再另收血液辐照费 |
| 疗程（COURSE） | ~10 | LG-COURSE-0001 康复训练疗程 | 同一训练项目不超过30天 |

**当前 conditions 示例**：
```json
{
  "type": "text_rule",
  "description": "根据平均治疗时长设置每日费用封顶线。每日限计费60分钟。",
  "source_project_code": "003115030150000",
  "source_project_name": "认知功能训练",
  "category": "康复类"
}
```

**目标 conditions（AI 生成草稿）**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.project_code", "op": "eq", "value": "003115030150000"},
    {"field": "claim_line.daily_quantity", "op": "gt", "value": 60}
  ]
}
```

**AI 闭环流程**：
1. AI 从 description 提取关键参数（"每日限计费60分钟" → `daily_quantity gt 60`）
2. AI 从 source_project_code 获取项目编码填入 value
3. 按 rulebook.md 频次限定模板生成 DSL
4. 专家确认：60 分钟是否正确？项目编码是否匹配？
5. 置信度评估：有明确数值（60分钟）→ 高置信度；无明确数值 → 低置信度

**数据依赖**：无（项目编码已有，数值从 description 提取）

#### 模式 2：inclusion_negative — 含/不含规则（6 条）

**业务含义**：某项目价格构成"不含"另一类项目，不含的部分可单独收费（正向规则，不拦截）。

| 规则编码 | 名称 | description |
|---------|------|-------------|
| PROJ-ANE-004 | 麻醉中独立穿刺可单独收费 | 麻醉价格构成中的静脉穿刺仅指麻醉必要穿刺，动脉/中心静脉穿刺置管等独立操作可单独收费 |
| PROJ-ANE-005 | 麻醉不含检验可单独收费 | 麻醉价格构成不含检验成本，血气分析等确有必要可按相应项目据实收费 |
| PROJ-ANE-006 | 其他类别监测与麻醉不互斥 | 麻醉'监测'仅含与麻醉直接相关的监测，不含颅内压监测、神经电生理定位监测等 |
| PROJ-GEN-015 | 院内抢救不含除颤和气管插管 | 院内抢救费不含除颤和气管插管，可依规据实另收 |
| PROJ-NUR-007 | 护理类不含监测费用 | 各类护理类价格项目均不含监测费用，监测服务可按项目据实收费 |
| PROJ-RSP-004 | 肺切除不含淋巴清扫可另收 | 肺切除术含淋巴结清扫，胸腔镜肺切除含淋巴清扫和肺门纵隔淋巴结清扫 |

**当前 conditions 示例**：
```json
{
  "type": "inclusion_negative",
  "description": "麻醉价格构成不含检验成本，血气分析等确有必要可按相应项目据实收费"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.project_code", "op": "in", "value": ["麻醉类项目编码列表"]},
    {"field": "claim_line.med_list_name", "op": "contains", "value": "检验"},
    {"field": "claim_line.is_flagged", "op": "eq", "value": false}
  ],
  "action_type": "info",
  "note": "麻醉不含检验，检验费可单独收费，此规则为正向提示不拦截"
}
```

**AI 闭环流程**：
1. AI 从 description 提取"不含"的项目类别（"检验""监测""穿刺"）
2. AI 识别这是正向规则（"可单独收费"），标记为 info 而非 block
3. 专家确认：哪些麻醉项目编码？哪些检验项目属于"不含"范围？
4. 数据依赖：需要"项目价格构成映射表"（哪些项目纳入了哪些成本）

**数据依赖**：需新建 `price_composition_map` 表（项目→纳入成本清单）

#### 模式 3：FW_XMHC — 互斥规则（4 条）

**业务含义**：两个项目不可同时收费，与已有的 38 条互斥规则同类，但未转化为 DSL。

| 规则编码 | 名称 | description |
|---------|------|-------------|
| PROJ-RAD-007 | 氢谱磷谱波谱不可叠加 | 氢谱与磷谱是波谱成像的两种技术手段，单次同时采用按一次加收 |
| PROJ-RSP-001 | 多种能量源同次治疗按1次 | 使用多种能量源支气管镜特殊治疗应按一次治疗计价收费 |
| PROJ-RSP-003 | 烧伤抢救与其他抢救费互斥 | 烧伤抢救费属于抢救费特殊场景，不可另收其他类别抢救费 |
| PROJ-TCM-002 | 走罐与推拿+拔罐互斥 | 运用罐具进行推拿（走罐）按走罐收费，不得同时收推拿费+拔罐费 |

**当前 conditions 示例**：
```json
{
  "type": "FW_XMHC",
  "description": "运用罐具进行推拿（走罐）按走罐收费，不得同时收推拿费+拔罐费"
}
```

**目标 conditions（PROJ-TCM-002 为例）**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "走罐"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "推拿"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "拔罐"}
  ],
  "note": "走罐已包含推拿和拔罐操作，三者同时收费触发拦截"
}
```

**AI 闭环流程**：
1. AI 从 description 提取互斥项目名称（"走罐""推拿""拔罐"）
2. 按 rulebook.md 互斥模板生成 `coexists_with` 结构
3. 专家确认：项目名称关键词是否准确？是否需要更精确的编码匹配？
4. 置信度评估：有明确项目名称 → 中高置信度

**数据依赖**：无（关键词匹配，与已有 38 条互斥规则相同模式）

#### 模式 4：inclusion — 纳入价格构成（2 条）

**业务含义**：某项目价格构成已包含某些子流程，不可另收。

| 规则编码 | 名称 | description |
|---------|------|-------------|
| PROJ-RSP-002 | 皮肤微生物检查含全流程 | 皮肤微生物检查价格构成已含取材、检测、报告全流程，不可另收检验费 |
| PROJ-TCM-008 | 中医外治类不含中药饮片 | 中医外治类立项指南原则上不包含中药饮片，可按处方单独收费 |

**当前 conditions 示例**：
```json
{
  "type": "inclusion",
  "description": "皮肤微生物检查价格构成已含取材、检测、报告全流程，不可另收检验费"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "皮肤微生物检查"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "检验"}
  ],
  "note": "皮肤微生物检查已含全流程，同笔另收检验费触发拦截"
}
```

**数据依赖**：无（关键词匹配）

#### 模式 5：material_excluded — 基本物耗不可单独收费（1 条）

**业务含义**：纳入手术/操作价格构成的基本物耗（刀片、缝线、吸引器头等），不得向患者额外收费。

**当前 conditions**：
```json
{
  "type": "material_excluded",
  "description": "立项指南中明确纳入价格构成的基本物耗，不得向患者额外收费"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.item_type", "op": "eq", "value": "耗材"},
    {"field": "claim_line.is_basic_material", "op": "eq", "value": true},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "手术"}
  ],
  "note": "需基本物耗清单支撑 is_basic_material 判断"
}
```

**数据依赖**：需新建 `basic_material_catalog` 表（耗材代码→是否基本物耗）

**AI 闭环流程**：
1. AI 识别此规则需要外部数据（基本物耗清单）
2. AI 生成 DSL 框架，标记 `is_basic_material` 为待填充字段
3. 专家提供基本物耗清单（从立项指南附件提取）
4. 技术人员新建 `basic_material_catalog` 表，引擎新增 `is_basic_material` 操作符
5. 入库激活

#### 模式 6：material_special — 特殊功能耗材三条件（1 条）

**业务含义**：特殊功能耗材单独收费需同时满足三个条件。

**当前 conditions**：
```json
{
  "type": "material_special",
  "description": "特殊功能耗材单独收费需满足：(1)特殊功能且临床必须；(2)集采平台阳光挂网；(3)排除时同步配套价格减收"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.item_type", "op": "eq", "value": "耗材"},
    {"field": "claim_line.is_special_function", "op": "eq", "value": true},
    {"field": "claim_line.is_clinically_necessary", "op": "eq", "value": true},
    {"field": "claim_line.is_procurement_platform_listed", "op": "eq", "value": true},
    {"field": "claim_line.has_price_reduction", "op": "eq", "value": true}
  ],
  "note": "三条件全部满足才可单独收费，否则触发标记"
}
```

**数据依赖**：需耗材属性表（特殊功能/临床必须/集采挂网/价格减收）

#### 模式 7：surcharge_no_stack — 加收项同类别不可叠加（1 条）

**业务含义**：加收码 15 位编码末 2 位中，第 1 位代表类别，同类别不可叠加。

**当前 conditions**：
```json
{
  "type": "surcharge_no_stack",
  "description": "加收码15位编码末2位，第1位代表类别。第1位相同的加收项不可叠加收取，第1位不同的可叠加"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.item_type", "op": "eq", "value": "加收项"},
    {"field": "claim_event.same_surcharge_category_count", "op": "gt", "value": 1}
  ],
  "note": "加收码末2位第1位相同=同类别，同类别加收项超过1个触发标记"
}
```

**数据依赖**：引擎需新增 `same_surcharge_category_count` 计算逻辑（解析编码末2位）

**AI 闭环流程**：
1. AI 从 description 提取编码规则（"末2位第1位代表类别"）
2. AI 生成 DSL 框架，定义 `same_surcharge_category_count` 计算逻辑
3. 技术人员实现该计算逻辑
4. 专家确认编码规则解读正确

#### 模式 8：surcharge_calculation — 加减收计算基数（1 条）

**业务含义**：多加减收项应基于同一单价基数分别计算，不可嵌套。

**当前 conditions**：
```json
{
  "type": "surcharge_calculation",
  "description": "多加减收项以项目单价为基数分别计算后汇总，不可嵌套计算",
  "formula": "单价 + 单价*加收率1 + 单价*减收率2 - 单价*减收率"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.has_multiple_surcharges", "op": "eq", "value": true},
    {"field": "claim_line.calculation_method", "op": "!=", "value": "base_separate"}
  ],
  "note": "正确公式：单价 + 单价*加收率1 + 单价*加收率2 - 单价*减收率，不可嵌套",
  "formula": "base + base*r1 + base*r2 - base*d1"
}
```

**数据依赖**：引擎需新增加减收计算验证逻辑

#### 模式 9：mapping_included — 纳入价格构成不可单独收（1 条）

**业务含义**：映射关系中标记为"纳入价格构成"的项目不可单独收费。

**当前 conditions**：
```json
{
  "type": "mapping_included",
  "description": "映射关系中'纳入价格构成'的项目不可单独收费（如麻醉术前访视、术后随访）"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.project_code", "op": "in", "value": "[纳入价格构成的项目编码列表]"},
    {"field": "claim_line.is_charged_separately", "op": "eq", "value": true}
  ],
  "note": "需价格构成映射表支撑"
}
```

**数据依赖**：需新建 `price_composition_map` 表（项目编码→纳入/不纳入）

#### 模式 10：pricing_time_threshold — 时间阈值计价（1 条）

**业务含义**：分级护理不足 12 小时按半天收取。

**当前 conditions**：
```json
{
  "type": "pricing_time_threshold",
  "threshold_hours": 12,
  "description": "分级护理计价单位为'日'，不足12小时按半天收取"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "分级护理"},
    {"field": "claim_line.duration_hours", "op": "lt", "value": 12},
    {"field": "claim_line.billing_unit", "op": "eq", "value": "日"}
  ],
  "note": "不足12小时应按半天收取，检查是否按整天计费"
}
```

**数据依赖**：引擎需支持 `duration_hours` 字段（从入院/出院时间计算）

**AI 闭环亮点**：这条规则已有 `threshold_hours: 12` 参数，AI 只需套模板，置信度极高。

#### 模式 11：condition_forbidden — 禁收条件（1 条）

**业务含义**：管理性禁陪病房不可收免陪照护费。

**当前 conditions**：
```json
{
  "type": "condition_forbidden",
  "description": "危重症、新生儿、早产儿、精神病、干细胞/器官移植等管理性禁陪病房，不得收取免陪照护费"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "免陪照护"},
    {"field": "claim_event.ward_type", "op": "in", "value": ["危重症", "新生儿", "早产儿", "精神病", "干细胞移植", "器官移植"]}
  ],
  "note": "管理性禁陪病房不可收免陪照护费"
}
```

**数据依赖**：需就诊数据中包含 `ward_type`（病房类型）字段

**AI 闭环流程**：
1. AI 从 description 提取病房类型列表（"危重症""新生儿""早产儿""精神病""干细胞/器官移植"）
2. 生成 `ward_type in [...]` 条件
3. 专家确认列表是否完整

#### 模式 12：condition_multi — 多条件组合（1 条）

**业务含义**：严密隔离护理费需同时满足疾病类型和隔离条件。

**当前 conditions**：
```json
{
  "type": "condition_multi",
  "conditions": ["甲/乙类传染病", "医疗机构提供单人收治等隔离条件"],
  "description": "按乙类管理的传染病收取严密隔离护理费，须同时满足疾病类型和隔离条件"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "严密隔离护理"},
    {"field": "claim_event.diagnosis_codes", "op": "not_contains_any", "value": ["甲类传染病ICD-10列表", "乙类传染病ICD-10列表"]},
    {"field": "claim_event.isolation_type", "op": "!=", "value": "单人收治"}
  ],
  "note": "需同时满足传染病诊断+隔离条件，否则触发标记"
}
```

**数据依赖**：需 ICD-10 传染病编码列表 + 就诊数据中 `isolation_type` 字段

#### 模式 13：condition_technical — 技术条件限定（1 条）

**业务含义**：薄层加收需原始扫描层厚 <2mm，软件重建不可收。

**当前 conditions**：
```json
{
  "type": "condition_technical",
  "description": "薄层扫描加收需满足扫描原始标称层厚<2mm，软件重建得到的薄层不按薄层加收"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "薄层"},
    {"field": "claim_line.scan_type", "op": "eq", "value": "software_reconstruction"}
  ],
  "note": "软件重建薄层不可收薄层加收费，需检查扫描类型"
}
```

**数据依赖**：需就诊明细中有 `scan_type` 字段（原始扫描/软件重建）

#### 模式 14：condition_informed_consent — 知情同意条件（1 条）

**业务含义**：胶片零差率销售需患者知情同意。

**当前 conditions**：
```json
{
  "type": "condition_informed_consent",
  "description": "实体胶片不再打包计入放射检查价格，患者确有需求且知情同意后可按采购价零差率销售"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "胶片"},
    {"field": "claim_line.price_margin", "op": "gt", "value": 0},
    {"field": "claim_line.has_informed_consent", "op": "eq", "value": false}
  ],
  "note": "胶片零差率销售需知情同意，检查是否有加价和知情同意记录"
}
```

**数据依赖**：需就诊明细中有 `has_informed_consent` 和 `price_margin` 字段

#### 模式 15：pricing_higher_no_stack — 就高不叠加（1 条）

**业务含义**：多治疗模式同次使用时按最高收费标准计费，不叠加。

**当前 conditions**：
```json
{
  "type": "pricing_higher_no_stack",
  "description": "多治疗模式放疗设备同次使用时，按收费标准最高的项目计费，不叠加"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "放疗"},
    {"field": "claim_event.same_session_modes_count", "op": "gt", "value": 1},
    {"field": "claim_line.is_highest_price", "op": "eq", "value": false}
  ],
  "note": "多治疗模式同次使用按最高收费，非最高价项目不应单独收费"
}
```

**数据依赖**：引擎需支持 `same_session_modes_count` 和 `is_highest_price` 计算

#### 模式 16：condition_step_necessity — 必要步骤判定（1 条）

**业务含义**：手术必要步骤不可另收，非必要步骤可另收。

**当前 conditions**：
```json
{
  "type": "condition_step_necessity",
  "description": "妇科手术必要步骤（如子宫动脉结扎作为手术必要步骤）不另收费，非必要步骤可单独收费"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.project_code", "op": "in", "value": "[手术必要步骤编码列表]"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "子宫手术"}
  ],
  "note": "需手术步骤映射表定义哪些是必要步骤"
}
```

**数据依赖**：需新建 `surgery_step_map` 表（手术→必要步骤编码列表）

#### 模式 17：FW_XMHC_higher — 就高互斥（1 条）

**业务含义**：同部位常规与特殊治疗就高收费，不可叠加。

**当前 conditions**：
```json
{
  "type": "FW_XMHC_higher",
  "description": "同部位常规治疗与特殊治疗就高收费，按特殊治疗价格项目计费，不叠加"
}
```

**目标 conditions**：
```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "常规治疗"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "特殊治疗"},
    {"field": "claim_event.same_body_site", "op": "eq", "value": true}
  ],
  "note": "同部位常规+特殊治疗就高收费，需检查是否同部位且叠加收费"
}
```

**数据依赖**：需就诊明细中有 `body_site`（治疗部位）字段

### 12.3 实施难度分级

| 难度 | 规则数 | 模式 | 特征 | 实施方式 | 数据依赖 |
|------|--------|------|------|---------|---------|
| **低** | ~111 | text_rule(互斥/定价/频次/条件/疗程) + FW_XMHC + inclusion | 逻辑清晰，关键词匹配即可 | AI 自动生成 DSL，专家确认 | 无 |
| **中** | ~8 | pricing_time_threshold + condition_forbidden + condition_multi + pricing_higher_no_stack | 需要新增字段但逻辑明确 | AI 生成草稿，技术人员加字段 | 就诊数据新增字段 |
| **高** | ~13 | material_excluded + material_special + surcharge_no_stack + surcharge_calculation + mapping_included + condition_technical + condition_informed_consent + condition_step_necessity + FW_XMHC_higher | 需要新建表+新操作符 | 专家定义规则，技术实现引擎 | 新表+引擎扩展 |

### 12.4 AI 闭环激活流程

```
132 条僵尸规则
    ↓
Step 1: AI 批量分析（采集 + 归类）
    → 逐条解析 type + description
    → 归类到 17 种业务模式
    → 识别数据依赖（无依赖/需新字段/需新表）
    → 生成 DSL 草稿 + 置信度 + 数据缺口报告
    ↓
Step 2: 按难度分批处理
    ↓
    ├── 批次 A（低难度 111 条）
    │   → AI 自动生成 DSL
    │   → 专家 Checkpoint：确认关键词和模板匹配
    │   → 入库激活
    │   → 预计耗时：1-2 天
    │
    ├── 批次 B（中难度 8 条）
    │   → AI 生成 DSL 框架
    │   → 技术人员：引擎新增字段支持（ward_type, duration_hours 等）
    │   → 专家 Checkpoint：确认字段值域
    │   → 入库激活
    │   → 预计耗时：3-5 天
    │
    └── 批次 C（高难度 13 条）
        → AI 生成 DSL 框架 + 数据缺口清单
        → 专家：提供基本物耗清单、手术步骤映射等数据
        → 技术人员：新建表 + 引擎新增操作符
        → 专家 Checkpoint：确认数据完整性
        → 入库激活
        → 预计耗时：1-2 周
    ↓
Step 3: 全量验证
    → 132 条规则全部可执行
    → 引擎执行无报错
    → 规则覆盖率从 96.7% → 100%
```

### 12.5 数据依赖清单

| 需新建的表 | 用途 | 关联模式 | 提供方 |
|-----------|------|---------|--------|
| `basic_material_catalog` | 基本物耗清单（耗材代码→是否基本物耗） | 模式 5 | 医保专家从立项指南提取 |
| `price_composition_map` | 价格构成映射（项目编码→纳入成本清单） | 模式 2, 9 | 医保专家从立项指南提取 |
| `surgery_step_map` | 手术步骤映射（手术→必要步骤编码列表） | 模式 16 | 医保专家+临床医生定义 |
| `special_material_attr` | 特殊耗材属性（代码→特殊功能/临床必须/集采挂网） | 模式 6 | 医保专家+采购部门 |

| 需引擎新增的字段 | 用途 | 关联模式 | 实现方 |
|----------------|------|---------|--------|
| `claim_line.item_type` | 明细行类型（药品/项目/耗材/加收项） | 模式 5, 6, 7 | 技术人员 |
| `claim_line.is_basic_material` | 是否基本物耗（查 basic_material_catalog） | 模式 5 | 技术人员 |
| `claim_line.duration_hours` | 服务时长（小时） | 模式 10 | 技术人员 |
| `claim_event.ward_type` | 病房类型 | 模式 11 | 技术人员 |
| `claim_event.isolation_type` | 隔离类型 | 模式 12 | 技术人员 |
| `claim_line.scan_type` | 扫描类型（原始/重建） | 模式 13 | 技术人员 |
| `claim_line.has_informed_consent` | 是否有知情同意 | 模式 14 | 技术人员 |
| `claim_event.same_body_site` | 是否同部位 | 模式 17 | 技术人员 |

| 需引擎新增的操作符 | 用途 | 关联模式 |
|------------------|------|---------|
| `same_surcharge_category_count` | 同类别加收项计数 | 模式 7 |
| `has_multiple_surcharges` | 是否有多加减收项 | 模式 8 |
| `same_session_modes_count` | 同次治疗模式计数 | 模式 15 |
| `is_highest_price` | 是否最高价 | 模式 15 |
| `not_contains_any` | 不包含列表中任意项 | 模式 12 |

### 12.6 AI 闭环中的分工

```
132 条僵尸规则激活的三方分工：

┌─────────────────────────────────────────────────────┐
│ AI 智能体                                             │
│  • 解析 132 条 description 文本                      │
│  • 归类到 17 种业务模式                               │
│  • 生成 DSL 草稿（低难度直接可用）                     │
│  • 识别数据缺口（标记需专家/技术提供的数据）             │
│  • 生成置信度评估                                     │
│  • 低难度 111 条自动处理，中高难度生成框架              │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌──────────────────────┴──────────────────────────────┐
│                人工 Checkpoint                        │
├─────────────────────┬───────────────────────────────┤
│ 医保专家              │ 技术人员                       │
│  • 确认 DSL 关键词    │  • 新增引擎字段               │
│  • 提供物耗清单       │  • 新建数据表                  │
│  • 提供手术步骤映射   │  • 实现新操作符                │
│  • 确认病房类型列表   │  • 引擎测试                    │
│  • 审批入库           │  • 性能验证                    │
└─────────────────────┴───────────────────────────────┘
```

### 12.7 实际完成结果（2026-07-01）

| 指标 | 激活前 | 激活后 | 状态 |
|------|--------|--------|------|
| 可执行规则数 | 3811 | 3943 | ✅ 已完成 |
| 规则覆盖率 | 96.7% | 100% | ✅ 已完成 |
| 僵尸规则数 | 132 | 0 | ✅ 已完成 |
| 引擎运算符数 | 12 | 17（+5） | ✅ 已完成 |
| 引擎字段数 | 29 | 48（+19） | ✅ 已完成 |
| 描述型规则 | 132 (3.3%) | 0 (0%) | ✅ 已完成 |

**实施记录**：
- 批次 A（低难度 119 条）：text_rule + FW_XMHC + inclusion，关键词匹配+数值提取，立即可执行
- 批次 B（中难度 5 条）：pricing_time_threshold + condition_forbidden + condition_multi + pricing_higher_no_stack + FW_XMHC_higher，引擎新增 10 个可计算字段
- 批次 C（高难度 8 条）：material_excluded + material_special + surcharge 等，DSL 框架 + note 标记数据缺口，引擎新增 6 个默认 None 字段（待外部数据表接入）
- 运行时测试：10 条样本规则零报错
- 处置类型分布：block 64 / tag 61 / info 7

### 12.8 与 AI 闭环五阶段的对应关系

僵尸规则激活作为 AI 闭环的**第二阶段补充任务**，与全量校验层建设同步进行：

| AI 闭环阶段 | 原计划 | 新增僵尸规则激活 |
|------------|--------|----------------|
| 第一阶段 | ICD-10 映射闭环（510 条） | — |
| 第二阶段 | 全量校验层建设 | **+132 条僵尸规则激活（批次 A 低难度）** |
| 第三阶段 | 采集层+入库层 | **+中高难度规则激活（批次 B/C）** |
| 第四阶段 | 优化与监控 | 僵尸规则激活效果验证 |
