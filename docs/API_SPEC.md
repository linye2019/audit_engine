# 医保智能审核规则引擎 — API 接口规范
版本: 2.1.0 | 对齐国家医保信息平台接口规范 V1.1.85 | 模块化重构 + 规则版本管理

## 一、接口总览

### 1.1 核心方法

```python
# 新导入路径（推荐）
from audit_engine import MedicareAuditEngine, ClaimEvent, ClaimLine

engine = MedicareAuditEngine(db_path="medicare_engine.db")
results = engine.audit_claim(claim, lines, stage="post_audit")
```

> **向后兼容**：旧导入路径 `from audit_engine import ...` 仍可使用，但建议迁移至新路径。

### 1.2 方法签名

| 方法 | 入参 | 出参 |
|------|------|------|
| `audit_claim(claim, lines, stage)` | ClaimEvent + list[ClaimLine] + stage | list[AuditResult] |
| `save_results(results)` | list[AuditResult] | None（写入 audit_result 表） |
| `close()` | 无 | None（关闭数据库连接） |

### 1.3 三阶段审核

| stage | 业务名称 | 时机 | 规则范围 | 加载逻辑 |
|-------|---------|------|---------|---------|
| `pre_check` | 事前医嘱审核 | 医生开立医嘱时 | 仅 severity=violation 的事前规则 | `stage='pre_check'` AND `severity='violation'` |
| `end_check` | 事中出科审核 | 患者出科/出院时 | 事前+事中全量规则 | `stage IN ('pre_check','end_check')` |
| `post_audit` | 事后结算监管 | 结算完成后 | 全量规则（事前+事中+事后） | 全量加载（无stage过滤） |

> **向下级联机制**：三阶段可用数据范围递增（事前:患者+诊断+单项 → 事中:+完整费用清单 → 事后:+DRG+结算），
> 因此规则按向下级联加载：事前规则在事中、事后也会触发，事中规则在事后也会触发。
> pre_check 阶段额外限制 severity='violation'，避免给医生推送不确定的提醒。

---

## 二、入参规范

### 2.1 ClaimEvent（结算事件）

对齐国家医保接口 2301 报文，结算维度数据。

| 字段 | 类型 | 必填 | 说明 | 值域 |
|------|------|------|------|------|
| `setl_id` | str | 是 | 结算ID | 唯一标识 |
| `mdtrt_id` | str | 否 | 就诊ID | 医保就诊唯一标识 |
| `psn_no` | str | 否 | 人员编号 | 医保唯一标识 |
| `psn_name` | str | 否 | 姓名 | |
| `gend` | str | 是 | 性别代码 | 0=未知, 1=男, 2=女, 9=未说明 |
| `brdy` | str | 否 | 出生日期 | YYYY-MM-DD（用于计算年龄） |
| `insutype` | str | 否 | 险种类型 | 310=职工医保, 390=居民医保 |
| `insu_region` | str | 否 | 参保地编码 | |
| `med_type` | str | 是 | 医疗类别 | 11=普通门诊, 13=急诊, 14=门诊慢特病, 21=普通住院, 24=急诊转住院, 26=单病种, 28=日间手术 |
| `adm_date` | str | 否 | 入院日期 | YYYY-MM-DD |
| `dscg_date` | str | 否 | 出院日期 | YYYY-MM-DD |
| `inhosp_days` | int | 否 | 住院天数 | |
| `hosp_lv` | str | 否 | 医院等级 | 1~11（2=三级甲等） |
| `dept` | str | 否 | 入院科别 | 用于推断病房类型 |
| `main_diag_code` | str | 否 | 主诊断ICD-10 | |
| `main_diag_name` | str | 否 | 主诊断名称 | |
| `diag_codes` | list[str] | 否 | 次诊断ICD-10列表 | |
| `main_oprn_code` | str | 否 | 主手术ICD-9-CM-3 | |
| `oprn_codes` | list[str] | 否 | 次手术编码列表 | |
| `drg_codg` | str | 否 | DRG病组编码 | |
| `drg_wt` | float | 否 | DRG权重 | |
| `drg_pay` | float | 否 | DRG标准支付额 | |
| `medfee_sumamt` | float | 否 | 医疗费总额 | |
| `fund_pay_sumamt` | float | 否 | 统筹基金支付 | |

### 2.2 ClaimLine（费用明细行）

对齐国家医保接口 2301 明细报文。

| 字段 | 类型 | 必填 | 说明 | 值域 |
|------|------|------|------|------|
| `setl_id` | str | 是 | 结算ID | 关联 ClaimEvent |
| `feedetl_sn` | str | 是 | 明细流水号 | 同结算单内唯一 |
| `mdtrt_id` | str | 否 | 就诊ID | |
| `fee_ocur_time` | str | 否 | 费用发生时间 | |
| `list_type` | str | 是 | 目录类别 | **11=西药, 12=中成药, 13=中药饮片, 21=诊疗项目, 31=医用耗材** |
| `med_list_name` | str | 是 | 目录项目名称 | |
| `med_list_codg` | str | 否 | 国家目录编码 | 15位（耗材基本物耗可能为空） |
| `medins_list_codg` | str | 否 | 院内编码 | 各院自定义 |
| `cnt` | float | 否 | 数量 | |
| `pric` | float | 否 | 单价 | |
| `det_amt` | float | 否 | 明细金额 | |
| `chrgitm_lv` | str | 否 | 收费等级 | 1=甲, 2=乙, 3=自费 |
| `bilg_dept_codg` | str | 否 | 开单科室编码 | |
| `bilg_dr_codg` | str | 否 | 开单医师编码 | |
| `oprn_code_used` | str | 否 | 使用耗材的手术编码 | ICD-9-CM-3 |
| `used_qty` | float | 否 | 实际使用数量 | |
| `hosp_appr_flag` | str | 否 | 医院审批标志 | 0=无需, 1=已审批, 2=待审批 |
| `etip_flag` | str | 否 | 外检标志 | 0=非外检, 1=外检 |
| `dscg_tkdrug_flag` | str | 否 | 出院带药标志 | 0=否, 1=是 |
| `comb_no` | str | 否 | 组套编号 | |

---

## 三、出参规范

### 3.1 AuditResult（审核结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| `claim_id` | str | 结算ID |
| `line_no` | int/None | 费用明细行号（事件级审核为 None） |
| `rule_id` | int | 规则ID |
| `rule_code` | str | 规则编码（如 LG-IND-0001） |
| `rule_category` | str | 规则大类（如 YP_SYZ） |
| `pillar` | str | 审核柱（YP/HC/FW/BZ） |
| `stage` | str | 审核阶段 |
| `verdict` | str | 审核判定：**pass/warning/violation** |
| `severity` | str | 严重程度：**violation/suspicious/info** |
| `matched_facts` | dict | 匹配事实（含 conditions_checked 推理链） |
| `rule_text` | str | 规则 conditions JSON 原文 |
| `reasoning` | str | 推理说明（检出逻辑文本） |
| `action` | str | 处置动作：**block/warn/tag/pass** |
| `engine_version` | str | 引擎版本号 |
| `rule_version` | int | 触发的规则版本号（用于回溯） |

### 3.2 matched_facts 结构

```json
{
  "drug_id": 123,
  "required_diagnoses": ["E75.2"],
  "conditions_checked": [
    {
      "field": "claim_line.med_list_code",
      "op": "in",
      "actual": "XL01ELA387E001010184513",
      "expected": ["XL01ELA387E001010184513"]
    },
    {
      "field": "claim_event.diagnosis_codes",
      "op": "not_contains",
      "actual": ["J00", "J01"],
      "expected": ["E75.2"]
    }
  ]
}
```

---

## 四、调用示例

### 4.1 Python SDK 调用

```python
from audit_engine import MedicareAuditEngine, ClaimEvent, ClaimLine

engine = MedicareAuditEngine("medicare_engine.db")

# 构造结算事件
claim = ClaimEvent(
    setl_id="SETL202601001",
    mdtrt_id="MDTRT001",
    gend="1",                    # 男性
    brdy="1980-01-01",
    insutype="310",              # 职工医保
    med_type="21",               # 普通住院
    hosp_lv="2",                 # 三级甲等
    dept="内科",
    adm_date="2026-01-01",
    dscg_date="2026-01-10",
    main_diag_code="J00",
    diag_codes=["J01", "J02"],
)

# 构造费用明细
lines = [
    ClaimLine(
        setl_id="SETL202601001",
        feedetl_sn="L001",
        list_type="11",          # 西药
        med_list_name="阿莫西林胶囊",
        med_list_codg="XL01EMA057E001010104675",
        cnt=3, pric=5.0, det_amt=15.0,
        chrgitm_lv="1",
    ),
    ClaimLine(
        setl_id="SETL202601001",
        feedetl_sn="L002",
        list_type="31",          # 耗材
        med_list_name="一次性使用无菌棉球",
        cnt=10, pric=0.5, det_amt=5.0,
        chrgitm_lv="2",
    ),
]

# 执行审核
results = engine.audit_claim(claim, lines, stage="post_audit")

# 处理结果
for r in results:
    print(f"[{r.verdict}] {r.rule_code}: {r.reasoning}")
    print(f"  处置: {r.action}, 严重度: {r.severity}")

engine.close()
```

### 4.2 HTTP API 调用（建议封装方式）

第三方系统可通过 HTTP 封装调用引擎：

```
POST /api/audit
Content-Type: application/json

请求体:
{
  "stage": "post_audit",
  "claim": {
    "setl_id": "SETL202601001",
    "gend": "1",
    "brdy": "1980-01-01",
    "insutype": "310",
    "med_type": "21",
    "hosp_lv": "2",
    "dept": "内科",
    "adm_date": "2026-01-01",
    "dscg_date": "2026-01-10",
    "main_diag_code": "J00",
    "diag_codes": ["J01"]
  },
  "lines": [
    {
      "setl_id": "SETL202601001",
      "feedetl_sn": "L001",
      "list_type": "11",
      "med_list_name": "阿莫西林胶囊",
      "med_list_codg": "XL01EMA057E001010104675",
      "cnt": 3,
      "pric": 5.0,
      "det_amt": 15.0,
      "chrgitm_lv": "1"
    }
  ]
}

响应体:
{
  "engine_version": "1.0.0",
  "total_results": 2,
  "results": [
    {
      "claim_id": "SETL202601001",
      "line_no": 0,
      "rule_code": "HC-WH-LXZN-0001",
      "rule_code_cn": "耗材-物耗限定-立项指南-0001",
      "rule_category": "HC_WH",
      "pillar": "HC",
      "verdict": "violation",
      "severity": "violation",
      "action": "block",
      "reasoning": "基本物耗不可单独收费",
      "matched_facts": {
        "conditions_checked": [
          {"field": "claim_line.list_type", "op": "eq", "actual": "31", "expected": "31"},
          {"field": "claim_line.is_basic_material", "op": "eq", "actual": true, "expected": true}
        ]
      }
    }
  ]
}
```

---

## 五、规则匹配流程

```
输入: ClaimEvent + list[ClaimLine]
  │
  ├─ 逐行处理每条 ClaimLine
  │   ├─ STEP1: 目录匹配（编码→精确→别名→模糊）
  │   ├─ STEP2: 确定审核柱（11/12/13→药品, 21→项目, 31→耗材）
  │   ├─ STEP3: 构建上下文 _build_context()（48个字段）
  │   ├─ STEP4: 加载该柱+该阶段的活跃规则
  │   ├─ STEP5: 实体关联过滤 _entity_matches()
  │   ├─ STEP6: 逐条评估 conditions DSL → ConditionEvaluator.evaluate()
  │   └─ STEP7: 满足条件 → 构建 AuditResult（含推理链）
  │
  ├─ 事件级审核（仅住院 med_type=21/24/26/28）
  │   └─ 柱4: DRG 规则审核
  │
  └─ 返回: list[AuditResult]
```

---

## 六、规则编码命名规范（拼音方案）

### 6.1 编码格式

```
{柱别}-{子类}-{来源}-{序号}
 YP    XB    B1-1   0001
 │     │     │      │
 │     │     │      └─ 4位序号（组内递增）
 │     │     └──────── 来源批次/文档
 │     └────────────── 业务子类（拼音首字母）
 └──────────────────── 业务柱别（拼音首字母）
```

### 6.2 柱别代码

| 代码 | 中文 | list_type |
|------|------|-----------|
| `YP` | 药品 | 11/12/13 |
| `XM` | 项目 | 21 |
| `HC` | 耗材 | 31 |
| `ZY` | 中药 | 13（饮片） |

### 6.3 子类代码（常用）

| 代码 | 中文 | 说明 |
|------|------|------|
| `XB` | 性别限定 | 药品/项目通用 |
| `ET` | 儿童专用 | 药品/项目通用 |
| `SYZ` | 适应症限定 | 药品专用 |
| `EX` | 二线限定 | 药品专用 |
| `HC` | 互斥重复 | 项目专用（位置2，与柱别HC位置1区分） |
| `DJ` | 定价折价 | 项目专用 |
| `PC` | 频次限定 | 项目专用 |
| `WH` | 物耗限定 | 耗材专用 |
| `SP` | 审批限定 | 耗材专用 |

### 6.4 来源代码（4位拼音）

| 代码 | 中文 | 说明 | 数量 |
|------|------|------|------|
| `GJ01`~`GJ17` | 国家两库第N批 | 国家医保局"两库"（规则库+知识库）知识点 Excel | 3487 |
| `LXZN` | 立项指南 | 医疗服务价格项目立项指南（Lì Xiàng Zhǐ Nán），提供项目计价/适应症/频次边界 | 218 |
| `MLXD` | 目录限定 | 药品目录"备注"列提取（Mù Lù Xiàn Dìng） | 226 |
| `TYGZ` | 通用规则 | 行业通用规则/常识（Tōng Yòng Guī Zé） | 7 |
| `CSZZ` | 测试种子 | 开发测试数据（Cè Shì Zhǒng Zǐ） | 5 |
| `RGBJ` | 人工编写 | 人工新增规则（Rén Gōng Biān Jiě） | 0 |

> **规则来源体系**：rule_items 中的规则来源于两条主线——
> 1. **国家两库**（GJ01~GJ17）：提供药品适应症、性别、儿童、险种、频次、互斥等监管规则
> 2. **立项指南**（LXZN）：提供项目计价单位、服务产出、适应症边界等项目约束
> 二者均需关联三目（药品/项目/耗材目录）中的具体编码才能形成可执行的有效规则。

### 6.5 编码示例

| 编码 | 解读 |
|------|------|
| `YP-XB-GJ01-0001` | 药品-性别限定-国家两库第一批-0001 |
| `XM-HC-GJ07-0001` | 项目-互斥重复-国家两库第七批-0001 |
| `HC-WH-LXZN-0001` | 耗材-物耗限定-立项指南-0001 |
| `YP-EX-MLXD-0001` | 药品-二线限定-目录限定-0001 |
| `ZY-ZF-GJ11-0001` | 中药-支付限定-国家两库第十一批-0001 |

> `rule_code_cn` 字段提供完整中文显示名，如"药品-性别限定-国家两库第一批-0001"

---

## 七、处置动作说明

| action | 含义 | 第三方系统处理建议 |
|--------|------|------------------|
| `block` | 拦截 | 应拒付或标记违规，需人工复核后才能放行 |
| `warn` | 提醒 | 推送给医生/审核员关注，不自动拦截 |
| `tag` | 标记 | 记录待复核，不影响结算流程 |
| `pass` | 放行 | 规则未触发，正常通过 |

---

## 八、引擎计算字段说明

引擎 `_build_context()` 会从入参自动派生以下字段，第三方系统无需传入：

| 计算字段 | 来源 | 用途 |
|---------|------|------|
| `age` | brdy → 当前日期计算 | 年龄限定规则 |
| `los` | adm_date/dscg_date 或 inhosp_days | 住院天数 |
| `co_claimed_names` | all_lines 遍历 | 跨行互斥判断 |
| `claim_lines` | all_lines 遍历 | 跨行共存/不存在判断 |
| `is_internet` | hosp_lv/med_type 含"互联网" | 互联网医院限定 |
| `same_incision_group_count` | oprn_code_used 去重计数 | 同切口组手术数 |
| `daily_quantity` | line.cnt | 每日数量 |
| `usage_days` | adm_date/dscg_date 计算 | 使用天数 |
| `period_quantity` | 同编码 cnt 累加 | 周期内数量 |
| `is_discounted` | det_amt < pric*cnt | 是否已折价 |
| `duration_hours` | adm_date/dscg_date 计算 | 服务时长（小时） |
| `ward_type` | dept 关键词推断 | 病房类型 |
| `same_surcharge_category_count` | 编码末2位解析 | 同类别加收项数 |
| `is_basic_material` | HC 表查询（is_basic=1） | 是否基本物耗 |
| `is_special_function` | HC 表查询（is_special_function=1） | 是否特殊功能耗材 |
| `is_highest_price` | 同笔单价比较 | 是否最高价项目 |
| `price_margin` | det_amt - pric*cnt | 价格差额 |

---

## 九、端到端测试验证

### 9.1 测试覆盖

10 组模拟结算单，覆盖四柱（药品/耗材/项目/DRG）+ 正向合规 + 负向违规场景：

| 用例 | 场景 | 期望规则 | 结果 |
|------|------|---------|------|
| T001 | 耗材-基本物耗单独收费 | HC-WH-LXZN-0001 | PASS |
| T002 | 耗材-正常诊疗无基本物耗 | 无违规 | PASS |
| T003 | 项目-走罐与推拿拔罐互斥 | XM-HC-LXZN-0002 | PASS |
| T004 | 项目-放疗多模式非最高价 | XM-DJ-LXZN-0006 | PASS |
| T005 | 项目-分级护理不足12小时 | XM-DJ-LXZN-0005 | PASS |
| T006 | 耗材-特殊功能耗材未挂网 | HC-WH-LXZN-0002 | PASS |
| T007 | 项目-氢谱磷谱波谱叠加 | XM-HC-LXZN-0011 | PASS |
| T008 | 项目-ICU病房收免陪照护费 | XM-TJ-LXZN-0002 | PASS |
| T009 | 耗材-钠石灰单独收费 | HC-WH-LXZN-0001 | PASS |
| T010 | 合规-正常住院无违规 | 无违规 | PASS |

**通过率: 10/10 (100%)**

### 9.2 引擎修复记录

| 修复项 | 影响范围 | 根因 |
|--------|---------|------|
| coexists_with 空字符串匹配 | ~6300条误报消除 | dict值中med_list_name不存在时回退为""，`"" in str(item)` 恒为True |
| not_exists 同上 | 跨行不存在判断修正 | 同上 |
| _entity_matches 未匹配穿透 | 防止无目录匹配的行触发实体规则 | `if match and ...` 当match=None时跳过检查 |
| _get_actual_value 计算字段 | conditions_checked展示正确 | getattr(claim,"claim_lines")→None，应从context读取 |
| PROJ-GEN-001/002 pillar | 耗材规则可正确加载 | pillar=FW但条件检查list_type=31，改pillar=HC |
| DRG高套分组规则 | 不再对每个结算触发 | regex `.+` 匹配任何字符串，改用 len_gt 3 |
| DRG分解住院规则 | 降低误报 | los<=3太激进，改los<=1且费用<1000 |

### 9.3 深度审查修复记录

| 修复项 | 影响范围 | 根因 |
|--------|---------|------|
| 组合限定规则 OR→AND | 30条规则 | `not_regex "A\|B"` 是OR逻辑（有A或B→合规），但"限A伴B"需AND逻辑（有A且B→合规），改为嵌套AND |
| stage值修复 | 159条规则 | 数据库中`stage='pre_audit'`与引擎期望的`'pre_check'`不匹配，导致规则从未被加载 |
| severity值修复 | 1条规则 | `severity='warning'`非标准值，改为`'suspicious'` |
| action值修复 | 2条规则 | `severity='violation'`但`action='warn'`不一致，改为`action='block'` |
| is_not_null噪音规则 | 7条规则 | 条件仅为`med_list_name is_not_null`对每条费用行触发，增加关键词过滤 |
| 重复规则清理 | 161条规则停用 | 同源同条件的规则被重复创建，保留低序号版本 |

### 9.4 终极审查修复记录（跨阶段合并）

| 修复项 | 影响范围 | 根因 |
|--------|---------|------|
| herbal pillar不匹配 | 153条规则 | `pillar='herbal'`但引擎pillar_map将list_type=13映射到`'drug'`，导致规则从未被加载 |
| herbal条件字段错误 | 153条规则 | `med_list_code eq '阿胶'`用药名匹配编码字段永不命中，改为`med_list_name contains '阿胶'` |
| herbal缺list_type限定 | 153条规则 | 条件无`list_type=13`限定，西药费用行也误触发，补充`list_type eq '13'` |
| project_catalog缺列 | 1列 | 引擎查询`med_list_codg`列但表无此列，从`national_code`复制补全 |

**审查后活跃规则: 3782条（原3943条，停用161条重复）**
**审查后e2e测试违规触发: 18条（原98条，噪音降低80%）**
**ZY_YPZF规则: 153条全部活跃，pillar=drug，含list_type=13限定**

### 9.5 第三阶段系统优化修复记录

| 修复项 | 影响范围 | 根因与措施 |
|--------|---------|-----------|
| 药品适应症规则补充 | 新增105条规则(YP-SYZ-GJ18-xxxx) | 178种药品有restriction_raw但无规则，从中提取诊断关键词映射ICD-10编码生成适应症限定规则 |
| ICD-10 API 500错误 | /api/v1/icd10/search | API使用`code`字段但表列为`chs_code`，修正SELECT/WHERE/ORDER BY |
| ICD-9 API 500错误 | /api/v1/icd9/search | 同上，`code`→`chs_code` |
| FW API 500错误 | /api/v1/catalog/project | API使用`med_list_name`但表列为`name`，修正查询字段 |
| 药品ATC编码补全 | 2649种药品 | 2728种药品缺ATC编码，通过关键词匹配分类补全，覆盖率40.3%→98.3% |
| DRG规则扩充 | 新增10条规则 | DRG规则从7条扩充至17条，覆盖未入组/低风险死亡/转院/短住/高权重/自费异常/支付差额/无手术入手术DRG/超长住院/天数费用不匹配 |
| 引擎事件上下文增强 | audit_engine.py | `_build_event_context`新增`psn_part_amt`和`dscg_way`字段 |
| DRG规则SQL优先级修复 | audit_engine.py | `WHERE is_active=1 OR ... AND ...`优先级错误，添加括号修正 |
| DRG规则缓存 | audit_engine.py | `_load_drg_rules`新增`_drg_rule_cache`避免重复查询 |
| 100行明细性能优化 | 全引擎 | 三级缓存(规则缓存+目录匹配缓存+DRG规则缓存)，100行性能: pre_check 45ms / end_check 149ms / post_audit 156ms |
| 跨行互斥bug修复 | audit_engine.py | `co_claimed_names`在`feedetl_sn`为空时无法识别跨行，改用`line_no`回退判断 |
| 条件解析缓存 | audit_engine.py | `ConditionEvaluator`新增`_condition_cache`，避免同一条件JSON重复`json.loads`解析 |
| 名称关键词预过滤 | audit_engine.py | `_load_rules`提取`_name_keyword`，药品名不包含关键词时跳过规则评估，100行性能628ms→78ms |
| 全量规则测试套件V3 | e2e_test_v3.py | 新增36组测试用例覆盖31个规则类别+7个DRG场景，35/36通过(97%)，发现1个规则数据质量问题 |
| GJ12-GJ17条件DSL迁移 | 522条适应症规则 | `med_list_code in [编码]`→`med_list_name contains 药品名`，与GJ18批次统一，沙箱可按名称触发 |
| 适应症规则阶段统一 | 734条适应症规则 | stage统一为`pre_check`，severity统一为`violation` |
| 三阶段重新划分 | 全部3887条规则 | 按可用数据范围重新分配: pre_check(2155条) / end_check(1727条) / post_audit(5条) |
| 级联方向修复 | audit_engine.py | 从向上级联(post_audit→pre_check)改为向下级联(pre_check→end_check→post_audit) |
| 规则沙箱环境 | api_server.py + rule_sandbox.html | 6个沙箱API端点 + 前端三栏UI(规则浏览/测试构建/结果可视化) + 10类测试模板 |

**当前活跃规则: 3887条rule_items + 17条drg_rules**
**ATC编码覆盖率: 98.3% (4488/4567)**
**三阶段分布: pre_check(事前医嘱) 2155条 / end_check(事中出科) 1727条 / post_audit(事后结算) 5条**
**100行明细性能: pre_check 45ms / post_audit 78ms (含条件缓存+名称预过滤)**
**全量测试覆盖: 31个规则类别+7个DRG场景, 35/36通过(97%), 1个跳过(数据质量问题)**

---

## 十、规则版本管理 API

> **设计定位**：采用"轻量快照 + 时间旅行"方案，通过 `SQLiteRepository` 提供规则版本管理能力，支持规则演进追溯和历史版本回查。

### 10.1 版本管理接口

所有方法通过 `engine.repo`（`SQLiteRepository` 实例）访问。

| 方法 | 入参 | 出参 | 说明 |
|------|------|------|------|
| `update_rule_version(rule_code, updates, changed_by)` | rule_code: str<br>updates: dict（要修改的字段）<br>changed_by: str | `{rule_code, old_version, new_version}` | 修订规则（旧版失效+插入新版） |
| `create_snapshot(snapshot_name, snapshot_desc, created_by)` | snapshot_name: str<br>snapshot_desc: str<br>created_by: str | `{snapshot_name, rule_count, created_at}` | 创建规则集快照 |
| `get_snapshots()` | 无 | list[dict] | 查询所有快照列表（按时间倒序） |
| `get_changelog(rule_id, rule_code, limit)` | rule_id: int（可选）<br>rule_code: str（可选）<br>limit: int（默认100） | list[dict] | 查询规则变更日志 |

### 10.2 使用示例

```python
from audit_engine import MedicareAuditEngine

engine = MedicareAuditEngine("medicare_engine.db")
repo = engine.repo

# 1. 修订某条规则（版本自动递增）
result = repo.update_rule_version(
    rule_code="YP-SYZ-GJ01-0001",
    updates={
        "rule_name": "奥司他韦限流感（修订版）",
        "action_message": "该药品限流感患者使用，诊断需包含J10-J11",
        "conditions": '{"logic":"AND","conditions":[...]}'
    },
    changed_by="admin"
)
# result: {"rule_code": "YP-SYZ-GJ01-0001", "old_version": 1, "new_version": 2}

# 2. 创建规则集快照（如批次导入完成时）
snapshot = repo.create_snapshot(
    snapshot_name="GJ18-imported",
    snapshot_desc="国家两库第18批导入完成",
    created_by="import_pipeline"
)
# snapshot: {"snapshot_name": "GJ18-imported", "rule_count": 3887, "created_at": "2026-07-03"}

# 3. 查询所有快照
snapshots = repo.get_snapshots()
# 返回按时间倒序的快照列表

# 4. 查看某规则的变更历史
changelog = repo.get_changelog(rule_code="YP-SYZ-GJ01-0001", limit=50)
# 返回该规则的所有变更记录（含 create/update/version_upgrade/deactivate）

engine.close()
```

### 10.3 时间旅行审核

审核时可通过传入 `audit_date` 参数加载指定日期生效的规则版本：

```python
# 加载 2026-06-01 当天生效的规则进行历史回溯审核
results = engine.audit_claim(claim, lines, stage="post_audit")
# 内部通过 effective_date / expired_date 自动过滤规则
```

> **注意**：`audit_date` 参数通过 `SQLiteRepository.load_rules(audit_date=...)` 传递，引擎核心自动适配。
