from ..models.claim import ClaimEvent


class DRGReasoning:
    @staticmethod
    def generate(rule_type: str, claim: ClaimEvent) -> str:
        reasoning_map = {
            "GT": f"患者 {claim.setl_id} 合并症编码数量({len(claim.diag_codes)}个)异常，存在高套分组嫌疑",
            "FJ": f"患者 {claim.psn_no} 诊断 {claim.main_diag_code} 存在短期内多次入院记录",
            "DB": f"患者 {claim.setl_id} 住院天数仅{claim.los}天，费用{claim.medfee_sumamt}元，存在低标入院嫌疑",
            "SJ": f"患者 {claim.setl_id} 费用{claim.medfee_sumamt}元，DRG支付{claim.drg_pay}元，费用消耗指数偏低",
            "ZSBP": f"患者 {claim.setl_id} 主诊断{claim.main_diag_code}与主手术{claim.main_oprn_code}缺乏临床关联",
            "PY": f"患者 {claim.setl_id} DRG分组{claim.drg_codg}权重{claim.drg_wt}存在时间序列异常波动",
            "WRZ": f"患者 {claim.setl_id} 住院类型{claim.med_type}但DRG编码为空，未入DRG分组",
            "DFSW": f"患者 {claim.setl_id} DRG权重{claim.drg_wt}较低但患者死亡(离院方式={claim.dscg_way})，需审查死亡合理性",
            "ZY": f"患者 {claim.setl_id} 转院(离院方式={claim.dscg_way})且费用{claim.medfee_sumamt}元，需核实转院必要性",
            "DZ": f"患者 {claim.setl_id} 住院仅{claim.los}天，费用{claim.medfee_sumamt}元，短住病例需核实入院必要性",
            "GQZ": f"患者 {claim.setl_id} DRG权重{claim.drg_wt}异常偏高，需审查诊断编码准确性",
            "ZF": f"患者 {claim.setl_id} 个人负担{claim.psn_part_amt}元/总费用{claim.medfee_sumamt}元，自费比例异常",
            "CE": f"患者 {claim.setl_id} 总费用{claim.medfee_sumamt}元与DRG支付{claim.drg_pay}元差额较大",
            "QSS": f"患者 {claim.setl_id} DRG分组{claim.drg_codg}为手术组但无手术操作编码",
            "CZ": f"患者 {claim.setl_id} 住院天数{claim.los}天异常偏长，需审查治疗合理性",
            "YCDZ": f"患者 {claim.setl_id} 住院仅{claim.los}天但费用{claim.medfee_sumamt}元，住院天数与费用不匹配",
            "CZFY": f"患者 {claim.setl_id} 住院{claim.los}天费用{claim.medfee_sumamt}元，长住高额费用需核实合理性",
            "FYPL": f"患者 {claim.setl_id} 总费用{claim.medfee_sumamt}元偏离DRG支付{claim.drg_pay}元，费用消耗指数异常",
            "FYTC": f"患者 {claim.setl_id} 费用{claim.medfee_sumamt}元远超同类病种，需审查高额费用合理性",
        }
        return reasoning_map.get(rule_type, f"触发DRG规则: {rule_type}")
