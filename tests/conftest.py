import os
import sys
import tempfile
import sqlite3
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit_engine.models.claim import ClaimEvent, ClaimLine
from audit_engine.models.result import AuditResult


SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")


@pytest.fixture
def sample_claim():
    return ClaimEvent(
        setl_id="TEST001",
        mdtrt_id="MDTRT001",
        psn_no="PSN001",
        psn_name="张三",
        gend="1",
        brdy="1990-05-15",
        insutype="310",
        insu_region="110000",
        med_type="21",
        adm_date="2026-06-01",
        dscg_date="2026-06-10",
        inhosp_days=9,
        hosp_lv="2",
        dept="呼吸内科",
        adm_way="2",
        dscg_way="1",
        main_diag_code="J18.900",
        main_diag_name="肺炎",
        diag_codes=["J44.900", "E11.900"],
        main_oprn_code="33.2400",
        oprn_codes=["36.0600"],
        drg_codg="ES23",
        drg_wt=1.5,
        drg_pay=15000.0,
        medfee_sumamt=20000.0,
        fund_pay_sumamt=12000.0,
        acct_pay_sumamt=2000.0,
        psn_part_amt=6000.0,
        cash_payamt=2000.0,
    )


@pytest.fixture
def sample_drug_line():
    return ClaimLine(
        setl_id="TEST001",
        feedetl_sn="L001",
        mdtrt_id="MDTRT001",
        fee_ocur_time="2026-06-01 09:00:00",
        line_no=1,
        list_type="11",
        med_list_name="阿莫西林胶囊",
        med_list_codg="XL01EMA057",
        medins_list_codg="Y001",
        cnt=10.0,
        pric=2.5,
        pric_ut="粒",
        det_amt=25.0,
        chrgitm_lv="1",
        bilg_drord_no="ORD001",
        drord_type="1",
        bilg_dept_codg="DEPT01",
        bilg_dept_name="呼吸内科",
        bilg_dr_codg="DR001",
        bilg_drord_dr_name="李医生",
        acord_dept_codg="DEPT02",
        acord_dept_name="药房",
        orders_dr_codg="DR002",
        orders_dr_name="王药师",
        dosage_form="胶囊剂",
        tcmdrug_used_way="",
        oprn_code_used="",
        used_qty=10.0,
        hosp_appr_flag="0",
        etip_flag="0",
        dscg_tkdrug_flag="0",
        matn_fee_flag="0",
        clr_type="21",
        fund_pay_type="",
        comb_no="",
        memo="",
        raw_data="",
    )


@pytest.fixture
def sample_project_line():
    return ClaimLine(
        setl_id="TEST001",
        feedetl_sn="L002",
        mdtrt_id="MDTRT001",
        fee_ocur_time="2026-06-02 10:00:00",
        line_no=2,
        list_type="21",
        med_list_name="胸部CT平扫",
        med_list_codg="CT001",
        cnt=1.0,
        pric=300.0,
        det_amt=300.0,
        chrgitm_lv="2",
    )


@pytest.fixture
def sample_consumable_line():
    return ClaimLine(
        setl_id="TEST001",
        feedetl_sn="L003",
        mdtrt_id="MDTRT001",
        fee_ocur_time="2026-06-03 14:00:00",
        line_no=3,
        list_type="31",
        med_list_name="一次性输液器",
        med_list_codg="CUC001",
        cnt=5.0,
        pric=3.0,
        det_amt=15.0,
        chrgitm_lv="1",
    )


@pytest.fixture
def sample_lines(sample_drug_line, sample_project_line, sample_consumable_line):
    return [sample_drug_line, sample_project_line, sample_consumable_line]


@pytest.fixture
def sample_audit_result():
    return AuditResult(
        claim_id="TEST001",
        line_no=1,
        rule_id=1,
        rule_code="YP-SYZ-GJ01-0001",
        rule_category="YP_SYZ",
        pillar="YP",
        stage="post_audit",
        verdict="violation",
        severity="violation",
        matched_facts={"diag_match": True, "age": 36},
        rule_text='{"logic":"AND","conditions":[]}',
        reasoning="诊断不匹配",
        action="block",
        engine_version="1.1.0",
        rule_version=1,
    )


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def init_db(temp_db_path):
    conn = sqlite3.connect(temp_db_path)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    yield temp_db_path


@pytest.fixture
def db_conn(init_db):
    conn = sqlite3.connect(init_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
