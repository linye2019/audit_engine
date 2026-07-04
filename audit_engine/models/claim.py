from dataclasses import dataclass, field
from typing import Optional
import datetime


@dataclass
class ClaimEvent:
    """结算事件 — 审核引擎的输入单元（对齐国家医保信息平台接口规范 V1.1.85）"""
    setl_id: str                            # 结算ID
    mdtrt_id: str = ""                      # 就诊ID（医保就诊唯一标识）
    psn_no: str = ""                        # 人员编号（医保唯一标识）
    psn_name: str = ""                      # 姓名
    gend: str = ""                          # 性别代码: 0=未知, 1=男, 2=女, 9=未说明
    brdy: str = ""                          # 出生日期 YYYY-MM-DD
    insutype: str = ""                      # 险种类型: 310=职工基本医疗保险, 390=城乡居民基本医疗保险
    insu_region: str = ""                   # 参保地编码
    med_type: str = ""                      # 医疗类别: 11=普通门诊, 13=急诊, 14=门诊慢特病, 21=普通住院, 24=急诊转住院, 26=单病种住院, 28=日间手术
    adm_date: str = ""                      # 入院日期
    dscg_date: str = ""                     # 出院日期
    inhosp_days: int = 0                    # 实际住院天数
    hosp_lv: str = ""                       # 医院等级: 1=三级特等, 2=三级甲等, 3=三级乙等, 4=三级丙等, 5=二级甲等, 6=二级乙等, 7=二级丙等, 8=一级甲等, 9=一级乙等, 10=一级丙等, 11=无等级
    dept: str = ""                          # 入院科别
    adm_way: str = ""                       # 入院途径: 1=急诊, 2=门诊, 3=其他医疗机构转入, 9=其他
    dscg_way: str = ""                      # 离院方式: 1=医嘱离院, 2=医嘱转院, 3=医嘱转社区卫生服务机构/乡镇卫生院, 4=非医嘱离院, 5=死亡, 9=其他
    main_diag_code: str = ""                # 主要诊断ICD-10编码
    main_diag_name: str = ""                # 主要诊断名称
    diag_codes: list = field(default_factory=list)  # 次诊断ICD-10编码列表
    main_oprn_code: str = ""                # 主要手术ICD-9-CM-3编码
    oprn_codes: list = field(default_factory=list)  # 次手术编码列表
    drg_codg: str = ""                      # DRG病组编码
    drg_wt: float = 0.0                     # DRG权重
    drg_pay: float = 0.0                    # DRG标准支付额
    medfee_sumamt: float = 0.0              # 医疗费总额
    fund_pay_sumamt: float = 0.0            # 医保统筹基金支付
    acct_pay_sumamt: float = 0.0            # 个人账户支付
    psn_part_amt: float = 0.0               # 个人负担总额
    cash_payamt: float = 0.0                # 个人现金支付

    @property
    def age(self) -> Optional[int]:
        if not self.brdy:
            return None
        try:
            birth = datetime.date.fromisoformat(self.brdy)
            today = datetime.date.today()
            return (today - birth).days // 365
        except (ValueError, TypeError):
            return None

    @property
    def los(self) -> Optional[int]:
        if self.inhosp_days and self.inhosp_days > 0:
            return self.inhosp_days
        if not self.adm_date or not self.dscg_date:
            return None
        try:
            adm = datetime.date.fromisoformat(self.adm_date)
            dis = datetime.date.fromisoformat(self.dscg_date)
            return (dis - adm).days + 1
        except (ValueError, TypeError):
            return None


@dataclass
class ClaimLine:
    """费用明细行（对齐国家医保信息平台接口规范 V1.1.85）"""
    setl_id: str
    feedetl_sn: str = ""          # 费用明细流水号（接口规范 2301 主键）
    mdtrt_id: str = ""            # 就诊ID
    fee_ocur_time: str = ""       # 费用发生时间
    line_no: int = 0
    list_type: str = ""           # 目录类别: 11=西药, 12=中成药, 13=中药饮片, 21=诊疗项目, 31=医用耗材
    med_list_name: str = ""       # 医疗目录项目名称
    med_list_codg: str = ""       # 医疗目录编码（国家统一编码）
    medins_list_codg: str = ""    # 医疗机构目录编码（院内编码）
    cnt: float = 0.0              # 数量
    pric: float = 0.0             # 单价
    pric_ut: str = ""             # 计价单位
    det_amt: float = 0.0          # 明细金额
    chrgitm_lv: str = ""          # 收费项目等级: 1=甲, 2=乙, 3=自费
    bilg_drord_no: str = ""       # 医嘱号
    drord_type: str = ""          # 医嘱类别: 1=长期, 2=临时
    bilg_dept_codg: str = ""      # 开单科室编码
    bilg_dept_name: str = ""      # 开单科室名称
    bilg_dr_codg: str = ""        # 开单医师编码
    bilg_drord_dr_name: str = ""  # 开医嘱医师姓名
    acord_dept_codg: str = ""     # 受单科室编码
    acord_dept_name: str = ""     # 受单科室名称
    orders_dr_codg: str = ""      # 受单医师编码
    orders_dr_name: str = ""      # 受单医师名称
    exec_dept_codg: str = ""      # 执行科室编码
    exec_dept_name: str = ""      # 执行科室名称
    dosage_form: str = ""         # 实际使用剂型
    tcmdrug_used_way: str = ""    # 中药使用方式
    oprn_code_used: str = ""      # 使用该耗材的手术编码（ICD-9-CM-3）
    used_qty: float = 0.0         # 实际使用数量
    hosp_appr_flag: str = ""      # 医院审批标志: 0=无需审批, 1=已审批, 2=待审批
    etip_flag: str = ""           # 外检标志: 0=非外检, 1=外检
    dscg_tkdrug_flag: str = ""    # 出院带药标志: 0=否, 1=是
    matn_fee_flag: str = ""       # 生育费用标志: 0=否, 1=是
    clr_type: str = ""            # 清算类别: 11=门诊, 21=住院, 51=暂缓结算, 99=其他
    fund_pay_type: str = ""       # 基金支付类型
    comb_no: str = ""             # 组套编号
    memo: str = ""                # 备注
    raw_data: str = ""            # 原始JSON

    matched_catalog_id: Optional[int] = None
    match_confidence: float = 0.0
    match_method: str = ""