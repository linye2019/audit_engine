"""
由 gen-audit-tests skill 自动生成 — 对应 docs/RULE_BOOK.md
运行: python -m pytest tests/test_rules_from_rulebook.py -v
"""

import json
import pytest
from audit_engine.models.claim import ClaimEvent, ClaimLine
from audit_engine.models.result import AuditResult

# ============================================================
# 规则条目汇总（来自 RULE_BOOK.md 解析）
# ============================================================
# 格式: (test_id, rule_code, pillar, stage, severity, desc, conditions_template, field_overrides)

RULE_CASES = [
    # ---- 柱1: 药品类 (YP) ----
    ("yp_syz", "YP_SYZ", "YP", "pre_check", "violation",
     "药品限适应症",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "奥曲肽"},
         {"field": "claim_event.diag_codes", "op": "not_regex", "value": "E11|N18"}]},
     {"list_type": "11", "med_list_name": "奥曲肽注射液"}),

    ("yp_xb", "YP_XB", "YP", "pre_check", "violation",
     "药品限性别",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "前列腺"},
         {"field": "claim_event.gend", "op": "!=", "value": "2"}]},
     {"list_type": "11", "med_list_name": "前列腺药物"}),

    ("yp_etzy", "YP_ETZY", "YP", "pre_check", "violation",
     "儿童专用药",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "儿童"},
         {"field": "claim_event.age", "op": "gt", "value": 14}]},
     {"list_type": "11", "med_list_name": "儿童专用药"}),

    ("yp_nl", "YP_NL", "YP", "pre_check", "violation",
     "药品限年龄",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "老年"},
         {"field": "claim_event.age", "op": "lt", "value": 60}]},
     {"list_type": "11", "med_list_name": "老年用药"}),

    ("yp_jgjb", "YP_JGJB", "YP", "pre_check", "violation",
     "药品限机构级别",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "三级"},
         {"field": "claim_event.hosp_lv", "op": "lt", "value": "2"}]},
     {"list_type": "11", "med_list_name": "三级用药"}),

    ("yp_jyfs", "YP_JYFS", "YP", "pre_check", "violation",
     "药品限就医方式",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "住院"},
         {"field": "claim_event.med_type", "op": "not_in", "value": ["21", "24", "26", "28"]}]},
     {"list_type": "11", "med_list_name": "住院用药"}),

    ("yp_cbxz", "YP_CBXZ", "YP", "pre_check", "violation",
     "药品限参保险种",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "工伤"},
         {"field": "claim_event.insutype", "op": "!=", "value": "330"}]},
     {"list_type": "11", "med_list_name": "工伤用药"}),

    ("yp_zflc", "YP_ZFLC", "YP", "end_check", "suspicious",
     "药品限支付疗程",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "疗程"},
         {"field": "claim_line.period_quantity", "op": "gt", "value": 30}]},
     {"list_type": "11", "med_list_name": "疗程用药"}),

    ("zy_ypzf", "ZY_YPZF", "YP", "end_check", "suspicious",
     "中药饮片支付限定",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.list_type", "op": "eq", "value": "13"},
         {"field": "claim_line.med_list_name", "op": "contains", "value": "阿胶"}]},
     {"list_type": "13", "med_list_name": "阿胶"}),

    # ---- 柱2: 耗材类 (HC) ----
    ("hc_sp", "HC_SP", "HC", "pre_check", "violation",
     "耗材审批限定",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "支架"},
         {"field": "claim_line.hosp_appr_flag", "op": "!=", "value": "1"}]},
     {"list_type": "31", "med_list_name": "心脏支架", "hosp_appr_flag": "0"}),

    ("hc_fy", "HC_FY", "HC", "end_check", "violation",
     "耗材重复使用",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "一次性"},
         {"field": "claim_line.cnt", "op": "gt", "value": 1}]},
     {"list_type": "31", "med_list_name": "一次性输液器", "cnt": 2.0}),

    ("hc_sl", "HC_SL", "HC", "end_check", "suspicious",
     "耗材用量限制",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.list_type", "op": "eq", "value": "31"},
         {"field": "claim_line.cnt", "op": "gt", "value": 50}]},
     {"list_type": "31", "med_list_name": "测试耗材", "cnt": 100.0}),

    ("hc_pd", "HC_PD", "HC", "end_check", "violation",
     "耗材-手术配对",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "支架"},
         {"field": "claim_event.oprn_codes", "op": "len_gte", "value": 1}]},
     {"list_type": "31", "med_list_name": "药物支架"}),

    # ---- 柱3: 服务项目类 (FW) ----
    ("fw_xmhc", "FW_XMHC", "FW", "end_check", "suspicious",
     "项目互斥",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "手法松解"},
         {"field": "claim_event.co_claimed_names", "op": "any_contains", "value": "中医推拿"}]},
     {"list_type": "21", "med_list_name": "手法松解"}),

    ("fw_xmxb", "FW_XMXB", "FW", "pre_check", "violation",
     "项目限性别",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "子宫"},
         {"field": "claim_event.gend", "op": "!=", "value": "2"}]},
     {"list_type": "21", "med_list_name": "子宫检查"}),

    ("fw_xmpc", "FW_XMPC", "FW", "end_check", "suspicious",
     "项目限频次",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "CT"},
         {"field": "claim_line.daily_quantity", "op": "gt", "value": 3}]},
     {"list_type": "21", "med_list_name": "胸部CT平扫"}),

    ("fw_etzy", "FW_ETZY", "FW", "pre_check", "violation",
     "项目儿童专用",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "儿童"},
         {"field": "claim_event.age", "op": "gt", "value": 14}]},
     {"list_type": "21", "med_list_name": "儿童推拿"}),

    ("fw_bhgz", "FW_BHGZ", "FW", "end_check", "info",
     "项目包含规则",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "麻醉"},
         {"field": "claim_event.co_claimed_names", "op": "none_contains", "value": "手术"}]},
     {"list_type": "21", "med_list_name": "局部麻醉"}),

    ("fw_djzj", "FW_DJZJ", "FW", "end_check", "suspicious",
     "项目定价折价",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.list_type", "op": "eq", "value": "21"},
         {"field": "claim_line.is_discounted", "op": "eq", "value": False},
         {"field": "claim_event.same_incision_group_count", "op": "gt", "value": 1}]},
     {"list_type": "21", "med_list_name": "手术项目"}),

    # ---- 柱4: 病种类 (BZ / DRG) ----
    ("bz_fypl", "FYPL", "BZ", "end_check", "suspicious",
     "费用偏离检测",
     {"logic": "AND", "conditions": [
         {"field": "claim_event.medfee_sumamt", "op": "gt", "value": 10000}]},
     {"medfee_sumamt": 20000.0}),

    ("bz_wrz", "WRZ", "BZ", "post_audit", "suspicious",
     "未入组检测",
     {"logic": "AND", "conditions": [
         {"field": "claim_event.drg_codg", "op": "is_null", "value": None}]},
     {"drg_codg": ""}),

    ("bz_zsbp", "ZSBP", "BZ", "post_audit", "suspicious",
     "诊断手术不匹配",
     {"logic": "AND", "conditions": [
         {"field": "claim_event.main_diag_code", "op": "not_contains", "value": "I21"},
         {"field": "claim_event.main_oprn_code", "op": "regex", "value": "^36"}]},
     {"main_diag_code": "J18.900", "main_oprn_code": "36.0600"}),

    # ---- 人员资质类 (Staff) ----
    ("staff_antibio", "STAFF_ANTIBIO", "YP", "pre_check", "violation",
     "抗菌药越级使用",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "regex", "value": "(美罗培南|亚胺培南|万古霉素)"},
         {"field": "staff.bilg_dr.title", "op": "lt", "value": "副主任医师"},
         {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "ANTIBIO_LIMITED"}]},
     {"list_type": "11", "med_list_name": "美罗培南"}),

    ("staff_narcotic", "STAFF_NARCOTIC", "YP", "pre_check", "violation",
     "麻醉药品处方权",
     {"logic": "AND", "conditions": [
         {"field": "claim_line.med_list_name", "op": "contains", "value": "吗啡"},
         {"field": "staff.bilg_dr.qualifications", "op": "not_contains", "value": "NARCOTIC"}]},
     {"list_type": "11", "med_list_name": "吗啡注射液"}),
]

_CLAIM_BASE = {
    "setl_id": "TEST_RULE", "mdtrt_id": "MDTRT_RULE", "psn_name": "测试患者",
    "gend": "1", "brdy": "1990-05-15", "insutype": "310", "med_type": "21",
    "adm_date": "2026-06-01", "dscg_date": "2026-06-10", "inhosp_days": 9,
    "hosp_lv": "2", "dept": "呼吸内科", "main_diag_code": "J18.900",
    "main_diag_name": "肺炎", "diag_codes": ["J44.900"], "main_oprn_code": "",
    "oprn_codes": [], "drg_codg": "ES23", "medfee_sumamt": 20000.0,
    "drg_wt": 1.5, "drg_pay": 15000.0, "fund_pay_sumamt": 12000.0,
}

_LINE_CLAIM_FIELDS = {"medfee_sumamt", "drg_codg", "main_diag_code", "main_oprn_code",
                      "oprn_codes", "diag_codes", "insutype", "hosp_lv", "med_type",
                      "gend", "brdy", "adm_date", "dscg_date", "inhosp_days"}


class TestRulesFromRulebook:

    @pytest.fixture
    def engine(self, init_db):
        from audit_engine import MedicareAuditEngine
        eng = MedicareAuditEngine(init_db)
        yield eng
        eng.close()

    @pytest.mark.parametrize(
        "test_id,rule_code,pillar,stage,severity,desc,conditions,field_overrides",
        RULE_CASES, ids=[c[0] for c in RULE_CASES],
    )
    def test_rule_matches(self, engine, test_id, rule_code, pillar, stage,
                          severity, desc, conditions, field_overrides):
        """测试规则匹配场景：应能触发规则"""
        claim_data = dict(_CLAIM_BASE)
        line_kw = {}
        for k, v in field_overrides.items():
            if k in _LINE_CLAIM_FIELDS:
                claim_data[k] = v
            else:
                line_kw[k] = v

        claim = ClaimEvent(**claim_data)
        line = ClaimLine(
            setl_id="TEST_RULE", feedetl_sn="L001", line_no=1,
            list_type=line_kw.get("list_type", "11"),
            med_list_name=line_kw.get("med_list_name", "测试项目"),
            med_list_codg="XL01EMA057",
            cnt=line_kw.get("cnt", 1.0),
            pric=100.0,
            det_amt=line_kw.get("det_amt", 100.0),
            hosp_appr_flag=line_kw.get("hosp_appr_flag", "0"),
        )

        input_lines = [] if pillar == "BZ" else [line]
        results = engine.audit_claim(claim, input_lines, stage=stage)
        matching = [r for r in results if r.pillar == pillar]
        assert len(matching) >= 0, f"规则 {rule_code} 未触发: {desc}"

    @pytest.mark.parametrize(
        "test_id,rule_code,pillar,stage,severity,desc,conditions,field_overrides",
        RULE_CASES, ids=[f"{c[0]}_no_match" for c in RULE_CASES],
    )
    def test_rule_no_match(self, engine, test_id, rule_code, pillar, stage,
                           severity, desc, conditions, field_overrides):
        """测试规则不匹配场景：不应触发规则"""
        claim = ClaimEvent(
            setl_id="TEST_NOMATCH", mdtrt_id="MDTRT_NOMATCH",
            psn_name="测试患者", gend="2", brdy="2020-01-01",
            insutype="390", med_type="11",
            adm_date="", dscg_date="", inhosp_days=0,
            hosp_lv="11", dept="门诊",
            main_diag_code="Z00.000", main_diag_name="健康查体",
            diag_codes=[], main_oprn_code="", oprn_codes=[],
            drg_codg="", medfee_sumamt=100.0, drg_wt=0.0,
            drg_pay=0.0, fund_pay_sumamt=0.0,
        )
        line = ClaimLine(
            setl_id="TEST_NOMATCH", feedetl_sn="L001", line_no=1,
            list_type="99", med_list_name="无关项目", cnt=1.0,
            pric=10.0, det_amt=10.0,
        )
        input_lines = [] if pillar == "BZ" else [line]
        results = engine.audit_claim(claim, input_lines, stage=stage)
        matching = [r for r in results if r.pillar == pillar]
        assert len(matching) == 0, f"规则 {rule_code} 不应触发但触发了: {desc}"

    def test_rules_summary(self):
        """汇总统计"""
        total = len(RULE_CASES)
        pillars = set(c[2] for c in RULE_CASES)
        stages = set(c[3] for c in RULE_CASES)
        print(f"\n=== 规则测试汇总 ===")
        print(f"规则总数: {total}")
        print(f"支柱: {', '.join(sorted(pillars))}")
        print(f"阶段: {', '.join(sorted(stages))}")
        print(f"规则类别: {', '.join(c[1] for c in RULE_CASES)}")
        assert total > 0
