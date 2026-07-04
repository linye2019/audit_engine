import pytest
from unittest.mock import Mock
from audit_engine.core.context import ContextBuilder
from audit_engine.models.claim import ClaimEvent, ClaimLine


class TestContextBuilder:
    @pytest.fixture
    def builder(self):
        conn = Mock()
        conn.execute.side_effect = Exception("no DB needed for basic tests")
        return ContextBuilder(conn)

    @pytest.fixture
    def builder_no_db(self):
        import sqlite3
        conn = Mock(spec=sqlite3.Connection)
        conn.execute.side_effect = sqlite3.OperationalError("no table")
        return ContextBuilder(conn)

    def test_build_line_context_basic(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)

        assert "claim_event" in ctx
        assert "claim_line" in ctx
        assert ctx["claim_event"]["setl_id"] == "TEST001"
        assert ctx["claim_event"]["gend"] == "1"
        assert ctx["claim_line"]["med_list_name"] == "阿莫西林胶囊"
        assert ctx["claim_line"]["list_type"] == "11"

    def test_build_line_context_all_diagnoses(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)

        all_diags = ctx["claim_event"]["all_diagnoses"]
        assert "J18.900" in all_diags
        assert "J44.900" in all_diags
        assert "E11.900" in all_diags
        assert len(all_diags) == 3

    def test_build_line_context_co_claimed(self, builder_no_db, sample_claim, sample_lines):
        drug_line = sample_lines[0]
        ctx = builder_no_db.build_line_context(sample_claim, drug_line, sample_lines)

        co_names = ctx["claim_event"]["co_claimed_names"]
        assert "胸部CT平扫" in co_names
        assert "一次性输液器" in co_names
        assert "阿莫西林胶囊" not in co_names
        assert len(co_names) == 2

    def test_build_line_context_co_claimed_with_line_no(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="", line_no=1, list_type="11", med_list_name="药A")
        line2 = ClaimLine(setl_id="T1", feedetl_sn="", line_no=2, list_type="11", med_list_name="药B")
        claim = ClaimEvent(setl_id="T1")

        ctx = builder_no_db.build_line_context(claim, line1, [line1, line2])

        co_names = ctx["claim_event"]["co_claimed_names"]
        assert "药B" in co_names
        assert "药A" not in co_names

    def test_build_line_context_daily_quantity(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)

        assert ctx["claim_line"]["daily_quantity"] == 10.0

    def test_build_line_context_usage_days(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)

        assert ctx["claim_line"]["usage_days"] == 9

    def test_build_line_context_usage_days_no_dates(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", adm_date="", dscg_date="")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)

        assert ctx["claim_line"]["usage_days"] == 1

    def test_build_line_context_period_quantity(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="11", med_list_codg="CODE1", med_list_name="药A", cnt=5.0)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L2", list_type="11", med_list_codg="CODE1", med_list_name="药A", cnt=3.0)
        line3 = ClaimLine(setl_id="T1", feedetl_sn="L3", list_type="11", med_list_codg="CODE2", med_list_name="药B", cnt=10.0)

        ctx = builder_no_db.build_line_context(sample_claim, line1, [line1, line2, line3])

        assert ctx["claim_line"]["period_quantity"] == 8.0

    def test_build_line_context_is_internet_false(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)
        assert ctx["claim_event"]["is_internet"] is False

    def test_build_line_context_is_internet_true_hosp_lv(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", hosp_lv="互联网医院")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)
        assert ctx["claim_event"]["is_internet"] is True

    def test_build_line_context_is_internet_true_med_type(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", med_type="互联网门诊")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)
        assert ctx["claim_event"]["is_internet"] is True

    def test_build_line_context_is_discounted_false(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)
        assert ctx["claim_line"]["is_discounted"] is False
        assert ctx["claim_line"]["price_margin"] == 0.0

    def test_build_line_context_is_discounted_true(self, builder_no_db, sample_claim):
        line = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="11", med_list_name="药A", cnt=10.0, pric=5.0, det_amt=40.0)
        ctx = builder_no_db.build_line_context(sample_claim, line)
        assert ctx["claim_line"]["is_discounted"] is True
        assert ctx["claim_line"]["price_margin"] == -10.0

    def test_build_line_context_duration_hours(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)
        assert ctx["claim_line"]["duration_hours"] == 216.0

    def test_build_line_context_ward_type_icu(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", dept="ICU病房")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)
        assert ctx["claim_event"]["ward_type"] == "危重症"

    def test_build_line_context_ward_type_newborn(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", dept="新生儿科")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)
        assert ctx["claim_event"]["ward_type"] == "新生儿"

    def test_build_line_context_ward_type_psych(self, builder_no_db, sample_drug_line):
        claim = ClaimEvent(setl_id="T1", dept="精神科")
        ctx = builder_no_db.build_line_context(claim, sample_drug_line)
        assert ctx["claim_event"]["ward_type"] == "精神病"

    def test_build_line_context_ward_type_empty(self, builder_no_db, sample_claim, sample_drug_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_drug_line)
        assert ctx["claim_event"]["ward_type"] == ""

    def test_build_line_context_is_highest_price_true(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="11", med_list_name="贵药", cnt=1.0, pric=100.0, det_amt=100.0)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L2", list_type="11", med_list_name="便宜药", cnt=1.0, pric=10.0, det_amt=10.0)

        ctx = builder_no_db.build_line_context(sample_claim, line1, [line1, line2])
        assert ctx["claim_line"]["is_highest_price"] is True

    def test_build_line_context_is_highest_price_false(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="11", med_list_name="便宜药", cnt=1.0, pric=10.0, det_amt=10.0)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L2", list_type="11", med_list_name="贵药", cnt=1.0, pric=100.0, det_amt=100.0)

        ctx = builder_no_db.build_line_context(sample_claim, line1, [line1, line2])
        assert ctx["claim_line"]["is_highest_price"] is False

    def test_build_line_context_consumable_not_basic(self, builder_no_db, sample_claim, sample_consumable_line):
        ctx = builder_no_db.build_line_context(sample_claim, sample_consumable_line)
        assert ctx["claim_line"]["is_basic_material"] is False
        assert ctx["claim_line"]["is_special_function"] is False

    def test_build_event_context(self, builder_no_db, sample_claim):
        ctx = builder_no_db.build_event_context(sample_claim)

        assert ctx["claim_event"]["setl_id"] == "TEST001"
        assert ctx["claim_event"]["med_type"] == "21"
        assert ctx["claim_event"]["drg_codg"] == "ES23"
        assert ctx["claim_event"]["medfee_sumamt"] == 20000.0
        assert isinstance(ctx["claim_event"]["diag_codes"], list)
        assert len(ctx["claim_event"]["diag_codes"]) == 2

    def test_build_line_context_same_incision_group(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="31", med_list_name="耗材A", oprn_code_used="36.0600", cnt=1.0)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L2", list_type="31", med_list_name="耗材B", oprn_code_used="33.2400", cnt=1.0)
        line3 = ClaimLine(setl_id="T1", feedetl_sn="L3", list_type="31", med_list_name="耗材C", oprn_code_used="", cnt=1.0)

        ctx = builder_no_db.build_line_context(sample_claim, line1, [line1, line2, line3])
        assert ctx["claim_event"]["same_incision_group_count"] == 1

    def test_build_line_context_same_session_modes(self, builder_no_db, sample_claim):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", list_type="21", med_list_name="常规放疗", cnt=1.0)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L2", list_type="21", med_list_name="适形放疗", cnt=1.0)
        line3 = ClaimLine(setl_id="T1", feedetl_sn="L3", list_type="21", med_list_name="CT检查", cnt=1.0)

        ctx = builder_no_db.build_line_context(sample_claim, line1, [line1, line2, line3])
        assert ctx["claim_event"]["same_session_modes_count"] == 2
