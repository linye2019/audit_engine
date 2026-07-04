# 医保智能审核引擎 — 架构设计文档

## 项目概述

医保智能审核系统，基于国家医保局「智能监管两库」（全部17批、12种规则类型）与「医疗服务价格项目立项指南」，关联药品、诊疗项目、耗材三目录，形成可执行的支付合规规则。

核心哲学：

- **三目为基础**（药品/项目/耗材各自有独立目录，只描述"是什么"）
- **两库+立项指南为约束**（两库提供监管规则，立项指南提供项目计价/适应症/频次边界，二者关联三目形成有效规则，统一归 rule_items）
- **四柱为框架**（药品目录限制 → 耗材使用合规 → 项目收费合规 → 支付合规性，正交不重叠）

---

## 一、目录结构

```
project_guide/
├── medicare_engine.db           # SQLite 数据库
├── ARCHITECTURE.md              # 本文档
├── pricing_engine/
│   ├── query_utils.py           # Python 引擎层
│   ├── audit_cli.py             # CLI 审计工具
│   ├── price_reasoning.js       # 前端 JS 引擎（嵌入 HTML）
│   └── test_js_engine.js        # JS 引擎 Node 测试
├── skills/medicare-rules-checker/
│   └── references/
│       └── prescription-checker-v2.html  # 前端页面
├── data/
│   ├── guides_extracted_data.json        # 立项指南图片提取数据
│   ├── gd_from_db.js                     # 从 DB 导出的 _GD 数据
│   ├── batch_png_map.json                # 图片批次映射
│   └── guide_batches.json                # 立项指南批次信息
├── migrate_project_catalog.py       # 建表脚本（已归档）
├── migrate_consumable_catalog.py
├── icd_scraper.py                   # ICD-10/ICD-9 浏览器自动化抓取脚本
├── fetch_and_import_icd.py          # ICD 数据导入合并脚本
├── fix_drug_catalog.py              # 药品目录限制条件拆分修复
└── fix_*.py                         # 修复脚本（已归档）
```

---

## 二、数据模型：三目录 + 两库 + 立项指南

### 2.1 设计原则

```
┌──────────────────────────────────────────────────────────────────┐
│                        三目录  只描述"是什么"                       │
│ ├── YP      → 药品的通用名、剂型、分类（不描述如何用）      │
│ ├── FW   → 项目的名称、计价单位、产出描述（不描述限制）  │
│ └── HC → 统一耗材目录（基本物耗/普通耗材/特殊功能）    │
├──────────────────────────────────────────────────────────────────┤
│              两库 + 立项指南  只描述"怎么管"                        │
│ └── rule_items        → 两库监管规则 + 立项指南约束，关联三目形成有效规则│
├──────────────────────────────────────────────────────────────────┤
│                        桥表                                       │
│ ├── project_catalog_codes     → 项目↔国家编码                     │
│ ├── project_catalog_aliases   → 项目↔别名（立项指南 vs DB名称）    │
│ └── project_connotation       → 项目内涵（已包含服务/耗材）        │
└──────────────────────────────────────────────────────────────────┘
```

关键约束：

- 三目录禁止混入任何规则字段（如 restriction_indication、visit_mode、pricing_strategy 等）
- 规则表保留 FK 关联（rule_items.project_a_id/b_id → FW(id)），主要用于审计引擎加速 JOIN，不强制 100% 匹配
- 每个违规项有且仅有一个支柱来源，结果可叠加不冲突

### 2.2 三目录表定义

#### ① 药品目录（YP）

```sql
CREATE TABLE YP (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name       TEXT NOT NULL UNIQUE,   -- 药品通用名
    dosage_form     TEXT,                   -- 剂型
    atc_code        TEXT,                   -- ATC 分类
    pharmacological_class TEXT,             -- 药理分类
    payment_type    TEXT DEFAULT '乙类',    -- 甲/乙/丙类（药品属性，非规则）
    label_indications TEXT,                 -- 说明书适应症（NMPA 批准的事实）
    restriction_raw TEXT,                   -- 原限制文本归档（保留原文备查）
    evidence_source TEXT,                   -- 数据来源
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| drug_name | TEXT | 药品通用名（唯一键） |
| dosage_form | TEXT | 剂型 |
| atc_code | TEXT | ATC 分类代码 |
| pharmacological_class | TEXT | 药理分类 |
| payment_type | TEXT | 甲/乙/丙类（这是药品的分类属性，不是规则） |
| label_indications | TEXT | 说明书适应症（NMPA 批准的客观事实，用于 off-label 比对） |
| restriction_raw | TEXT | 原医保目录限制文本（归档，规则解析后不应在此表直接查） |
| evidence_source | TEXT | 数据来源 |

⚠️ 所有结构性支付限制（限适应症、限性别、限年龄、限就医方式、限机构级别、限二线用药、限支付疗程、限工伤保险/生育保险、儿童专用）不属于目录，归入 rule_items。

#### ② 诊疗项目目录（FW）

```sql
CREATE TABLE FW (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    med_list_codg       TEXT NOT NULL UNIQUE,    -- 目录编码（15位立项指南编码）
    med_list_name       TEXT NOT NULL,            -- 目录名称
    med_list_type       TEXT DEFAULT '21',        -- 目录类型: 21=诊疗项目（基线版）
    category_id         INTEGER REFERENCES project_category(id),  -- 二级分类
    billing_unit        TEXT,                   -- 计价单位（次/日/部位等）
    service_output      TEXT,                   -- 服务产出（立项指南原文）
    pricing_composition TEXT,                   -- 价格构成（立项指南原文）
    chrgitm_lv          TEXT,                   -- 收费项目等级: 1=甲,2=乙,3=自费
    evidence_source     TEXT,                   -- 数据来源（gc/pricing/guide_new）
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| med_list_codg | TEXT | 目录编码（15位立项指南编码，唯一键） |
| med_list_name | TEXT | 目录名称 |
| med_list_type | TEXT | 目录类型: 21=诊疗项目（基线版） |
| category_id | INTEGER FK | 二级分类 → project_category.id |
| billing_unit | TEXT | 计价单位（纯描述） |
| service_output | TEXT | 服务产出（立项指南原文事实） |
| pricing_composition | TEXT | 价格构成（立项指南原文事实） |
| chrgitm_lv | TEXT | 收费项目等级: 1=甲,2=乙,3=自费 |
| evidence_source | TEXT | 来源标记（gc/pricing/guide_new） |

⚠️ 下列字段已被判定为规则属性，不在本表：pricing_strategy、exclusion_items、restriction_indication、gender、age_min/max、visit_mode、hospital_level、FW_XMPC、is_repeat_charge。它们归入 rule_items。

connotation 也不在本表——通过 project_connotation 桥表统一维护，见下文。

#### ③ 统一耗材目录（HC）

> 原 `consumables`、`basic_material_catalog`、`special_material_attr` 三表合并，通过 `material_type` 字段区分类型。

```sql
CREATE TABLE HC (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    material_type       TEXT NOT NULL DEFAULT 'normal',  -- basic=基本物耗, special=特殊功能, normal=普通耗材
    med_list_name       TEXT NOT NULL,                   -- 耗材/物耗名称
    med_list_codg       TEXT,                            -- 耗材编码
    ccode               TEXT,                            -- CUC编码（20位）
    category            TEXT,                            -- 分类
    payment_type        TEXT,                            -- 甲/乙类
    payment_ratio       REAL,                            -- 自付比例
    drug_loaded         INTEGER DEFAULT 0,               -- 是否载药
    drug_component      TEXT,                            -- 载药成分
    is_basic            INTEGER DEFAULT 0,               -- 1=基本物耗(不可单独收费)
    is_special_function INTEGER DEFAULT 0,               -- 1=特殊功能耗材
    is_clinically_necessary INTEGER DEFAULT 0,           -- 1=临床必须
    is_platform_listed  INTEGER DEFAULT 0,               -- 1=集采平台挂网
    price_reduction_rule TEXT,                           -- 排除时价格减收规则
    source_project_name TEXT,                            -- 关联的诊疗项目名称
    source_project_codg TEXT,                            -- 关联的诊疗项目编码
    match_keywords      TEXT,                            -- 匹配关键词
    evidence_source     TEXT,                            -- 政策出处
    evidence_summary    TEXT,                            -- 证据摘要
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| material_type | TEXT | 耗材类型：**basic**=基本物耗, **special**=特殊功能, **normal**=普通耗材 |
| med_list_name | TEXT | 耗材/物耗名称 |
| med_list_codg | TEXT | 国家医保耗材编码 |
| ccode | TEXT | CUC 编码（20位） |
| category | TEXT | 分类（自由文本） |
| payment_type | TEXT | 甲/乙类 |
| payment_ratio | REAL | 自付比例 |
| drug_loaded | INTEGER | 是否载药（物理属性，不是规则） |
| drug_component | TEXT | 载药成分（物理属性） |
| is_basic | INTEGER | 1=基本物耗（不可单独收费） |
| is_special_function | INTEGER | 1=特殊功能耗材 |
| evidence_source | TEXT | 数据来源/政策出处 |
| evidence_summary | TEXT | 证据摘要 |

⚠️ 耗材的适应症限制、用量限制、配对手术等属于规则，直接通过 `rule_items.conditions` DSL 表达，不使用独立桥表。

### 2.3 核心规则表（rule_items）

> **设计定位**：rule_items 是整个审核引擎的"大脑"。每条规则描述一个"如果...那么..."的判定逻辑：如果输入数据（claim_event + claim_line）满足某组条件，则产生某种处置结果。

```sql
CREATE TABLE rule_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 规则标识
    rule_code           TEXT NOT NULL UNIQUE,       -- 规则编码（如 DRUG-IND-001）
    rule_name           TEXT NOT NULL,               -- 规则名称（如"奥司他韦限流感"）
    rule_category       TEXT NOT NULL,               -- 规则大类（见下表）
    rule_subcategory    TEXT,                       -- 规则子类（如限适应症→限流感/限新冠等）
    -- 四柱归属
    pillar: YP / HC / FW / BZ（中药饮片归 YP 柱，rule_category=ZY_YPZF）
    -- 三阶段归属（事前医嘱/事中出科/事后结算）
    stage               TEXT DEFAULT 'post_audit',  -- pre_check(事前医嘱) / end_check(事中出科) / post_audit(事后结算)
    -- 规则级别
    severity            TEXT DEFAULT 'suspicious',  -- violation（明确违规）/ suspicious（可疑）/ info（提示）
    -- 关联实体（多选一或组合）
    drug_id             INTEGER REFERENCES YP(id),
    project_a_id        INTEGER REFERENCES FW(id),
    project_b_id        INTEGER REFERENCES FW(id),  -- 配对项目
    consumable_id       INTEGER REFERENCES HC(id),
    diagnosis_codes     TEXT,                       -- 关联的ICD-10编码（JSON数组，如 ["J11.1","J10.1"]）
    procedure_codes     TEXT,                       -- 关联的ICD-9-CM-3编码（JSON数组）
    -- 规则条件（JSON结构化，引擎解析执行）
    conditions          TEXT NOT NULL,              -- JSON条件体（见下方条件DSL设计）
    -- 处置措施
    action              TEXT DEFAULT 'warn',        -- block（拦截）/ warn（提醒）/ tag（标记）/ pass（放行）
    action_message      TEXT,                       -- 提示消息模板（如"该药品限流感患者使用，当前诊断不符"）
    -- 规则来源与版本
    source_batch        TEXT,                       -- 规则来源批次（两库"第12批"/立项指南"XX批"）
    source_reference    TEXT,                       -- 原始政策文件引用
    version             INTEGER DEFAULT 1,
    effective_date      TEXT,                       -- 生效日期
    expired_date        TEXT,                       -- 失效日期（空=长期有效）
    is_active           INTEGER DEFAULT 1,          -- 是否启用
    -- 元数据
    created_at          TEXT DEFAULT (datetime('now','localtime')),
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_rule_pillar ON rule_items(pillar);
CREATE INDEX idx_rule_stage ON rule_items(stage);
CREATE INDEX idx_rule_severity ON rule_items(severity);
CREATE INDEX idx_rule_drug ON rule_items(drug_id);
CREATE INDEX idx_rule_project ON rule_items(project_a_id);
CREATE INDEX idx_rule_active ON rule_items(is_active);
```

#### 规则大类（rule_category）

| 规则大类 | 对应柱 | 典型场景 | 说明 |
|---------|--------|---------|------|
| **YP_SYZ** | 柱1 | 药品限适应症 | 某药仅限某（些）ICD-10诊断使用 |
| **YP_XB** | 柱1 | 药品限性别 | 某药仅限男性/女性使用 |
| **drug_age** | 柱1 | 药品限年龄 | 某药限≥18岁或限儿童 |
| **YP_EXYY** | 柱1 | 药品限二线用药 | 需先使用一线药物无效后才可使用 |
| **YP_ZFLC** | 柱1 | 药品限支付疗程 | 累计用药天数/次数上限 |
| **drug_insurance** | 柱1 | 限工伤/生育保险 | 仅限特定险种支付 |
| **project_visit_mode** | 柱3 | 项目限就医方式 | 某项目仅限住院/门诊使用 |
| **project_hospital_level** | 柱3 | 项目限机构级别 | 某项目仅限三级医院开展 |
| **project_frequency** | 柱3 | 项目限频次 | 某项目限每日/每周次数 |
| **project_repeat** | 柱3 | 项目重复收费 | 同一项目同日重复计费 |
| **project_overcharge** | 柱3 | 项目超标准收费 | 单价超过限价标准 |
| **project_split** | 柱3 | 分解项目收费 | 将套餐项目拆分为多个子项目分别收费 |
| **HC_PD** | 柱2 | 耗材-手术配对 | 某耗材仅限某手术使用 |
| **consumable_indication** | 柱2 | 耗材适应症 | 某耗材限某诊断/手术使用 |
| **HC_SL** | 柱2 | 耗材用量限制 | 某耗材单次手术用量上限 |
| **drg_GT** | 柱4 | 高套分组 | 合并症编码异常多 |
| **drg_FJ** | 柱4 | 分解住院 | 同一患者短期内多次入院 |
| **drg_DB** | 柱4 | 低标入院 | 住院天数过短 |
| **drg_SJ** | 柱4 | 缩减服务 | 费用消耗指数过低 |

#### 条件 DSL 设计（conditions JSON 格式）

规则条件采用结构化 JSON，引擎统一解析执行：

```json
{
  "logic": "AND",
  "conditions": [
    { "field": "claim_line.line_type", "op": "eq", "value": "drug" },
    { "field": "claim_event.primary_diagnosis", "op": "not_in", "value": ["J11.1", "J10.1"] },
    { "field": "claim_event.gender", "op": "eq", "value": "男" },
    { "field": "claim_event.age", "op": "gte", "value": 18 }
  ]
}
```

支持的运算符：`eq` / `ne` / `gt` / `gte` / `lt` / `lte` / `in` / `not_in` / `contains` / `not_contains` / `regex` / `not_regex` / `is_null` / `is_not_null` / `any_contains` / `none_contains` / `coexists_with` / `not_exists` / `not_between` / `len_gt` / `len_gte`。

#### 性能优化设计（三级缓存 + 名称预过滤）

引擎内置三级缓存机制，确保100行明细审核在100ms内完成：

1. **规则缓存** (`_rule_cache`)：按 `pillar+stage` 缓存规则列表，避免重复查询数据库
2. **目录匹配缓存** (`_match_cache`)：按 `list_type+codg+name` 缓存目录匹配结果
3. **DRG规则缓存** (`_drg_rule_cache`)：按 `stage` 缓存DRG规则
4. **条件解析缓存** (`_condition_cache`)：条件JSON解析结果缓存，同一条件字符串只解析一次
5. **名称关键词预过滤** (`_name_keyword`)：从规则条件中提取 `med_list_name contains` 关键词，药品名不包含关键词时跳过规则评估

---

### 2.4 桥表定义

> 桥表用于目录↔编码、目录↔别名、目录↔内涵的关联关系。耗材的规则属性（适应症/用量/配对等）直接通过 `rule_items.conditions` DSL 表达，不再使用独立桥表。

#### ① 项目↔国家编码桥表（project_catalog_codes）

```sql
CREATE TABLE project_catalog_codes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    code_type           TEXT NOT NULL,              -- national（国家编码）/ regional（地方编码）/ internal（院内编码）
    code_value          TEXT NOT NULL,              -- 编码值
    region_code         TEXT,                       -- 地区编码（地方编码时必填）
    is_primary          INTEGER DEFAULT 0,          -- 是否主编码
    evidence_source     TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX idx_proj_code ON project_catalog_codes(project_id, code_type, code_value);
```

#### ② 项目↔别名桥表（project_catalog_aliases）

```sql
CREATE TABLE project_catalog_aliases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    alias_name          TEXT NOT NULL,              -- 别名（如立项指南中的名称 vs DB中的标准名称）
    alias_source        TEXT,                       -- 来源（如"立项指南第3批"）
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_proj_alias ON project_catalog_aliases(alias_name);
```

#### ③ 项目内涵桥表（project_connotation）

> 项目"内涵"描述该价格项目已包含哪些服务/耗材，避免重复收费。

```sql
CREATE TABLE project_connotation (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    included_project_id INTEGER REFERENCES FW(id),  -- 已包含的子项目
    included_item_type  TEXT,                       -- project / consumable / service
    included_item_name  TEXT,                       -- 已包含项的名称
    description         TEXT,                       -- 说明（如"该项目价格已包含麻醉费用"）
    evidence_source     TEXT,                       -- 立项指南原文引用
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

---

### 2.5 规则版本管理

> **设计定位**：采用"轻量快照 + 时间旅行"方案，通过 `effective_date` / `expired_date` 实现规则生效周期管理，配合变更日志和规则集快照，支持规则演进追溯和历史版本回查。

#### 设计原则

| 原则 | 说明 |
|------|------|
| **有效日期过滤** | 规则加载时自动按审核日期过滤 `effective_date <= audit_date < expired_date` |
| **版本递增** | 修改规则时保留旧版本（设为失效），插入新版本记录，`version` 字段递增 |
| **自动变更日志** | 触发器自动记录 rule_items 的 INSERT / UPDATE / 停用操作到 `rule_changelog` |
| **规则集快照** | 批量变更时打快照（`rule_set_snapshot`），标记规则集状态，便于版本对比和回滚 |
| **审核可追溯** | `audit_result.rule_version` 记录审核时使用的规则版本，支持事后回查 |

#### ① 规则变更日志表（rule_changelog）

```sql
CREATE TABLE rule_changelog (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id             INTEGER NOT NULL REFERENCES rule_items(id),
    rule_code           TEXT,                       -- 冗余存储，便于直接查询
    change_type         TEXT NOT NULL,              -- create / update / deactivate / version_upgrade / delete
    changed_fields      TEXT,                       -- JSON: {field: {before, after}}
    changed_by          TEXT,                       -- 操作人（system / user_id）
    changed_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

**触发时机**（由 SQLite 触发器自动维护）：

| 触发事件 | change_type | 说明 |
|---------|-------------|------|
| INSERT | `create` | 新增规则时记录完整字段 |
| UPDATE（version 不变） | `update` | 字段级 before/after 对比 |
| UPDATE（version 递增） | `version_upgrade` | 版本升级时标记 |
| UPDATE（is_active: 1→0） | `deactivate` | 规则停用单独标记 |

#### ② 规则集快照表（rule_set_snapshot）

```sql
CREATE TABLE rule_set_snapshot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_name       TEXT NOT NULL UNIQUE,       -- 快照名称，如 v2026Q3 / GJ18-import
    snapshot_desc       TEXT,                       -- 快照描述
    rule_count          INTEGER,                    -- 快照时活跃规则数
    created_at          TEXT DEFAULT (datetime('now','localtime')),
    created_by          TEXT,
    effective_date      TEXT,                       -- 快照生效日期
    expired_date        TEXT                        -- 快照失效日期（空=当前活跃）
);
CREATE INDEX idx_snapshot_active ON rule_set_snapshot(expired_date);
```

**典型快照场景**：
- 国家两库新批次导入完成（如 `GJ18-imported`）
- 季度规则校准发布（如 `2026Q3-release`）
- 重大政策调整（如 DRG 分组器版本升级）

#### 版本更新流程

```
修订规则（SQLiteRepository.update_rule_version）:
  1. 读取当前活跃版本（is_active=1 AND expired_date IS NULL）
  2. 将旧版本设为失效: is_active=0, expired_date=当前日期
  3. 插入新版本记录: version=old+1, effective_date=当前日期, is_active=1
  4. 触发器自动写入 rule_changelog（change_type='version_upgrade'）

创建规则集快照（SQLiteRepository.create_snapshot）:
  1. 统计当前活跃规则数
  2. 插入 rule_set_snapshot 记录
  3. 将上一个活跃快照的 expired_date 设为当前日期
  4. 新快照作为当前活跃版本
```

#### 时间旅行查询示例

```sql
-- 查询 2026-06-01 当天生效的所有药品适应症规则
SELECT rule_code, rule_name, version, effective_date, expired_date
FROM rule_items
WHERE pillar = 'drug'
  AND rule_category = 'YP_SYZ'
  AND is_active = 1
  AND (effective_date IS NULL OR effective_date <= '2026-06-01')
  AND (expired_date IS NULL OR expired_date > '2026-06-01')
ORDER BY rule_code, version;

-- 查看某规则的完整演进历史
SELECT change_type, changed_fields, changed_by, changed_at
FROM rule_changelog
WHERE rule_code = 'YP-SYZ-GJ01-0001'
ORDER BY changed_at ASC;
```

---

## 三、诊断编码维度（ICD 实体层）

> **设计定位**：诊断编码是"知识目录"的一部分（描述"是什么"），不是规则。它与三目录平行，作为 rule_items 规则触发时的核心匹配维度。

### 3.1 为什么诊断维度是独立章节

医保审核中几乎所有规则都需要诊断编码参与判定：

| 规则类型 | 诊断编码的作用 |
|---------|---------------|
| 药品限适应症 | 患者主诊断必须在药品允许的 ICD-10 范围内 |
| 限性别/限年龄 | 需结合患者基本信息交叉判定 |
| 限就医方式 | 门诊/住院方式与诊断的关联合理性 |
| 诊疗项目合规 | 主诊断必须与执行的诊疗项目临床逻辑一致 |
| 耗材配对 | 手术操作（ICD-9-CM-3）必须与耗材适配 |
| DRG/DIP入组 | ICD-10 主诊断 + ICD-9-CM-3 手术 → 病组分组 |
| 高套分组检测 | 合并症/并发症（MCC/CC）编码是否有病历支撑 |

### 3.2 疾病诊断实体表（icd_10）

```sql
CREATE TABLE icd_10 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chs_code        TEXT NOT NULL UNIQUE,       -- ICD-10 医保版2.0编码（如 J18.900）
    name            TEXT NOT NULL,               -- 诊断名称（医保版2.0）
    is_gray_code    INTEGER DEFAULT 0,          -- 是否灰码（1=灰码，不可作为主诊断）
    chapter         TEXT,                       -- 章节编码（如 J=呼吸系统）
    chapter_name    TEXT,                       -- 章节名称
    drg_group_type  TEXT,                       -- DRG分组类型：MDC/ADRG
    is_mcc          INTEGER DEFAULT 0,          -- 是否主要合并症/并发症
    is_cc           INTEGER DEFAULT 0,          -- 是否合并症/并发症
    guolin_code     TEXT,                       -- 国临版2.0编码
    guolin_name     TEXT,                       -- 国临版2.0名称
    need_review     TEXT,                       -- 是否需要论证
    review_reason   TEXT,                       -- 原因备注
    review_type     TEXT,                       -- 类型（编码一致名称不一致等）
    evidence_source TEXT,                       -- 来源
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| chs_code | TEXT | ICD-10 医保版编码，唯一键（如 J18.900、I21.000） |
| name | TEXT | 诊断名称（如"社区获得性肺炎"、"急性心肌梗死"） |
| is_gray_code | INTEGER | 灰码标识，CHS-DRG 2.0 中灰码不可作为主诊断 |
| chapter | TEXT | ICD-10 章节一级分类 |
| chapter_name | TEXT | 章节名称 |
| drg_group_type | TEXT | DRG 分组锚定类型 |
| is_mcc / is_cc | INTEGER | 合并症标记，用于 DRG 高套分组检测 |
| guolin_code / guolin_name | TEXT | 国临版2.0对照编码与名称 |
| need_review / review_reason / review_type | TEXT | 论证标记与说明 |

当前数据量：**2,453 条**（含亚目级编码 1,865 条 + 细目级补充 588 条），覆盖 ICD-10 全部 19 章，来源：国家医保信息业务编码标准数据库 + 临床路径管理系统 DOM 抓取。

⚠️ 本表只存储诊断的"客观属性"，不存储"某药品限制用于某诊断"——那是 rule_items 的职责。

### 3.3 手术操作实体表（icd_9）

```sql
CREATE TABLE icd_9 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chs_code        TEXT NOT NULL UNIQUE,       -- ICD-9-CM-3 医保版编码（如 36.0600）
    name            TEXT NOT NULL,               -- 手术/操作名称
    category        TEXT,                       -- 一级分类（如"心血管系统手术"）
    is_major        INTEGER DEFAULT 0,          -- 是否主要手术/操作
    drg_effect      TEXT,                       -- DRG 修正效应（major/minor/none）
    guolin_code     TEXT,                       -- 国临版3.0手术代码
    guolin_name     TEXT,                       -- 国临版3.0手术名称
    op_input_option TEXT NOT NULL,               -- 手术操作录入选项（必选/选择性/中医必选，必填）
    op_level        TEXT,                       -- 手术级别（一/二/三/四级）
    incision_type   TEXT,                       -- 切口类别（0/I/II/III）
    evidence_source TEXT,
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| chs_code | TEXT | ICD-9-CM-3 医保版编码，唯一键 |
| name | TEXT | 手术/操作名称 |
| is_major | INTEGER | 主要手术标识（病案首页需标记主要手术） |
| drg_effect | TEXT | 对 DRG 分组的修正效应 |
| guolin_code / guolin_name | TEXT | 国临版3.0对照编码与名称 |
| op_input_option | TEXT | 手术操作录入选项（必选/选择性/中医必选） |
| op_level | TEXT | 手术级别（一/二/三/四级） |
| incision_type | TEXT | 切口类别 |

当前数据量：**1,271 条**（含二位码 990 条 + 三位码补充 281 条），覆盖 ICD-9-CM-3 18 个手术分类，来源：国家医保信息业务编码标准数据库 + 临床路径管理系统 DOM 抓取。

---

## 四、审核输入模型（被审核的对象）

> **设计定位**：知识目录（三目录 + 诊断编码）是静态的"字典"，审核输入模型是动态的"考卷"——每次结算事件（claim_event）就是一份需要逐行判定的考卷。

### 4.1 为什么需要审核输入模型

没有审核输入，引擎无法运行。rule_items 中的 FK 关联（project_a_id、drug_id、diagnosis_id）缺少被 JOIN 的对象。

审核引擎的完整执行路径：
```
知识库（静态）               审核输入（动态）              审核输出（结果）
┌─────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ YP │         │                 │         │                 │
│ project_cat  │  JOIN   │   claim_event   │  规则   │  audit_result   │
│ HC │◄───│   claim_line    │────────►│  (违规/通过)     │
│ icd_10       │         │   (费用明细行)   │         │                 │
│ rule_items   │────────►│                 │         │                 │
└─────────────┘  规则绑定 └─────────────────┘         └─────────────────┘
```

### 4.2 结算事件主表（claim_event）

> 一次医保结算 = 一张"考卷"。一次住院或一次门诊就是一条 claim_event。

```sql
CREATE TABLE claim_event (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    setl_id             TEXT NOT NULL UNIQUE,     -- 结算ID（国家医保接口规范字段）
    mdtrt_id            TEXT,                       -- 就诊ID（接口规范核心字段，一次就诊唯一标识）
    -- 患者信息（对齐医保结算清单 + 接口规范 V1.1.85）
    psn_no              TEXT,                       -- 人员编号（医保唯一标识）
    psn_name            TEXT,                       -- 姓名
    gend                TEXT,                       -- 性别: 0=未知, 1=男, 2=女, 9=未说明（GB/T 2261.1）
    brdy                TEXT,                       -- 出生日期 YYYY-MM-DD
    insutype            TEXT,                       -- 险种: 310=职工基本医保, 390=城乡居民基本医保, 510=生育保险
    insu_region         TEXT,                       -- 参保地编码
    -- 就诊信息（对齐接口规范 2304/4101A）
    med_type            TEXT,                       -- 医疗类别: 11=普通门诊, 13=急诊, 14=门诊慢特病, 21=普通住院, 24=急诊转住院, 26=单病种住院, 28=日间手术
    adm_date            TEXT,                       -- 入院日期
    dscg_date           TEXT,                       -- 出院日期
    inhosp_days         INTEGER,                    -- 实际住院天数
    hosp_lv             TEXT,                       -- 医院等级: 1=三级特等, 2=三级甲等, 3=三级乙等, 4=三级丙等, 5=二级甲等, 6=二级乙等, 7=二级丙等, 8=一级甲等, 9=一级乙等, 10=一级丙等, 11=无等级
    dept                TEXT,                       -- 入院科别
    adm_way             TEXT,                       -- 入院途径: 1=急诊, 2=门诊, 3=其他医疗机构转入, 9=其他
    dscg_way            TEXT,                       -- 离院方式: 1=医嘱离院, 2=医嘱转院, 3=转社区卫生服务机构, 4=非医嘱离院, 5=死亡, 9=其他
    -- 诊断信息（对齐医保结算清单填写规范）
    main_diag_code      TEXT,                       -- 主要诊断ICD-10编码（医保版）
    main_diag_name      TEXT,                       -- 主要诊断名称
    diag_codes          TEXT,                       -- 次诊断ICD-10编码（JSON数组）
    -- 手术信息
    main_oprn_code      TEXT,                       -- 主要手术ICD-9-CM-3编码（医保版）
    oprn_codes          TEXT,                       -- 次手术编码（JSON数组）
    -- DRG/DIP 信息
    drg_codg            TEXT,                       -- DRG病组编码
    drg_wt              REAL,                       -- DRG权重
    drg_pay             REAL,                       -- DRG标准支付额
    -- 费用汇总（对齐医保结算清单医疗收费信息）
    medfee_sumamt       REAL,                       -- 医疗费总额
    fund_pay_sumamt     REAL,                       -- 医保统筹基金支付
    acct_pay_sumamt     REAL,                       -- 个人账户支付
    psn_part_amt        REAL,                       -- 个人负担总额
    cash_payamt         REAL,                       -- 个人现金支付
    -- 元数据
    data_source         TEXT,                       -- 数据来源标识
    imported_at         TEXT DEFAULT (datetime('now','localtime'))
);
```

### 4.3 费用明细行表（claim_line）

> 一条 claim_event 下有多条 claim_line。每行就是费用清单上的一个条目。

```sql
CREATE TABLE claim_line (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    feedetl_sn          TEXT NOT NULL,              -- 费用明细流水号（接口规范2301核心字段）
    setl_id             TEXT NOT NULL REFERENCES claim_event(setl_id),  -- 结算ID
    mdtrt_id            TEXT,                       -- 就诊ID（接口规范核心字段）
    -- 明细内容（对齐国家医保信息平台接口规范 2301 费用明细上传）
    fee_ocur_time       TEXT,                       -- 费用发生时间
    list_type           TEXT NOT NULL,              -- 目录类别: 11=西药, 12=中成药, 13=中药饮片, 21=诊疗项目, 31=医用耗材（med_chrgitm_type）
    med_list_name       TEXT,                       -- 医疗目录项目名称
    med_list_codg       TEXT,                       -- 医疗目录编码（CHS/CUC/项目编码）
    medins_list_codg    TEXT,                       -- 医药机构目录编码（院内编码）
    cnt                 REAL,                       -- 数量
    pric                REAL,                       -- 单价
    pric_ut             TEXT,                       -- 计价单位（次/日/部位等）
    det_amt             REAL,                       -- 明细金额（cnt × pric）
    chrgitm_lv          TEXT,                       -- 收费项目等级: 1=甲, 2=乙, 3=丙（含自费）
    -- 目录匹配结果（引擎预填）
    matched_catalog_id  INTEGER,                    -- 匹配到的目录ID
    match_confidence    REAL,                       -- 匹配置信度（0-1）
    match_method        TEXT,                       -- 匹配方式: exact/fuzzy/alias/code
    -- 医嘱与科室信息（对齐接口规范2301）
    bilg_drord_no       TEXT,                       -- 医嘱号
    drord_type          TEXT,                       -- 医嘱类别: 1=长期, 2=临时
    bilg_dept_codg      TEXT,                       -- 开单科室编码
    bilg_dept_name      TEXT,                       -- 开单科室名称
    bilg_dr_codg        TEXT,                       -- 开单医生编码
    bilg_drord_dr_name  TEXT,                       -- 开单医师姓名
    acord_dept_codg     TEXT,                       -- 受单科室编码
    acord_dept_name     TEXT,                       -- 受单科室名称
    orders_dr_codg      TEXT,                       -- 受单医生编码
    orders_dr_name      TEXT,                       -- 受单医生姓名
    -- 药品附加信息
    dosage_form         TEXT,                       -- 实际使用剂型
    tcmdrug_used_way    TEXT,                       -- 中药使用方式
    -- 耗材附加信息
    oprn_code_used      TEXT,                       -- 使用该耗材的手术编码（ICD-9-CM-3）
    used_qty            REAL,                       -- 实际使用数量
    -- 标志位（对齐接口规范2301出参）
    hosp_appr_flag      TEXT,                       -- 医院审批标志: 0=否, 1=是
    etip_flag           TEXT,                       -- 外检标志: 0=否, 1=是
    dscg_tkdrug_flag    TEXT,                       -- 出院带药标志: 0=否, 1=是
    matn_fee_flag       TEXT,                       -- 生育费用标志
    -- 清算与支付
    clr_type            TEXT,                       -- 清算类别: 11=门诊, 21=住院, 51=暂缓结算, 99=其他
    fund_pay_type       TEXT,                       -- 基金支付类型
    -- 元数据
    comb_no             TEXT,                       -- 组套编号
    memo                TEXT,                       -- 备注
    raw_data            TEXT,                       -- 原始JSON（保留完整数据备查）
    imported_at         TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_claim_line_setl ON claim_line(setl_id);
CREATE INDEX idx_claim_line_list_type ON claim_line(list_type);
```

### 4.4 审核结果表（audit_result）

> 每条违规/通过记录，记录完整的推理链（可追溯、可解释）。`rule_version` 字段记录审核时使用的规则版本，支持按版本回溯审核结果。

```sql
CREATE TABLE audit_result (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    setl_id             TEXT NOT NULL REFERENCES claim_event(setl_id),
    line_no             INTEGER,                    -- 触发行号（空=事件级规则）
    -- 规则信息
    rule_id             INTEGER REFERENCES rule_items(id),
    rule_code           TEXT,                       -- 规则编码
    rule_category       TEXT,                       -- 规则类别
    pillar              TEXT,                       -- 支柱来源（YP/HC/FW/BZ）
    stage               TEXT,                       -- 执行阶段（pre_check/end_check/post_audit）
    -- 判定结果
    verdict             TEXT NOT NULL,              -- pass / warning / violation
    severity            TEXT,                       -- 严重级别（明确违规/可疑/提示）
    -- 推理链
    matched_facts       TEXT,                       -- 匹配到的事实（JSON）
    rule_text           TEXT,                       -- 触发规则的原文
    reasoning           TEXT,                       -- 推理说明（自然语言）
    -- 处置
    action              TEXT,                       -- 建议处置（block/warn/tag/pass）
    -- 元数据
    engine_version      TEXT,                       -- 引擎版本
    rule_version        INTEGER DEFAULT 1,          -- 触发的规则版本号
    audited_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_audit_setl ON audit_result(setl_id);
CREATE INDEX idx_audit_verdict ON audit_result(verdict);
CREATE INDEX idx_audit_pillar ON audit_result(pillar);
```

---

## 五、代码架构：模块化规则引擎

> **设计定位**：将原单文件 `audit_engine.py` 拆分为多个职责明确的模块，实现关注点分离、依赖注入和配置外部化。

### 5.1 目录结构

```
engine/
├── __init__.py                # 对外API入口（兼容旧导入路径）
├── config.py                  # 配置管理（字段映射、日志级别、缓存策略）
├── logger.py                  # 日志配置
├── exceptions.py              # 自定义异常体系
├── cli.py                     # 命令行接口
├── models/                    # 数据模型层
│   ├── __init__.py
│   ├── claim.py               # ClaimEvent, ClaimLine（结算事件与费用明细）
│   └── result.py              # AuditResult（审核结果）
├── dsl/                       # 条件DSL解析层
│   ├── __init__.py
│   ├── evaluator.py           # ConditionEvaluator（条件评估器）
│   └── operators.py           # 运算符定义与注册机制
├── matcher/                   # 目录匹配层
│   ├── __init__.py
│   └── catalog.py             # CatalogMatcher（编码/名称/别名/模糊匹配）
├── core/                      # 审核引擎核心层
│   ├── __init__.py
│   ├── engine.py              # MedicareAuditEngine（主引擎入口）
│   ├── context.py             # ContextBuilder（上下文构建器）
│   └── reasoning.py           # DRGReasoning（推理说明生成）
└── repo/                      # 数据访问层
    ├── __init__.py
    └── sqlite_repo.py         # SQLiteRepository（数据库操作封装）
```

### 5.2 模块职责划分

| 模块 | 职责 | 核心类 | 行数 |
|------|------|--------|------|
| `models/claim.py` | 定义结算事件和费用明细的数据模型 | ClaimEvent, ClaimLine | 106 |
| `models/result.py` | 定义审核结果数据模型 | AuditResult | 20 |
| `dsl/operators.py` | 定义条件运算符及注册机制 | OperatorRegistry | 91 |
| `dsl/evaluator.py` | 解析并评估条件DSL | ConditionEvaluator | 80 |
| `matcher/catalog.py` | 目录匹配（编码/精确/别名/模糊） | CatalogMatcher | 108 |
| `core/context.py` | 构建审核上下文（派生48个计算字段） | ContextBuilder | 272 |
| `core/engine.py` | 审核引擎主入口 | MedicareAuditEngine | 241 |
| `core/reasoning.py` | DRG推理说明生成 | DRGReasoning | 24 |
| `repo/sqlite_repo.py` | 数据库访问层 | SQLiteRepository | 141 |
| `config.py` | 配置管理 | EngineConfig | 30 |

### 5.3 依赖关系

```
                    ┌─────────────────┐
                    │  MedicareAuditEngine  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ ContextBuilder│    │CatalogMatcher │    │DRGReasoning   │
└───────────────┘    └───────┬───────┘    └───────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  OperatorRegistry │   ConditionEvaluator│   SQLiteRepository│
└───────────────┘    └───────────────┘    └───────────────┘
```

### 5.4 关键设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **依赖注入** | MedicareAuditEngine | 通过构造函数注入 Repository，便于单元测试 Mock |
| **策略模式** | OperatorRegistry | 运算符动态注册，支持扩展新运算符 |
| **缓存模式** | 三级缓存 | 规则缓存 + 目录匹配缓存 + 条件解析缓存 |
| **外观模式** | engine/__init__.py | 统一对外接口，兼容旧导入路径 |

### 5.5 运算符注册机制

```python
# 注册运算符（支持动态扩展）
OperatorRegistry.register("eq", lambda a, b: a == b)
OperatorRegistry.register("contains", lambda a, b: b in str(a))

# 使用运算符
result = OperatorRegistry.get("eq")(value, expected)
```

### 5.6 配置管理

```python
class EngineConfig:
    DEFAULT_DB_PATH = "medicare_engine.db"
    LOG_LEVEL = "INFO"
    ENABLE_CACHE = True
    FIELD_MAPPING = {
        "age": "_calculate_age",
        "los": "_calculate_los",
        # ... 其他计算字段映射
    }
```

---

## 六、DRG/DIP 第四柱：支付合规性

> **设计定位**：四柱审核框架中，柱1-3 覆盖药品/耗材/项目的逐行合规性，柱4 覆盖 DRG/DIP 打包付费场景下的支付合规性。

### 6.1 为什么需要第四柱

截至2026年，全国超九成统筹地区已开展DRG/DIP支付改革，住院"按项目付费"占比已降至约1/4。审核重心已从"单项目费用审核"向"入组准确性审核"转移。

四柱审核框架：
```
┌──────────────────────────────────────────────────────────────────────┐
│                          四柱审核框架                                 │
│                                                                      │
│  柱1：药品目录限制    医保目录限定条件（适应症/性别/年龄/二线/疗程等） │
│                      + 中药饮片支付限定（ZY_YPZF, list_type=13）│
│  柱2：耗材使用合规    耗材与手术配对/适应症匹配/用量限制              │
│  柱3：项目收费合规    超标准/重复/分解收费 + 限就医方式/机构/频次     │
│  柱4：支付合规性      DRG入组准确性/高套/分解/低标/缩减               │
│                                                                      │
│  柱1-3：逐行审核（claim_line 级别）                                  │
│  柱4：事件级审核（claim_event 级别，需整单上下文）                   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 DRG 规则子表（drg_rules）

> 不是目录（不描述"是什么"），是规则（描述"怎么判"）。DRG 规则全部通过 `conditions` DSL 表达判定逻辑，阈值配置存放于 `threshold_config`。

```sql
CREATE TABLE drg_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name           TEXT NOT NULL,               -- 规则名称
    rule_type           TEXT NOT NULL,               -- 规则类型（见下表）
    -- 检测条件（JSON结构化）
    conditions          TEXT,                       -- JSON条件体
    -- 判定逻辑
    threshold_config    TEXT,                       -- 阈值配置（JSON）
    -- 归属
    pillar              TEXT DEFAULT 'drg',         -- 固定柱4
    stage               TEXT DEFAULT 'post_audit', -- DRG审核通常为事后
    severity            TEXT DEFAULT 'suspicious',  -- DRG问题多为"可疑"
    is_active           INTEGER DEFAULT 1,          -- 是否启用
    -- 来源
    evidence_source     TEXT,
    effective_date      TEXT,
    expired_date        TEXT,
    version             INTEGER DEFAULT 1,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

| rule_type | 说明 | 检测逻辑 |
|-----------|------|---------|
| GT | 高套分组 | 合并症编码数量异常多 / 主诊断权重偏离 |
| FJ | 分解住院 | 同一患者同病种 15天内再次住院 |
| DB | 低标入院 | 住院天数≤1天 且 费用低于门诊阈值 |
| SJ | 缩减服务 | 费用消耗指数远低于区域均值 |
| ZSBP | 诊断-手术不匹配 | 主诊断与主手术无临床关联 |
| PY | 分组漂移 | 同一病种入组权重时间序列异常波动 |

> **DRG 参考数据说明**：DRG 分组的参考标准（权重、标准住院天数、费用区间等）直接嵌入 `drg_rules.threshold_config` 或通过 rule_items 条件表达，不再维护独立的 `drg_reference` 表；分解住院检测直接基于 `claim_event` 表聚合查询，不再维护 `split_stay_tracking` 辅助表。

---

## 六、审核引擎执行流程（四柱 + 三阶段）

### 6.1 三阶段业务定义

| 阶段编码 | 业务名称 | 时机 | 可用数据 | 处置方式 |
|---------|---------|------|---------|---------|
| `pre_check` | 事前医嘱审核 | 医生开立医嘱时 | 患者信息+诊断+当前开立的单个项目 | 实时拦截或弹窗提醒 |
| `end_check` | 事中出科审核 | 患者出科/出院时 | 完整费用清单（全部明细行） | 标记可疑行，允许人工复核 |
| `post_audit` | 事后结算监管 | 结算完成后 | 完整结算+DRG分组+支付数据 | 生成审核报告，供飞检参考 |

### 6.2 级联加载机制（向下级联）

三阶段可用数据范围递增，因此规则按**向下级联**方式加载：

```
pre_check  → 仅加载 stage='pre_check' 规则（且 severity='violation'，不给医生弹不确定提醒）
end_check → 加载 stage IN ('pre_check','end_check') 规则（事前能查的事中也要查）
post_audit → 加载全量规则（pre_check + end_check + post_audit，最深度审核）
```

> **设计依据**：事前阶段可获取的数据（患者信息+诊断+单个项目），在事中、事后阶段必然也存在；
> 事中阶段可获取的数据（完整费用清单），在事后阶段必然也存在。
> 因此早期阶段的规则在后期阶段必然也能执行，按向下级联加载。

### 6.3 规则类别 × 阶段映射

| 阶段 | 规则类别 | 依据 |
|------|---------|------|
| **pre_check** (2155条) | YP_SYZ, YP_XB, YP_ETZY, YP_ETXZ, YP_NL, YP_JGJB, YP_CBXZ, YP_JYFS, YP_EXYY, YP_JYQD, FW_XMXB, FW_ETZY, NLXZ, HC_SP | 开单时即可判断（患者属性+诊断+单个项目） |
| **end_check** (1727条) | FW_XMHC, FW_BHGZ, FW_XMPC, FW_CFXZ, FW_DJZJ, FW_QZTJ, ZY_YPZF, HC_FY, HC_PD, HC_SL, HC_WH, FW_XMLC, YP_ZFLC | 需完整费用清单（跨行判断） |
| **post_audit** (5条) | HC_ZY, HC_ZF, BM_YY | 需结算+支付属性数据 |
| **DRG规则** (17条) | WRZ, DFSW, GQZ 等 | 需DRG分组+结算数据，仅事后触发 |

### 6.4 总体流程

```
输入：claim_event + claim_line（一组结算数据）
  │
  ├─ 阶段1：事前医嘱审核（pre_check）
  │    └─ 规则子集：stage='pre_check' AND severity='violation'
  │    └─ 处置：实时拦截或弹窗提醒
  │    └─ 柱1-3 逐行扫描
  │
  ├─ 阶段2：事中出科审核（end_check）
  │    └─ 规则子集：stage IN ('pre_check','end_check')
  │    └─ 处置：标记可疑行，允许人工复核
  │    └─ 柱1-3 逐行扫描 + 柱4 事件级预检
  │
  └─ 阶段3：事后结算监管（post_audit）
       └─ 规则子集：全量规则（pre_check + end_check + post_audit）
       └─ 处置：生成审核报告，供飞检参考
       └─ 柱1-3 逐行 + 柱4 深度分析（高套/分解/行为模式）
```

### 6.2 柱1-3 逐行审核逻辑（claim_line 级别）

```
对 claim_event 中的每一条 claim_line：
  │
  ├─ STEP 1：目录匹配
  │    └─ 根据 line_type + item_name/item_code → 匹配到三目录之一
  │    └─ 写入 claim_line.matched_catalog_id
  │
  ├─ STEP 2：柱判定（根据 line_type 分流）
  │    ├─ drug → 柱1：药品目录限制（限适应症/限性别/限年龄/限二线/限疗程等）
  │    ├─ consumable → 柱2：耗材使用合规（配对/适应症/用量）
  │    └─ project → 柱3：项目收费合规（超标准/重复/分解收费 + 限就医方式/限机构/限频次）
  │
  └─ STEP 3：生成 audit_result
       └─ 每条违规写入一行（推理链完整记录）
```

### 6.3 柱4 事件级审核逻辑（claim_event 级别）

```
对整个 claim_event：
  │
  ├─ DRG入组校验
  │    ├─ 主诊断是否灰码？（查 icd_10.is_gray_code）
  │    ├─ 主诊断与主手术匹配合理性（规则DSL判定）
  │    └─ MCC/CC 编码数量是否异常？（查 icd_10.is_mcc/is_cc）
  │
  ├─ 分解住院检测
  │    ├─ 聚合 claim_event：同一患者 + 主诊断前3位 + 15天内再入院
  │    └─ 超过阈值 → 标记
  │
  ├─ 低标入院检测
  │    ├─ 住院天数 ≤ 1天？
  │    ├─ 费用低于门诊同病种阈值？
  │    └─ 同时满足 → 标记
  │
  └─ 缩减服务检测
       ├─ 费用消耗指数 < 区域均值 × 0.5？
       ├─ 病历记录是否过于简略？
       └─ 同时满足 → 标记
```

---

## 七、完整 ER 关系总览

```
                              ┌──────────────────────┐
                              │    知识层（静态）      │
                              └──────────────────────┘
  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ YP│  │FW│  │unified_materi│  │icd_10 │
  │             │  │              │  │als           │  │              │
  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                │                 │                 │
         │    ┌───────────┴─────────────────┴─────────┐       │
         │    │          规则层（约束）                  │       │
         │    │                                       │       │
         ▼    ▼                                       ▼       ▼
  ┌────────────────────────────────────────────────────────────────┐
  │                        rule_items                                │
  │  drug_id ──► YP.id                                     │
  │  project_a_id ──► FW.id                             │
  │  project_b_id ──► FW.id (配对项目)                  │
  │  consumable_id ──► HC.id                          │
  │  diagnosis_codes ──► [icd_10 chs_code] (JSON)                   │
  │  conditions ──► {gender, age_min, age_max, visit_mode, ...}     │
  └────────────────────────────────────────────────────────────────┘
         │                 │                │                 │
         │    ┌────────────┴────────────────┘                 │
         │    │          桥表（仅项目）                          │
         ▼    ▼                                                 │
  ┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐   │
  │project_catalo│ │project_catalog_a│ │project_connota-  │   │
  │g_codes       │ │liases           │ │tion              │   │
  └──────────────┘ └──────────────────┘ └──────────────────┘   │
                                                               │
  ┌──────────────────┐                                         │
  │     icd_9        │                                         │
  └──────────────────┘                                         │
                                                               │
                              ┌──────────────────────┐        │
                              │   审核输入（动态）      │        │
                              └──────────────────────┘        │
  ┌────────────────────────────────────┐                       │
  │          claim_event               │                       │
  │  main_diag_code ──► icd_10.chs_code                      │
  │  main_oprn_code ──► icd_9.chs_code                        │
  │  drg_codg ──► (外部分组器结果，不存参考表)                  │
  └─────────────┬──────────────────────┘                       │
                │ 1:N                                           │
  ┌─────────────▼──────────────────────┐                       │
  │          claim_line                 │                       │
  │  matched_catalog_id ──► 三目录之一  │                       │
  └─────────────┬──────────────────────┘                       │
                │ 规则执行                                      │
                ▼                                               │
  ┌────────────────────────────────────┐                       │
  │        audit_result                │                       │
  │  rule_id ──► rule_items            │                       │
  │  setl_id ──► claim_event.setl_id   │                       │
  │  rule_version ──► rule_items.versi │                       │
  │  on                              │                       │
  └────────────────────────────────────┘                       │
                                                                │
  ┌────────────────────────────────────┐                       │
  │      规则版本管理（元数据）           │                       │
  ├──────────────┬─────────────────────┤                       │
  │rule_changelog│ │rule_set_snapshot  │                       │
  │  (变更日志)   │ │  (规则集快照)      │                       │
  └──────────────┴─────────────────────┘                       │
                                                                │
                              ┌──────────────────────┐        │
                              │  DRG第四柱（事件级）    │        │
                              └──────────────────────┘        │
  ┌──────────────────────────────────────────────────────────┐  │
  │                       drg_rules                          │  │
  │  规则类型: GT/FJ/DB/SJ/ZSBP/PY  │  │
  │  阈值配置存于 threshold_config (JSON)                     │  │
  └──────────────────────────────────────────────────────────┘  │
```

---

## 八、数据导入与同步机制

> **设计定位**：知识层数据（三目录、ICD编码、DRG参考标准）需要定期从国家医保局数据源同步。本节定义各数据源的导入路径、格式和更新策略。

### 8.1 数据集成映射表（Data Integration Mapping）

| 目标实体 | 权威数据源 | 采集通道 | 同步周期 | 数据形态 |
|---------|-----------|---------|---------|---------|
| YP | 国家医保药品目录（2025版） | 国家医保信息业务编码标准数据库（code.nhsa.gov.cn）API/批量下载 | 年度基线 + 月度增量补丁 | 结构化（Excel/CSV/API JSON） |
| FW | 医疗服务价格项目立项指南（已发布17批，609个收费编码） | 国家医保局官网政策文件公开发布 | 按批次触发（每批新增） | 半结构化（PDF → OCR识别 → JSON提取） |
| HC | 医保医用耗材分类与代码（CUC，20位标准编码）+ 基本物耗/特殊功能耗材目录 | 国家医保信息业务编码标准数据库 + 地方医保局政策文件 | 季度全量刷新 | 结构化（Excel/CSV/API JSON） |
| icd_10 | 疾病诊断分类与代码（ICD-10 医保版2.0） | 国家医保信息业务编码标准数据库 + 临床路径管理系统 DOM抓取 | 年度基线更新 | 结构化（Excel/CSV）+ 浏览器自动化抓取 JSON |
| icd_9 | 手术操作分类与代码（ICD-9-CM-3 医保版） | 国家医保信息业务编码标准数据库 + 临床路径管理系统 DOM抓取 | 年度基线更新 | 结构化（Excel/CSV）+ 浏览器自动化抓取 JSON |
| rule_items | 智能监管知识库、规则库（2025年版，88类规则，24.7万条知识点） | 国家医保局分批公开发布（已至第17批） | 每1–2月一批次增量发布 | 非结构化（PDF/Excel）→ 人工校验 → 结构化JSON |
| drg_rules | CHS-DRG 支付规则（2.0版） | 国家医保局官网分组器标准文件 + 地方实施细则 | 版本级更新（跨版本差异较大） | 结构化（Excel/CSV）→ 规则DSL转换 |

### 8.2 规则导入管道（rule_items）

国家医保局"两库"知识点达24.7万条，逐条人工录入不现实。建议设计半自动导入管道：

```
国家医保局发布（PDF/Excel）
    │
    ▼
【步骤1】结构化提取（Python脚本）
    ├─ PDF解析 → 表格提取
    ├─ 规则文本 → NLP实体识别（药品名/项目名/诊断名）
    └─ 输出：raw_rules.json（含规则原文、关联实体、限制条件）
    │
    ▼
【步骤2】实体匹配（人工复核 + 模糊匹配）
    ├─ 药品名 → YP.drug_name（fuzzy匹配）
    ├─ 项目名 → FW.name（fuzzy匹配）
    ├─ 诊断名 → icd_10.name（fuzzy匹配）
    └─ 未匹配项 → 人工标注 → 反馈至目录表
    │
    ▼
【步骤3】条件结构化（规则引擎DSL生成）
    ├─ "限流感患者" → {"field": "claim_event.primary_diagnosis", "op": "in", "value": ["J11.1", "J10.1"]}
    ├─ "限二线用药" → {"field": "claim_event.first_line_used", "op": "eq", "value": true}
    └─ "限三级医院" → {"field": "claim_event.hospital_level", "op": "eq", "value": "三级"}
    │
    ▼
【步骤4】人工审核与入库
    ├─ 规则评审小组逐条确认
    ├─ 写入 rule_items（is_active=0，待启用）
    └─ 批量启用（UPDATE rule_items SET is_active=1 WHERE batch='第X批'）
```

### 8.3 目录增量更新策略

```sql
-- 药品目录增量更新示例
INSERT INTO YP (drug_name, dosage_form, atc_code, payment_type, evidence_source)
SELECT drug_name, dosage_form, atc_code, payment_type, '2025版_月度补丁'
FROM staging_drug_update
WHERE drug_name NOT IN (SELECT drug_name FROM YP);

-- 标记变更（用于审计追踪）
UPDATE YP
SET payment_type = staging.payment_type,
    updated_at = datetime('now','localtime')
FROM staging_drug_update staging
WHERE YP.drug_name = staging.drug_name
  AND YP.payment_type != staging.payment_type;

-- ICD 编码补充导入（浏览器自动化抓取 → 合并到 icd_10/icd_9）
INSERT OR IGNORE INTO icd_10 (code, name, chapter, chapter_name, evidence_source)
SELECT code, name, category, '', '抓取补充'
FROM staging_icd10
WHERE code NOT IN (SELECT code FROM icd_10);

INSERT OR IGNORE INTO icd_9 (code, name, category, evidence_source)
SELECT code, name, category, '抓取补充'
FROM staging_icd9
WHERE code NOT IN (SELECT code FROM icd_9);
```

### 8.4 规则变更日志（rule_changelog）

```sql
CREATE TABLE rule_changelog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         INTEGER NOT NULL REFERENCES rule_items(id),
    change_type     TEXT NOT NULL,              -- create / update / deactivate / delete
    changed_fields  TEXT,                       -- JSON，记录变更字段的 before/after
    changed_by      TEXT,                       -- 操作人
    changed_at      TEXT DEFAULT (datetime('now','localtime'))
);
```

> 每次 rule_items 的 INSERT/UPDATE/DELETE 通过触发器自动写入 changelog，实现规则全生命周期追溯。

---

## 九、规则版本管理

> **设计定位**：实现规则的版本控制、时间旅行查询和可追溯审计，解决规则变更后的"当时用的是哪版规则"问题。

### 9.1 核心设计思路

| 设计要点 | 实现方式 | 说明 |
|---------|---------|------|
| **有效日期过滤** | `effective_date <= audit_date AND (expired_date IS NULL OR expired_date > audit_date)` | 过期规则自动不加载 |
| **版本演进** | 修订时保留旧行（设 `is_active=0, expired_date=当前日期`），插入新行（`version+1`） | 不覆写历史，支持回溯 |
| **规则集快照** | `rule_set_snapshot` 表标记规则集状态 | 支持版本回滚 |
| **变更追踪** | 触发器自动写入 `rule_changelog` | 记录每个字段的 before/after |
| **审核追溯** | `audit_result.rule_version` 记录使用的规则版本 | 可回溯"当时用的是哪版规则" |

### 9.2 规则集快照表（rule_set_snapshot）

```sql
CREATE TABLE rule_set_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_name   TEXT NOT NULL UNIQUE,    -- 快照名称，如 v2026Q3
    snapshot_desc   TEXT,                   -- 快照描述
    rule_count      INTEGER,                -- 快照时活跃规则数
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    created_by      TEXT,
    effective_date  TEXT,                   -- 生效日期
    expired_date    TEXT                    -- 失效日期（空=当前活跃）
);
CREATE INDEX idx_snapshot_active ON rule_set_snapshot(expired_date);
```

### 9.3 版本更新流程

```
┌─────────────────────────────────────────────────────────────┐
│                    规则版本更新流程                          │
├─────────────────────────────────────────────────────────────┤
│  PUT /api/v1/rules/{rule_code}/version                     │
│                                                             │
│  1. 查询当前活跃规则（rule_code + is_active=1 + 未过期）     │
│         ↓                                                   │
│  2. 将旧行标记为过期: is_active=0, expired_date=当前日期     │
│         ↓                                                   │
│  3. 插入新版本行: version=old_version+1, is_active=1        │
│         ↓                                                   │
│  4. 触发器自动写入 rule_changelog（change_type=version_upgrade）│
└─────────────────────────────────────────────────────────────┘
```

### 9.4 版本管理 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/rules/snapshots` | 获取规则集快照列表 |
| POST | `/api/v1/rules/snapshots` | 创建规则集快照 |
| GET | `/api/v1/rules/changelog` | 获取规则变更日志（支持按 rule_id/rule_code 筛选） |
| PUT | `/api/v1/rules/{rule_code}/version` | 更新规则版本（保留旧版本，插入新版本） |

### 9.5 时间旅行查询

审核引擎支持按历史日期查询当时生效的规则：

```python
# 默认使用当前日期
engine = MedicareAuditEngine(db_path="medicare_engine.db")
results = engine.audit_claim(claim, lines)

# 指定审核日期（时间旅行）
results = engine.audit_claim(claim, lines, audit_date="2026-01-15")
```

### 9.6 改进的 changelog 触发器

触发器现在捕获全部字段的变更，而非单个字段：

```sql
CREATE TRIGGER trg_rule_update AFTER UPDATE ON rule_items
BEGIN
    INSERT INTO rule_changelog (rule_id, rule_code, change_type, changed_fields, changed_by)
    VALUES (NEW.id, NEW.rule_code, 
        CASE WHEN OLD.version != NEW.version THEN 'version_upgrade' ELSE 'update' END,
        json_object(
            'rule_name', json_object('before', OLD.rule_name, 'after', NEW.rule_name),
            'pillar', json_object('before', OLD.pillar, 'after', NEW.pillar),
            'severity', json_object('before', OLD.severity, 'after', NEW.severity),
            'conditions', json_object('before', OLD.conditions, 'after', NEW.conditions),
            'version', json_object('before', OLD.version, 'after', NEW.version),
            ...
        ), 'system');
END;
```
