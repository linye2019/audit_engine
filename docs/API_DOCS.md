# 医保智能审核引擎 — API 接口文档

> **版本**: 1.0.0  
> **日期**: 2026-06-28  
> **基础URL**: `http://{host}:8000`  
> **交互式文档**: `http://{host}:8000/docs` (Swagger UI) / `http://{host}:8000/redoc` (ReDoc)  
> **编码标准**: 国家医保局《医疗保障信息平台定点医药机构接口规范》V1.1.85

---

## 一、概述

### 1.1 四柱审核框架

| 柱 | 名称 | 审核级别 | 覆盖规则 |
|---|---|---|---|
| 柱1 | 药品目录限制 | 逐行(claim_line) | 适应症/性别/年龄/二线用药/疗程/险种 |
| 柱2 | 耗材使用合规 | 逐行(claim_line) | 审批/配对手术/用量/载药/重复计费 |
| 柱3 | 项目收费合规 | 逐行(claim_line) | 互斥/拆分/包含/定价/频次/材料 |
| 柱4 | 支付合规性 | 事件级(claim_event) | 高套分组/分解住院/低标入院/费用偏离 |

### 1.2 三阶段审核

| 阶段 | 接口 | 场景 | 规则范围 | 响应要求 |
|---|---|---|---|---|
| 事前提醒 | `POST /api/v1/audit/precheck` | 医生开单时 | 明确违规+高置信度 | < 200ms |
| 事中控制 | `POST /api/v1/audit/end_check` | 结算前 | 全量规则(柱1-3+柱4预检) | < 2s |
| 事后监管 | `POST /api/v1/audit/postaudit` | 结算后 | 全量规则+DRG深度分析 | < 5s |

### 1.3 通用响应格式

所有接口返回 JSON，包含 `code` 字段：

```json
{
  "code": 0,          // 0=成功, 非0=失败
  "message": "success",
  ...
}
```

---

## 二、审核接口

### 2.1 事前提醒

**场景**: 医生在HIS系统开处方/医嘱时实时调用，检查拟开立项目是否合规。

```
POST /api/v1/audit/precheck
Content-Type: application/json
```

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| gend | string | 否 | 性别: 1=男, 2=女 |
| brdy | string | 否 | 出生日期 YYYY-MM-DD |
| med_type | string | 否 | 医疗类别(默认11=门诊) |
| hosp_lv | string | 否 | 医院等级 |
| dept | string | 否 | 科室 |
| insutype | string | 否 | 险种: 310=职工, 390=居民 |
| main_diag_code | string | 否 | 主诊断ICD-10编码 |
| main_diag_name | string | 否 | 主诊断名称 |
| diag_codes | string[] | 否 | 次诊断编码列表 |
| main_oprn_code | string | 否 | 主手术编码 |
| items | object[] | **是** | 拟开立项目列表 |

**items 字段**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| list_type | string | **是** | 11=西药, 12=中成药, 13=中药饮片, 21=诊疗项目, 31=耗材 |
| med_list_name | string | **是** | 项目名称 |
| med_list_codg | string | 否 | 目录编码 |
| cnt | number | 否 | 数量(默认1) |
| pric | number | 否 | 单价 |
| chrgitm_lv | string | 否 | 收费等级: 1=甲, 2=乙, 3=自费 |
| hosp_appr_flag | string | 否 | 审批标志: 0=否, 1=是 |
| oprn_code_used | string | 否 | 耗材关联手术编码 |

**响应**:

| 字段 | 类型 | 说明 |
|---|---|---|
| decision | string | **pass**(放行) / **warn**(提醒) / **block**(拦截) |
| total_items | int | 检查项目数 |
| total_alerts | int | 触发规则数 |
| block_count | int | 拦截级规则数 |
| warn_count | int | 提醒级规则数 |
| alerts | object[] | 触发规则详情列表 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/audit/precheck \
  -H "Content-Type: application/json" \
  -d '{
    "gend": "1",
    "brdy": "1980-01-01",
    "med_type": "11",
    "hosp_lv": "2",
    "main_diag_code": "I10",
    "main_diag_name": "高血压",
    "items": [
      {"list_type": "11", "med_list_name": "艾塞那肽注射液", "cnt": 1, "pric": 200}
    ]
  }'
```

**响应示例**:

```json
{
  "code": 0,
  "message": "success",
  "decision": "block",
  "total_items": 1,
  "total_alerts": 1,
  "block_count": 1,
  "warn_count": 0,
  "alerts": [
    {
      "claim_id": "PRECHECK_20260628164834413065",
      "line_no": 1,
      "rule_id": 217,
      "rule_code": "DRUG-DRU-0002",
      "rule_category": "YP_SYZ",
      "pillar": "YP",
      "verdict": "violation",
      "severity": "violation",
      "reasoning": "该药品限2型糖尿病患者使用",
      "action": "block",
      "matched_facts": {
        "drug_id": 167,
        "conditions_checked": [
          {"claim_line.med_list_name": "艾塞那肽注射液"},
          {"claim_event.diag_codes": "E11"}
        ]
      }
    }
  ]
}
```

---

### 2.2 事中控制

**场景**: 患者结算前调用，提交完整结算单进行全量审核（含跨行互斥判断）。

```
POST /api/v1/audit/end_check
Content-Type: application/json
```

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| claim_event | object | **是** | 结算事件（完整字段见2.4） |
| claim_lines | object[] | **是** | 费用明细行列表 |
| persist | boolean | 否 | 是否持久化(默认true) |

**响应**:

| 字段 | 类型 | 说明 |
|---|---|---|
| setl_id | string | 结算ID |
| stage | string | 审核阶段 |
| total_lines | int | 明细行数 |
| total_results | int | 审核结果数 |
| violation_count | int | 明确违规数 |
| warning_count | int | 可疑提示数 |
| has_block | boolean | 是否存在拦截级规则 |
| results | object[] | 审核结果列表 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/audit/end_check \
  -H "Content-Type: application/json" \
  -d '{
    "claim_event": {
      "setl_id": "SETL_2026_001",
      "med_type": "21",
      "gend": "1",
      "brdy": "1950-01-01",
      "hosp_lv": "2",
      "main_diag_code": "I21",
      "main_diag_name": "急性心肌梗死",
      "adm_date": "2026-06-01",
      "dscg_date": "2026-06-10",
      "inhosp_days": 10,
      "medfee_sumamt": 50000
    },
    "claim_lines": [
      {
        "list_type": "31",
        "med_list_name": "心脏支架",
        "cnt": 1, "pric": 15000, "det_amt": 15000,
        "hosp_appr_flag": "0"
      },
      {
        "list_type": "11",
        "med_list_name": "阿司匹林肠溶片",
        "cnt": 10, "pric": 5, "det_amt": 50
      }
    ],
    "persist": true
  }'
```

**响应示例**:

```json
{
  "code": 0,
  "message": "success",
  "setl_id": "SETL_2026_001",
  "stage": "end_check",
  "total_lines": 2,
  "total_results": 3,
  "violation_count": 2,
  "warning_count": 1,
  "info_count": 0,
  "has_block": true,
  "results": [
    {
      "line_no": 1,
      "rule_code": "CONS-GEN-001",
      "rule_category": "HC_SP",
      "pillar": "HC",
      "verdict": "violation",
      "reasoning": "高值耗材（支架类）使用前需完成医院审批",
      "action": "block"
    },
    {
      "line_no": 1,
      "rule_code": "CONS-PAIR-001",
      "rule_category": "HC_PD",
      "pillar": "HC",
      "verdict": "violation",
      "reasoning": "心脏支架使用需关联心血管手术编码(oprn_code_used)",
      "action": "block"
    },
    {
      "line_no": null,
      "rule_code": "高套分组检测",
      "rule_category": "GT",
      "pillar": "BZ",
      "verdict": "warning",
      "reasoning": "患者 SETL_2026_001 合并症编码数量(0个)异常",
      "action": "tag"
    }
  ]
}
```

---

### 2.3 事后监管

**场景**: 结算后调用，执行全量规则 + DRG深度分析。

```
POST /api/v1/audit/postaudit
```

请求格式与事中控制相同（`claim_event` + `claim_lines` + `persist`），区别在于执行 `post_audit` 阶段规则（含DRG深度分析：高套分组/分解住院/低标入院/费用偏离/诊断手术不匹配等）。

---

### 2.4 结算事件字段说明 (claim_event)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| setl_id | string | **是** | 结算ID（唯一标识） |
| mdtrt_id | string | 否 | 就诊ID |
| psn_no | string | 否 | 人员编号 |
| psn_name | string | 否 | 姓名 |
| gend | string | 否 | 性别: 1=男, 2=女, 0=未知 |
| brdy | string | 否 | 出生日期 YYYY-MM-DD |
| insutype | string | 否 | 险种: 310=职工医保, 390=居民医保 |
| med_type | string | **是** | 医疗类别(见枚举表) |
| adm_date | string | 否 | 入院日期 |
| dscg_date | string | 否 | 出院日期 |
| inhosp_days | int | 否 | 实际住院天数 |
| hosp_lv | string | 否 | 医院等级(见枚举表) |
| dept | string | 否 | 科室 |
| main_diag_code | string | 否 | 主诊断ICD-10编码 |
| main_diag_name | string | 否 | 主诊断名称 |
| diag_codes | string[] | 否 | 次诊断编码列表 |
| main_oprn_code | string | 否 | 主手术ICD-9-CM-3编码 |
| drg_codg | string | 否 | DRG病组编码 |
| drg_wt | float | 否 | DRG权重 |
| drg_pay | float | 否 | DRG标准支付额 |
| medfee_sumamt | float | 否 | 医疗费总额 |
| fund_pay_sumamt | float | 否 | 医保统筹基金支付 |

### 2.5 费用明细行字段说明 (claim_line)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| setl_id | string | 否 | 结算ID(可从claim_event继承) |
| feedetl_sn | string | 否 | 费用明细流水号 |
| list_type | string | **是** | 目录类别(见枚举表) |
| med_list_name | string | **是** | 项目名称 |
| med_list_codg | string | 否 | 目录编码 |
| cnt | float | 否 | 数量 |
| pric | float | 否 | 单价 |
| det_amt | float | 否 | 明细金额 |
| chrgitm_lv | string | 否 | 收费等级: 1=甲, 2=乙, 3=自费 |
| hosp_appr_flag | string | 否 | 审批标志: 0=否, 1=是 |
| oprn_code_used | string | 否 | 耗材关联手术编码 |
| bilg_dept_name | string | 否 | 开单科室名称 |
| bilg_drord_dr_name | string | 否 | 开单医师姓名 |

---

### 2.6 查询审核结果

```
GET /api/v1/audit/results/{setl_id}
```

根据结算ID查询已持久化的审核结果。

**响应示例**:

```json
{
  "code": 0,
  "setl_id": "SETL_2026_001",
  "total": 3,
  "results": [...]
}
```

---

## 三、目录查询接口

### 3.1 药品目录查询

```
GET /api/v1/catalog/drug?keyword=阿司匹林&limit=20&offset=0
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| keyword | string | 空 | 名称或编码模糊匹配 |
| limit | int | 20 | 返回条数(1-200) |
| offset | int | 0 | 偏移量 |

### 3.2 诊疗项目目录查询

```
GET /api/v1/catalog/project?keyword=CT&limit=20&offset=0
```

### 3.3 耗材目录查询

```
GET /api/v1/catalog/consumable?keyword=支架&limit=20&offset=0
```

---

## 四、耗材目录批量导入

**场景**: 补充耗材目录数据。耗材目录当前数据较少，第三方可通过此接口批量导入耗材数据，导入后即可被柱2审核规则匹配使用。

```
POST /api/v1/catalog/consumable/import
Content-Type: application/json
```

**请求参数**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| consumables | object[] | **是** | 耗材列表 |
| skip_existing | boolean | 否 | 是否跳过已存在(默认true) |

**consumables 字段**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| generic_name | string | **是** | 通用名(唯一键) |
| ccode | string | 否 | CUC编码(20位) |
| category | string | 否 | 分类 |
| payment_type | string | 否 | 甲/乙类 |
| payment_ratio | float | 否 | 自付比例 |
| drug_loaded | int | 否 | 是否载药: 0=否, 1=是 |
| drug_component | string | 否 | 载药成分 |
| evidence_source | string | 否 | 数据来源 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/catalog/consumable/import \
  -H "Content-Type: application/json" \
  -d '{
    "consumables": [
      {
        "generic_name": "冠脉药物洗脱支架",
        "ccode": "CUC010503001",
        "category": "心血管介入耗材",
        "payment_type": "乙类",
        "payment_ratio": 0.2,
        "drug_loaded": 1,
        "drug_component": "雷帕霉素"
      },
      {
        "generic_name": "人工关节髋关节假体",
        "ccode": "CUC020401001",
        "category": "骨科植入物",
        "payment_type": "乙类"
      }
    ],
    "skip_existing": true
  }'
```

**响应示例**:

```json
{
  "code": 0,
  "message": "导入完成: 新增 2 条, 跳过 0 条, 错误 0 条",
  "inserted": 2,
  "skipped": 0,
  "errors": []
}
```

---

## 五、规则查询接口

### 5.1 规则列表

```
GET /api/v1/rules?pillar=drug&stage=pre_check&category=YP_SYZ&limit=50
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| pillar | string | 空 | YP/HC/FW/BZ |
| stage | string | 空 | pre_check/end_check/post_audit |
| category | string | 空 | 规则大类(见下表) |
| active_only | bool | true | 仅返回启用规则 |
| limit | int | 50 | 返回条数(1-500) |
| offset | int | 0 | 偏移量 |

### 5.2 规则详情

```
GET /api/v1/rules/{rule_id}
```

返回规则完整信息，含条件DSL（conditions JSON）。

### 5.3 规则大类对照表

| rule_category | 柱 | 说明 |
|---|---|---|
| YP_SYZ | 柱1 | 药品限适应症 |
| YP_JGJB | 柱1 | 药品限机构级别 |
| YP_EXYY | 柱1 | 限二线用药 |
| YP_CBXZ | 柱1 | 限险种 |
| YP_NL | 柱1 | 限年龄 |
| YP_ZFLC | 柱1 | 限支付疗程 |
| FW_XMHC | 柱3 | 项目互斥 |
| FW_CFXZ | 柱3 | 拆分限制 |
| FW_BHGZ | 柱3 | 包含规则 |
| FW_DJZJ | 柱3 | 定价规则 |
| FW_XMPC | 柱3 | 频次限制 |
| HC_WH | 柱3 | 材料规则 |
| HC_SP | 柱2 | 耗材审批 |
| HC_PD | 柱2 | 耗材-手术配对 |
| HC_SL | 柱2 | 耗材用量限制 |
| HC_FY | 柱2 | 重复计费 |
| GT | 柱4 | 高套分组 |
| FJ | 柱4 | 分解住院 |
| DB | 柱4 | 低标入院 |

---

## 六、ICD编码查询

> 支持编码前缀模糊匹配。`icd_10` 存储亚目级编码（如 `I21`），`icd_9` 存储二位码（如 `36.0`），查询细目级编码（如 `I21.0`、`36.07`）时通过 `LIKE` 前缀匹配返回上级编码。

### 6.1 ICD-10诊断编码

```
GET /api/v1/icd10/search?keyword=J11&limit=20
GET /api/v1/icd10/search?keyword=急性心肌梗死&limit=10
```

### 6.2 ICD-9-CM-3手术编码

```
GET /api/v1/icd9/search?keyword=36.06&limit=20
GET /api/v1/icd9/search?keyword=支架&limit=10
```

---

## 七、系统接口

### 7.1 健康检查

```
GET /api/v1/health
```

```json
{
  "code": 0,
  "status": "healthy",
  "db_path": "medicare_engine.db",
  "rule_count": 349
}
```

### 7.2 数据库统计

```
GET /api/v1/stats
```

```json
{
  "code": 0,
  "tables": {
    "YP": 3631,
    "FW": 956,
    "consumables": 6,
    "rule_items": 349,
    "icd_10": 2453,
    "icd_9": 1271,
    "claim_event": 50,
    "claim_line": 382,
    "audit_result": 2664
  }
}
```

---

## 八、枚举值对照表

### 8.1 医疗类别 (med_type)

| 代码 | 说明 |
|---|---|
| 11 | 普通门诊 |
| 13 | 急诊 |
| 14 | 门诊慢特病 |
| 21 | 普通住院 |
| 24 | 急诊转住院 |
| 26 | 单病种住院 |
| 28 | 日间手术 |

### 8.2 目录类别 (list_type)

| 代码 | 说明 | 审核柱 |
|---|---|---|
| 11 | 西药 | 柱1(药品) |
| 12 | 中成药 | 柱1(药品) |
| 13 | 中药饮片 | 柱1(药品) |
| 21 | 诊疗项目 | 柱3(项目) |
| 31 | 医用耗材 | 柱2(耗材) |

### 8.3 性别 (gend)

| 代码 | 说明 |
|---|---|
| 0 | 未知 |
| 1 | 男 |
| 2 | 女 |
| 9 | 未说明 |

### 8.4 医院等级 (hosp_lv)

| 代码 | 说明 |
|---|---|
| 1 | 三级特等 |
| 2 | 三级甲等 |
| 3 | 三级乙等 |
| 5 | 二级甲等 |
| 6 | 二级乙等 |
| 8 | 一级甲等 |
| 11 | 无等级 |

### 8.5 审核结果字段

| 字段 | 值 | 说明 |
|---|---|---|
| verdict | pass | 通过 |
| | warning | 可疑 |
| | violation | 违规 |
| severity | violation | 明确违规 |
| | suspicious | 可疑 |
| | info | 提示 |
| action | block | 拦截 |
| | warn | 提醒 |
| | tag | 标记 |
| | pass | 放行 |
| pillar | drug | 柱1(药品) |
| | consumable | 柱2(耗材) |
| | project | 柱3(项目) |
| | drg | 柱4(支付) |

---

## 九、部署与启动

### 9.1 环境要求

- Python 3.10+
- 依赖: `pip install -r requirements.txt`

### 9.2 启动命令

```bash
# 方式1: 直接运行
python3 api_server.py

# 方式2: uvicorn (推荐生产环境)
uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4

# 方式3: 指定数据库路径
MEDICARE_DB_PATH=/data/medicare_engine.db python3 api_server.py
```

### 9.3 交互式文档

启动后访问：
- **Swagger UI**: `http://localhost:8000/docs` — 可在线测试所有接口
- **ReDoc**: `http://localhost:8000/redoc` — 可读性更好的文档展示
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` — 可导入Postman等工具

---

## 十、对接建议

### 10.1 事前提醒对接流程

```
HIS系统开单 → 调用 precheck API → decision=block? 
    → 是: 弹窗拦截，禁止提交
    → 否(warn): 弹窗提醒，允许继续
    → 否(pass): 直接放行
```

### 10.2 事中控制对接流程

```
结算前 → 组装完整结算单 → 调用 end_check API → has_block?
    → 是: 暂停结算，转人工复核
    → 否: 允许结算，结果存档供事后分析
```

### 10.3 耗材数据补充

耗材目录当前数据量较少，建议通过以下方式补充：

1. **批量导入**: 调用 `POST /api/v1/catalog/consumable/import` 接口，从医保局耗材编码目录批量导入
2. **增量更新**: 导入时设置 `skip_existing=true`，仅新增不覆盖
3. **导入后即时生效**: 导入的耗材数据立即可被柱2审核规则匹配

---

## 附录: 审核结果推理链示例

每条审核结果包含完整的推理链，便于人工复核：

```json
{
  "rule_code": "DRUG-DRU-0002",
  "rule_category": "YP_SYZ",
  "verdict": "violation",
  "severity": "violation",
  "reasoning": "该药品限2型糖尿病患者使用",
  "matched_facts": {
    "drug_id": 167,
    "conditions_checked": [
      {"claim_line.med_list_name": "艾塞那肽注射液"},
      {"claim_event.diag_codes": "E11"}
    ]
  },
  "rule_text": "{\"logic\":\"AND\",\"conditions\":[{\"field\":\"claim_line.med_list_name\",\"op\":\"contains\",\"value\":\"艾塞那肽注射液\"},{\"field\":\"claim_event.diag_codes\",\"op\":\"not_regex\",\"value\":\"E11\"}]}",
  "action": "block"
}
```

- `matched_facts.conditions_checked`: 引擎实际检查的每个条件及其值
- `rule_text`: 触发规则的原始条件DSL（JSON格式）
- `reasoning`: 自然语言推理说明
