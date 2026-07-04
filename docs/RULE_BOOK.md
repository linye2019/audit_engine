# 医保智能审核引擎 — 规则手册 (Rulebook)

> 统一规则编码注册中心。所有规则的分类、编码、检出逻辑、条件 DSL 模板的总览。

---

## 一、规则体系总览

### 1.1 四阶段级联

| 阶段 | 业务名称 | 时机 | 可用数据 |
|------|---------|------|---------|
| `pre_check` | 事前医嘱审核 | 医生开立医嘱时 | 患者信息 + 诊断 + 当前单个项目 |
| `mid_check` | 在院日终审核 | 住院期间每晚跑累计明细 | 累计费用明细（不含结算） |
| `end_check` | 出科审核 | 患者出院/出科时 | 完整费用清单 |
| `post_audit` | 事后结算监管 | 结算完成后 | 完整结算 + DRG 分组 + 支付数据 |

> **级联机制**：`pre_check` → `mid_check` → `end_check` → `post_audit`，早期阶段的规则在后期阶段必然也能执行。

### 1.2 四柱分类

| 柱 | 编码 | 范围 | 审核粒度 |
|----|------|------|---------|
| 柱1 药品目录限制 | **YP** | 西药/中成药/中药饮片 | 逐行 |
| 柱2 耗材使用合规 | **HC** | 基本物耗/普通耗材/特殊功能耗材 | 逐行 |
| 柱3 项目收费合规 | **FW** | 诊疗项目收费合规 | 逐行 |
| 柱4 支付合规性 | **BZ** | DRG/DIP 入组准确性/费用偏离 | 事件级 |

### 1.3 规则数据量

| 维度 | 数值 |
|------|------|
| 活跃规则总量 | **3,887 条** |
| DRG 规则 | **17 条** |
| 规则来源 | 两库 3,487条 + 立项指南 218条 + 目录限定 226条 |
| 药品 ATC 覆盖率 | 98.3% |

---

## 二、码体系

### 2.1 来源编码

| 来源编码 | 来源名称 | 规则数 |
|---------|---------|--------|
| `GJ01`~`GJ17` | 国家两库第N批 | 3,487 |
| `LXZN` | 立项指南 | 218 |
| `MLXD` | 目录限定 | 226 |
| `TYGZ` | 通用规则 | 7 |
| `CSZZ` | 测试种子 | 5 |

### 2.2 规则编码格式

```
{前缀}-{来源}-{编号}

YP-XB-GJ01-0001
│  │    │     └── 序号
│  │    └──────── 来源批次
│  └───────────── 规则子类
└──────────────── 所属柱前缀
```

| 前缀 | 含义 |
|------|------|
| `YP` | 药品类规则 |
| `XM` | 医疗服务项目类规则 |
| `HC` | 耗材类规则 |
| `ZY` | 中药类规则 |
| `DRG` | DRG 支付规则 |

---

## 三、柱1：药品类规则（YP）

### 3.1 规则类别一览

| 编码 | 原英文名 | 含义 | 规则数 | 阶段 | 严重级别 |
|------|---------|------|--------|------|---------|
| **YP_SYZ** | drug_indication | 药品限适应症 | 734 | pre_check | violation（违规） |
| **YP_XB** | drug_gender | 药品限性别 | 481 | pre_check | violation（违规） |
| **YP_ETZY** | drug_child_only | 儿童专用药 | 271 | pre_check | violation（违规） |
| **YP_EXYY** | drug_second_line | 药品限二线用药 | 126 | pre_check | violation（违规） |
| **YP_JGJB** | drug_hospital_level | 药品限机构级别 | 88 | pre_check | violation（违规） |
| **YP_JYFS** | drug_visit_type | 药品限就医方式 | 35 | pre_check | violation（违规） |
| **YP_JYQD** | drug_channel | 药品限渠道（互联网） | 22 | pre_check | violation（违规） |
| **YP_CBXZ** | drug_insurance_type | 药品限参保险种 | 19 | pre_check | violation（违规） |
| **YP_ETXZ** | drug_child_limit | 药品限儿童使用 | 11 | pre_check | violation（违规） |
| **YP_NL** | drug_age_limit | 药品限年龄 | 5 | pre_check | violation（违规） |
| **YP_ZFLC** | drug_course | 药品限支付疗程 | 31 | end_check | suspicious（可疑） |
| **ZY_YPZF** | herbal_payment | 中药饮片支付限定 | 153 | end_check | suspicious（可疑） |

### 3.2 检出逻辑模板

#### 药品限适应症（YP_SYZ）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "药品关键词"},
    {"field": "claim_event.diag_codes", "op": "not_regex", "value": "E11|N18"}
  ]
}
```

#### 药品限性别（YP_XB）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "药品关键词"},
    {"field": "claim_event.gend", "op": "!=", "value": "限定性别"}
  ]
}
```

#### 药品限二线用药（YP_EXYY）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "二线药品关键词"},
    {"field": "claim_event.co_claimed_names", "op": "not_exists", "value": {"med_list_name": "一线药品关键词"}}
  ]
}
```

#### 中药饮片支付限定（ZY_YPZF）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.list_type", "op": "eq", "value": "13"},
    {"field": "claim_line.med_list_name", "op": "contains", "value": "阿胶"}
  ]
}
```

---

## 四、柱2：耗材类规则（HC）

### 4.1 规则类别一览

| 编码 | 原英文名 | 含义 | 规则数 | 阶段 | 严重级别 |
|------|---------|------|--------|------|---------|
| **HC_WH** | material_rule | 耗材物耗限定 | 5 | end_check | info（提示） |
| **HC_SP** | consumable_approval | 耗材审批限定 | 1 | pre_check | violation（违规） |
| **HC_ZY** | consumable_drug_loaded | 载药耗材 | 1 | post_audit | violation（违规） |
| **HC_FY** | consumable_reuse | 耗材重复使用 | 1 | end_check | violation（违规） |
| **HC_PD** | consumable_pair | 耗材-手术配对 | 1 | end_check | violation（违规） |
| **HC_SL** | consumable_qty | 耗材用量限制 | 1 | end_check | suspicious（可疑） |
| **HC_ZF** | consumable_payment | 耗材支付比例 | 1 | post_audit | info（提示） |

### 4.2 检出逻辑模板

#### 耗材审批限定（HC_SP）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "支架"},
    {"field": "claim_line.hosp_appr_flag", "op": "!=", "value": "1"}
  ]
}
```

#### 耗材重复使用（HC_FY）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "一次性"},
    {"field": "claim_line.cnt", "op": "gt", "value": 1}
  ]
}
```

#### 耗材物耗限定（HC_WH）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.list_type", "op": "eq", "value": "31"},
    {"field": "claim_line.is_basic_material", "op": "eq", "value": true},
    {"field": "claim_event.co_claimed_names", "op": "len_gt", "value": 0}
  ]
}
```

---

## 五、柱3：服务项目类规则（FW）

### 5.1 规则类别一览

| 编码 | 原英文名 | 含义 | 规则数 | 阶段 | 严重级别 |
|------|---------|------|--------|------|---------|
| **FW_XMHC** | mutual_exclusion | 项目互斥 | 937 | end_check | suspicious（可疑）/ violation（违规） |
| **FW_DJZJ** | pricing_rule | 项目定价折价 | 445 | end_check | suspicious（可疑） |
| **FW_XMXB** | project_gender | 项目限性别 | 390 | pre_check | violation（违规） |
| **FW_XMPC** | frequency_limit | 项目限频次 | 112 | end_check | suspicious（可疑） |
| **FW_ETZY** | project_child_only | 项目儿童专用 | 30 | pre_check | violation（违规） |
| **FW_BHGZ** | inclusion_rule | 项目包含规则 | 13 | end_check | info（提示） |
| **FW_XMLC** | project_course | 项目限疗程 | 12 | end_check | suspicious（可疑） |
| **FW_CFXZ** | split_limit | 项目拆分限制 | 9 | end_check | suspicious（可疑） |
| **FW_QZTJ** | condition_require | 项目前置条件 | 7 | end_check | info（提示） |

### 5.2 检出逻辑模板

#### 项目互斥（FW_XMHC）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "手法松解"},
    {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "中医推拿"}
  ]
}
```

#### 项目定价折价（FW_DJZJ）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.list_type", "op": "eq", "value": "21"},
    {"field": "claim_line.is_discounted", "op": "eq", "value": false},
    {"field": "claim_event.same_incision_group_count", "op": "gt", "value": 1}
  ]
}
```

#### 项目包含规则（FW_BHGZ）

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "被包含项目"},
    {"field": "claim_event.co_claimed_names", "op": "none_contains", "value": "主项目"}
  ]
}
```

---

## 六、柱4：病种类规则（BZ / DRG）

### 6.1 规则类型一览

| 编码 | 全称 | 检测逻辑 |
|------|------|---------|
| **GT** | 高套分组 | 合并症编码数量异常多 / 主诊断权重偏离 |
| **FJ** | 分解住院 | 同一患者同病种 15 天内再次住院 |
| **DB** | 低标入院 | 住院天数 ≤1天 且 费用低于门诊阈值 |
| **SJ** | 缩减服务 | 费用消耗指数远低于区域均值 |
| **ZSBP** | 诊断手术不匹配 | 主诊断与主手术无临床关联 |
| **PY** | 分组漂移 | 同一病种入组权重时间序列异常波动 |
| **WRZ** | 未入组 | 住院记录无 DRG 编码 |
| **DFSW** | 低风险死亡 | DRG 组为低风险但患者死亡 |
| **ZY** | 转院 | 转院患者费用异常 |
| **DZ** | 短住 | 住院天数短但费用高 |
| **GQZ** | 高权重 | DRG 权重高于阈值 |
| **ZF** | 自费 | 个人负担比例异常 |
| **CE** | 差额 | 总费用与 DRG 支付额差额较大 |
| **QSS** | 缺手术 | DRG 分组为手术组但无手术编码 |
| **CZ** | 长住 | 住院天数异常偏长 |
| **YCDZ** | 异常短住 | 短住 + 高费用不匹配 |
| **CZFY** | 长住费用 | 长住院 + 高费用 |
| **FYPL** | 费用偏离 | 总费用偏离 DRG 支付 |
| **FYTC** | 费用突出 | 费用远超同类病种 |

### 6.2 DRG 规则存储

DRG 规则独立存放于 `drg_rules` 表，通过 `conditions` DSL + `threshold_config` 阈值配置表达。

```json
// 费用偏离检测示例
{
  "rule_name": "费用偏离检测",
  "rule_type": "FYPL",
  "conditions": {
    "logic": "AND",
    "conditions": [
      {"field": "claim_event.medfee_sumamt", "op": "gt", "value": 10000}
    ]
  },
  "threshold_config": {
    "max_cost": 10000,
    "deviation_ratio": 0.25
  },
  "severity": "suspicious",
  "stage": "end_check"
}
```

---

## 七、人员资质类规则（Staff）

### 7.1 人员资质数据表

数据存放于 `staff_qualification` 表：

| 人员编码 | 姓名 | 职称 | 资质 |
|---------|------|------|------|
| DR001 | 李医生 | 住院医师 | ANTIBIO_UNLIMITED, NARCOTIC |
| DR002 | 王医生 | 副主任医师 | ANTIBIO_UNLIMITED, ANTIBIO_LIMITED, NARCOTIC, INTERVENTION |
| DR003 | 赵医生 | 主治医师 | ANTIBIO_UNLIMITED, INTERVENTION |
| DR004 | 孙药师 | 主管药师 | PHARMACIST |

### 7.2 规则类别

#### 抗菌药越级使用

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "regex", "value": "(美罗培南|亚胺培南|万古霉素)"},
    {"field": "staff.bilg_dr.title", "op": "lt", "value": "副主任医师"},
    {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "ANTIBIO_LIMITED"}
  ]
}
```

#### 麻醉药品处方权

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "吗啡"},
    {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "NARCOTIC"}
  ]
}
```

#### 介入手术资质

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "claim_line.med_list_name", "op": "contains", "value": "支架"},
    {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "INTERVENTION"}
  ]
}
```

#### 处方审核资质

```json
{
  "logic": "AND",
  "conditions": [
    {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "PHARMACIST"}
  ]
}
```

### 7.3 审核上下文（staff 段）

```json
{
  "staff": {
    "bilg_dr": {
      "staff_codg": "DR001",
      "staff_name": "李医生",
      "title": "住院医师",
      "qualifications": ["ANTIBIO_UNLIMITED", "NARCOTIC"],
      "cert_levels": ["非限制级"]
    },
    "orders_dr": {
      "staff_codg": "",
      "title": "",
      "qualifications": []
    }
  }
}
```

---

## 八、DSL 条件参考

### 8.1 运算符

| 运算符 | 用途 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{"op":"eq","value":"男"}` |
| `!=` | 不等于 | `{"op":"!=","value":"工伤"}` |
| `gt` | 大于 | `{"op":"gt","value":14}` |
| `gte` | 大于等于 | `{"op":"gte","value":18}` |
| `lt` | 小于 | `{"op":"lt","value":"二级"}` |
| `lte` | 小于等于 | `{"op":"lte","value":65}` |
| `in` | 在列表中 | `{"op":"in","value":["A","B"]}` |
| `not_in` | 不在列表中 | `{"op":"not_in","value":["住院"]}` |
| `contains` | 包含字符串 | `{"op":"contains","value":"检验"}` |
| `not_contains` | 不包含字符串 | `{"op":"not_contains","value":"E75.2"}` |
| `regex` | 正则匹配 | `{"op":"regex","value":"(美罗培南\|亚胺培南)"}` |
| `not_regex` | 正则不匹配 | `{"op":"not_regex","value":"^T"}` |
| `is_null` | 为空 | `{"op":"is_null","value":null}` |
| `is_not_null` | 不为空 | `{"op":"is_not_null","value":null}` |
| `any_contains` | 同笔清单含关键词 | `{"op":"any_contains","value":"推拿"}` |
| `none_contains` | 同笔清单不含关键词 | `{"op":"none_contains","value":"检验"}` |
| `coexists_with` | 同笔共存项目 | `{"op":"coexists_with","value":{"med_list_code":"X001"}}` |
| `not_exists` | 同笔不存在项目 | `{"op":"not_exists","value":{"med_list_code":"X001"}}` |
| `not_between` | 不在区间 | `{"op":"not_between","value":[0,100]}` |
| `len_gt` | 列表长度大于 | `{"op":"len_gt","value":3}` |
| `len_gte` | 列表长度大于等于 | `{"op":"len_gte","value":1}` |

### 8.2 上下文字段路径

| 路径 | 来源 | 说明 |
|------|------|------|
| `claim_event.gend` | ClaimEvent | 性别 |
| `claim_event.age` | ClaimEvent | 年龄（计算字段） |
| `claim_event.brdy` | ClaimEvent | 出生日期 |
| `claim_event.med_type` | ClaimEvent | 医疗类别 |
| `claim_event.hosp_lv` | ClaimEvent | 医院等级 |
| `claim_event.dept` | ClaimEvent | 入院科室 |
| `claim_event.insutype` | ClaimEvent | 险种 |
| `claim_event.main_diag_code` | ClaimEvent | 主诊断编码 |
| `claim_event.main_diag_name` | ClaimEvent | 主诊断名称 |
| `claim_event.diag_codes` | ClaimEvent | 次诊断列表 |
| `claim_event.main_oprn_code` | ClaimEvent | 主手术编码 |
| `claim_event.oprn_codes` | ClaimEvent | 次手术列表 |
| `claim_event.los` | ClaimEvent | 住院天数（计算字段） |
| `claim_event.medfee_sumamt` | ClaimEvent | 医疗费总额 |
| `claim_event.drg_codg` | ClaimEvent | DRG 病组编码 |
| `claim_event.co_claimed_names` | ContextBuilder | 同笔其他行名称列表 |
| `claim_event.claim_lines` | ContextBuilder | 同笔其他行完整数据 |
| `claim_event.is_internet` | ContextBuilder | 是否互联网医院 |
| `claim_event.same_incision_group_count` | ContextBuilder | 同切口组手术数 |
| `claim_line.list_type` | ClaimLine | 目录类别 |
| `claim_line.med_list_name` | ClaimLine | 项目名称 |
| `claim_line.med_list_codg` | ClaimLine | 目录编码 |
| `claim_line.cnt` | ClaimLine | 数量 |
| `claim_line.pric` | ClaimLine | 单价 |
| `claim_line.det_amt` | ClaimLine | 明细金额 |
| `claim_line.chrgitm_lv` | ClaimLine | 收费等级 |
| `claim_line.hosp_appr_flag` | ClaimLine | 审批标志 |
| `claim_line.is_basic_material` | ContextBuilder | 是否基本物耗 |
| `claim_line.is_special_function` | ContextBuilder | 是否特殊功能耗材 |
| `claim_line.is_discounted` | ContextBuilder | 是否已折价 |
| `claim_line.daily_quantity` | ContextBuilder | 每日用量 |
| `claim_line.period_quantity` | ContextBuilder | 周期累计用量 |
| `staff.bilg_dr.staff_codg` | StaffQualification | 开单医师编码 |
| `staff.bilg_dr.title` | StaffQualification | 开单医师职称 |
| `staff.bilg_dr.qualifications` | StaffQualification | 开单医师资质列表 |
| `staff.bilg_dr.cert_levels` | StaffQualification | 开单医师资质等级列表 |

---

## 九、字段别名映射

| DSL 字段名 | 引擎字段名 | 说明 |
|-----------|-----------|------|
| `patient_gender` | `gend` | 性别 |
| `patient_age` | `age` | 年龄 |
| `hospital_level` | `hosp_lv` | 医院等级 |
| `insurance_type` | `insutype` | 险种 |
| `diagnosis_codes` | `diag_codes` | 诊断编码列表 |
| `med_list_code` | `med_list_codg` | 医疗目录编码 |
| `project_code` | `med_list_codg` | 项目编码 |
| `visit_type` | `med_type` | 就医方式 |
| `prescription_type` | `med_type` | 处方类型 |
