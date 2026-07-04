"""医保智能审核引擎 — Pydantic 请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field


class ClaimEventModel(BaseModel):
    """结算事件（对齐医保接口规范 V1.1.85）"""
    setl_id: str = Field(..., description="结算ID")
    mdtrt_id: str = Field("", description="就诊ID")
    psn_no: str = Field("", description="人员编号")
    psn_name: str = Field("", description="姓名")
    gend: str = Field("", description="性别: 1=男, 2=女, 0=未知, 9=未说明")
    brdy: str = Field("", description="出生日期 YYYY-MM-DD")
    insutype: str = Field("", description="险种: 310=职工医保, 390=居民医保")
    insu_region: str = Field("", description="参保地编码")
    med_type: str = Field(..., description="医疗类别: 11=门诊,13=急诊,14=门慢特,21=住院,24=急诊转住院,26=单病种,28=日间手术")
    adm_date: str = Field("", description="入院日期")
    dscg_date: str = Field("", description="出院日期")
    inhosp_days: int = Field(0, description="实际住院天数")
    hosp_lv: str = Field("", description="医院等级: 2=三甲,5=二甲,8=一甲等")
    dept: str = Field("", description="入院科别")
    adm_way: str = Field("", description="入院途径: 1=急诊,2=门诊,3=转入,9=其他")
    dscg_way: str = Field("", description="离院方式: 1=医嘱离院,5=死亡等")
    main_diag_code: str = Field("", description="主要诊断ICD-10编码")
    main_diag_name: str = Field("", description="主要诊断名称")
    diag_codes: list = Field(default_factory=list, description="次诊断ICD-10编码列表")
    main_oprn_code: str = Field("", description="主要手术ICD-9-CM-3编码")
    oprn_codes: list = Field(default_factory=list, description="次手术编码列表")
    drg_codg: str = Field("", description="DRG病组编码")
    drg_wt: float = Field(0.0, description="DRG权重")
    drg_pay: float = Field(0.0, description="DRG标准支付额")
    medfee_sumamt: float = Field(0.0, description="医疗费总额")
    fund_pay_sumamt: float = Field(0.0, description="医保统筹基金支付")
    acct_pay_sumamt: float = Field(0.0, description="个人账户支付")
    psn_part_amt: float = Field(0.0, description="个人负担总额")
    cash_payamt: float = Field(0.0, description="个人现金支付")


class ClaimLineModel(BaseModel):
    """费用明细行（对齐医保接口规范 V1.1.85）"""
    setl_id: str = Field("", description="结算ID")
    feedetl_sn: str = Field("", description="费用明细流水号")
    mdtrt_id: str = Field("", description="就诊ID")
    fee_ocur_time: str = Field("", description="费用发生时间")
    line_no: int = Field(0, description="行号")
    list_type: str = Field(..., description="目录类别: 11=西药,12=中成药,13=中药饮片,21=诊疗项目,31=医用耗材")
    med_list_name: str = Field(..., description="医疗目录项目名称")
    med_list_codg: str = Field("", description="医疗目录编码")
    medins_list_codg: str = Field("", description="医疗机构目录编码")
    cnt: float = Field(0.0, description="数量")
    pric: float = Field(0.0, description="单价")
    pric_ut: str = Field("", description="计价单位")
    det_amt: float = Field(0.0, description="明细金额")
    chrgitm_lv: str = Field("", description="收费项目等级: 1=甲,2=乙,3=自费")
    bilg_drord_no: str = Field("", description="医嘱号")
    drord_type: str = Field("", description="医嘱类别: 1=长期,2=临时")
    bilg_dept_codg: str = Field("", description="开单科室编码")
    bilg_dept_name: str = Field("", description="开单科室名称")
    bilg_dr_codg: str = Field("", description="开单医生编码")
    bilg_drord_dr_name: str = Field("", description="开单医师姓名")
    acord_dept_codg: str = Field("", description="受单科室编码")
    acord_dept_name: str = Field("", description="受单科室名称")
    orders_dr_codg: str = Field("", description="受单医师编码")
    orders_dr_name: str = Field("", description="受单医师名称")
    exec_dept_codg: str = Field("", description="执行科室编码")
    exec_dept_name: str = Field("", description="执行科室名称")
    dosage_form: str = Field("", description="实际使用剂型")
    tcmdrug_used_way: str = Field("", description="中药使用方式")
    oprn_code_used: str = Field("", description="使用该耗材的手术编码(ICD-9-CM-3)")
    used_qty: float = Field(0.0, description="实际使用数量")
    hosp_appr_flag: str = Field("", description="医院审批标志: 0=否,1=是")
    etip_flag: str = Field("", description="外检标志: 0=否,1=是")
    dscg_tkdrug_flag: str = Field("", description="出院带药标志: 0=否,1=是")
    matn_fee_flag: str = Field("", description="生育费用标志")
    clr_type: str = Field("", description="清算类别: 11=门诊,21=住院")
    fund_pay_type: str = Field("", description="基金支付类型")
    comb_no: str = Field("", description="组套编号")
    memo: str = Field("", description="备注")


class PreCheckItemModel(BaseModel):
    """事前提醒-拟开立项目"""
    list_type: str = Field(..., description="目录类别: 11=西药,12=中成药,13=中药饮片,21=诊疗项目,31=医用耗材")
    med_list_name: str = Field(..., description="项目名称")
    med_list_codg: str = Field("", description="目录编码")
    cnt: float = Field(1.0, description="数量")
    pric: float = Field(0.0, description="单价")
    chrgitm_lv: str = Field("", description="收费等级: 1=甲,2=乙,3=自费")
    hosp_appr_flag: str = Field("", description="审批标志: 0=否,1=是")
    oprn_code_used: str = Field("", description="耗材关联手术编码")


class PreCheckRequest(BaseModel):
    """事前医嘱审核请求"""
    gend: str = Field("", description="患者性别")
    brdy: str = Field("", description="出生日期")
    med_type: str = Field("", description="医疗类别")
    hosp_lv: str = Field("", description="医院等级")
    dept: str = Field("", description="科室")
    insutype: str = Field("", description="险种")
    main_diag_code: str = Field("", description="主诊断编码")
    main_diag_name: str = Field("", description="主诊断名称")
    diag_codes: list = Field(default_factory=list, description="次诊断列表")
    main_oprn_code: str = Field("", description="主手术编码")
    items: list[PreCheckItemModel] = Field(..., description="拟开立项目列表")


class ConcurrentAuditRequest(BaseModel):
    """事中出科审核请求"""
    claim_event: ClaimEventModel
    claim_lines: list[ClaimLineModel]
    persist: bool = Field(True, description="是否持久化审核结果")


class PostAuditRequest(BaseModel):
    """事后结算监管请求"""
    claim_event: ClaimEventModel
    claim_lines: list[ClaimLineModel]
    persist: bool = Field(True, description="是否持久化审核结果")


class ConsumableImportItem(BaseModel):
    """耗材导入条目"""
    generic_name: str = Field(..., description="耗材通用名")
    ccode: str = Field("", description="CUC编码")
    category: str = Field("", description="分类")
    payment_type: str = Field("乙类", description="支付类别: 甲/乙")
    payment_ratio: float = Field(0.0, description="自付比例")
    drug_loaded: int = Field(0, description="是否载药: 0=否,1=是")
    drug_component: str = Field("", description="载药成分")
    evidence_source: str = Field("", description="来源")


class ConsumableImportRequest(BaseModel):
    """耗材批量导入请求"""
    consumables: list[ConsumableImportItem]
    skip_existing: bool = Field(True, description="跳过已存在的通用名")


class AuditResultItem(BaseModel):
    """审核结果条目"""
    claim_id: str = ""
    line_no: Optional[int] = None
    rule_code: str = ""
    rule_category: str = ""
    pillar: str = ""
    verdict: str = "pass"
    severity: str = ""
    reasoning: str = ""
    action: str = "warn"


class AuditResponse(BaseModel):
    """审核响应"""
    setl_id: str
    stage: str
    total_lines: int = 0
    total_results: int = 0
    violation_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    has_block: bool = False
    results: list = []


class PreCheckResponse(BaseModel):
    """事前审核响应"""
    decision: str = "pass"
    total_items: int = 0
    total_alerts: int = 0
    block_count: int = 0
    warn_count: int = 0
    alerts: list[AuditResultItem] = []


class StatsResponse(BaseModel):
    """统计响应"""
    code: int = 0
    tables: dict = {}


# ============================================================================
# 规则版本管理模型
# ============================================================================

class CreateSnapshotRequest(BaseModel):
    snapshot_name: str = Field(..., description="快照名称，如 v2026Q3")
    snapshot_desc: str = Field("", description="快照描述")
    created_by: str = Field("system", description="创建人")


class UpdateRuleVersionRequest(BaseModel):
    rule_name: Optional[str] = None
    rule_category: Optional[str] = None
    pillar: Optional[str] = None
    stage: Optional[str] = None
    severity: Optional[str] = None
    conditions: Optional[str] = None
    action: Optional[str] = None
    action_message: Optional[str] = None
    effective_date: Optional[str] = None
    expired_date: Optional[str] = None
    changed_by: str = "system"


# ============================================================================
# 规则沙箱模型
# ============================================================================

class SandboxTestRequest(BaseModel):
    """规则沙箱测试请求"""
    stage: str = Field("post_audit", description="审核阶段: pre_check/end_check/post_audit")
    gend: str = Field("", description="性别: 1=男,2=女")
    brdy: str = Field("1980-01-01", description="出生日期 YYYY-MM-DD")
    med_type: str = Field("11", description="医疗类别: 11=门诊,21=住院")
    hosp_lv: str = Field("", description="医院等级")
    dept: str = Field("", description="科室")
    insutype: str = Field("", description="险种")
    main_diag_code: str = Field("", description="主诊断ICD-10")
    main_diag_name: str = Field("", description="主诊断名称")
    diag_codes: list = Field(default_factory=list, description="次诊断ICD-10列表")
    main_oprn_code: str = Field("", description="主手术ICD-9-CM-3")
    inhosp_days: int = Field(0, description="住院天数")
    adm_date: str = Field("", description="入院日期")
    dscg_date: str = Field("", description="出院日期")
    dscg_way: str = Field("", description="离院方式: 1=医嘱离院,5=死亡")
    drg_codg: str = Field("", description="DRG病组编码")
    drg_wt: float = Field(0.0, description="DRG权重")
    drg_pay: float = Field(0.0, description="DRG支付额")
    medfee_sumamt: float = Field(0.0, description="费用总额")
    fund_pay_sumamt: float = Field(0.0, description="基金支付")
    psn_part_amt: float = Field(0.0, description="个人负担")
    lines: list[dict] = Field(default_factory=list, description="费用明细行列表")
    rule_code_filter: str = Field("", description="只返回指定规则编码的结果(空=全部)")
