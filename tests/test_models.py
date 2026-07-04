import pytest
from datetime import date
from audit_engine.models.claim import ClaimEvent, ClaimLine


class TestClaimEvent:
    def test_claim_event_creation(self, sample_claim):
        assert sample_claim.setl_id == "TEST001"
        assert sample_claim.psn_name == "张三"
        assert sample_claim.gend == "1"
        assert sample_claim.med_type == "21"

    def test_age_property_valid(self, sample_claim):
        age = sample_claim.age
        assert age is not None
        assert isinstance(age, int)
        assert age > 0

    def test_age_property_no_brdy(self):
        claim = ClaimEvent(setl_id="T1", brdy="")
        assert claim.age is None

    def test_age_property_invalid_brdy(self):
        claim = ClaimEvent(setl_id="T1", brdy="invalid")
        assert claim.age is None

    def test_los_from_inhosp_days(self, sample_claim):
        assert sample_claim.los == 9

    def test_los_from_dates(self):
        claim = ClaimEvent(
            setl_id="T1",
            adm_date="2026-06-01",
            dscg_date="2026-06-10",
            inhosp_days=0,
        )
        assert claim.los == 10

    def test_los_no_dates(self):
        claim = ClaimEvent(setl_id="T1", inhosp_days=0)
        assert claim.los is None

    def test_los_invalid_dates(self):
        claim = ClaimEvent(
            setl_id="T1",
            adm_date="invalid",
            dscg_date="invalid",
            inhosp_days=0,
        )
        assert claim.los is None

    def test_diag_codes_default_empty_list(self):
        claim = ClaimEvent(setl_id="T1")
        assert claim.diag_codes == []
        assert claim.oprn_codes == []

    def test_default_values(self):
        claim = ClaimEvent(setl_id="T1")
        assert claim.medfee_sumamt == 0.0
        assert claim.drg_wt == 0.0
        assert claim.hosp_lv == ""


class TestClaimLine:
    def test_claim_line_creation(self, sample_drug_line):
        assert sample_drug_line.setl_id == "TEST001"
        assert sample_drug_line.line_no == 1
        assert sample_drug_line.list_type == "11"
        assert sample_drug_line.med_list_name == "阿莫西林胶囊"

    def test_default_values(self):
        line = ClaimLine(setl_id="T1", feedetl_sn="L1")
        assert line.cnt == 0.0
        assert line.pric == 0.0
        assert line.det_amt == 0.0
        assert line.matched_catalog_id is None
        assert line.match_confidence == 0.0
        assert line.match_method == ""

    def test_numeric_fields(self, sample_project_line):
        assert isinstance(sample_project_line.cnt, float)
        assert isinstance(sample_project_line.pric, float)
        assert isinstance(sample_project_line.det_amt, float)

    def test_consumable_line(self, sample_consumable_line):
        assert sample_consumable_line.list_type == "31"
        assert sample_consumable_line.med_list_codg == "CUC001"

    def test_line_equality(self):
        line1 = ClaimLine(setl_id="T1", feedetl_sn="L1", line_no=1)
        line2 = ClaimLine(setl_id="T1", feedetl_sn="L1", line_no=1)
        assert line1 == line2
