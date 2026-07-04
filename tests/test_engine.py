import pytest
import json
from audit_engine import MedicareAuditEngine
from audit_engine.models.claim import ClaimEvent, ClaimLine
from audit_engine.models.result import AuditResult


class TestMedicareAuditEngine:
    @pytest.fixture
    def engine(self, init_db):
        eng = MedicareAuditEngine(init_db)
        yield eng
        eng.close()

    def _insert_drug_catalog(self, conn, yp_id=1, chs_code="XL01EMA057", drug_name="阿莫西林胶囊"):
        conn.execute("INSERT INTO YPML (id, chs_code, drug_name, atc_code) VALUES (?, ?, ?, ?)",
                     (yp_id, chs_code, drug_name, "J01CA04"))
        conn.commit()

    def _insert_rule(self, conn, rule_id=1, rule_code="TEST-001", pillar="YP", stage="post_audit",
                     severity="violation", yp_id=1,
                     conditions='{"logic":"AND","conditions":[{"field":"claim_event.age","op":"gt","value":10}]}',
                     action="block", action_message="年龄不符",
                     diagnosis_codes=None, version=1):
        conn.execute("""
            INSERT INTO rule_items (
                id, rule_code, rule_name, rule_category, pillar, stage, severity,
                yp_id, conditions, action, action_message, diagnosis_codes, version, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (rule_id, rule_code, f"测试规则{rule_code}", "YP_SYZ", pillar, stage, severity,
              yp_id, conditions, action, action_message,
              json.dumps(diagnosis_codes) if diagnosis_codes else None, version))
        conn.commit()

    def test_engine_initialization(self, engine):
        assert engine is not None
        assert engine.ENGINE_VERSION == "1.1.0"
        assert engine.repo is not None
        assert engine.evaluator is not None
        assert engine.matcher is not None
        assert engine.context_builder is not None

    def test_audit_claim_drug_violation(self, engine, sample_claim):
        conn = engine.conn
        self._insert_drug_catalog(conn)
        self._insert_rule(conn, conditions='{"logic":"AND","conditions":[]}')

        line = ClaimLine(
            setl_id="TEST001",
            feedetl_sn="L001",
            list_type="11",
            med_list_codg="XL01EMA057",
            med_list_name="阿莫西林胶囊",
            cnt=10.0,
            pric=2.5,
            det_amt=25.0,
            line_no=1,
        )

        results = engine.audit_claim(sample_claim, [line], stage="post_audit")

        assert len(results) >= 1
        assert results[0].verdict == "violation"
        assert results[0].pillar == "YP"
        assert results[0].rule_code == "TEST-001"
        assert results[0].rule_version == 1

    def test_audit_claim_no_match_no_rules(self, engine, sample_claim):
        line = ClaimLine(
            setl_id="TEST001",
            feedetl_sn="L001",
            list_type="11",
            med_list_codg="UNKNOWN",
            med_list_name="未知药品",
            line_no=1,
        )

        results = engine.audit_claim(sample_claim, [line], stage="post_audit")

        assert isinstance(results, list)

    def test_audit_claim_unknown_list_type(self, engine, sample_claim):
        line = ClaimLine(
            setl_id="TEST001",
            feedetl_sn="L001",
            list_type="99",
            med_list_name="未知类型",
            line_no=1,
        )

        results = engine.audit_claim(sample_claim, [line], stage="post_audit")
        assert results == []

    def test_audit_claim_drg_event_level(self, engine, sample_claim):
        conn = engine.conn
        conn.execute("""
            INSERT INTO drg_rules (
                rule_name, rule_type, conditions, threshold_config, severity, stage, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
        """, ("DRG-费用超高", "cost_overrun",
              '{"logic":"AND","conditions":[{"field":"claim_event.medfee_sumamt","op":"gt","value":1000}]}',
              '{"max_cost": 1000}', "warning", "post_audit"))
        conn.commit()

        results = engine.audit_claim(sample_claim, [], stage="post_audit")

        drg_results = [r for r in results if r.pillar == "BZ"]
        assert len(drg_results) >= 1
        assert drg_results[0].rule_category == "cost_overrun"

    def test_audit_claim_outpatient_no_drg(self, engine):
        claim = ClaimEvent(setl_id="OUT001", med_type="11")
        line = ClaimLine(setl_id="OUT001", feedetl_sn="L1", list_type="11", line_no=1)

        results = engine.audit_claim(claim, [line], stage="post_audit")
        drg_results = [r for r in results if r.pillar == "BZ"]
        assert len(drg_results) == 0

    def test_rule_cache(self, engine, sample_claim):
        conn = engine.conn
        self._insert_drug_catalog(conn)
        self._insert_rule(conn, conditions='{"logic":"AND","conditions":[]}')

        line = ClaimLine(
            setl_id="TEST001", feedetl_sn="L001",
            list_type="11", med_list_codg="XL01EMA057",
            med_list_name="阿莫西林胶囊", line_no=1,
        )

        r1 = engine.audit_claim(sample_claim, [line], stage="post_audit")
        r2 = engine.audit_claim(sample_claim, [line], stage="post_audit")

        assert len(r1) == len(r2)
        assert hasattr(engine, '_rule_cache')

    def test_extract_name_keyword(self):
        from audit_engine.core.engine import MedicareAuditEngine

        cond1 = '{"logic":"AND","conditions":[{"field":"med_list_name","op":"contains","value":"阿莫西林"}]}'
        kw1 = MedicareAuditEngine._extract_name_keyword(cond1)
        assert kw1 == "阿莫西林"

        kw2 = MedicareAuditEngine._extract_name_keyword("")
        assert kw2 == ""

        kw3 = MedicareAuditEngine._extract_name_keyword(None)
        assert kw3 == ""

        kw4 = MedicareAuditEngine._extract_name_keyword("invalid json")
        assert kw4 == ""

    def test_entity_matches_drug(self, engine, sample_drug_line):
        rule = {"yp_id": 1}
        match = {"table": "YP", "id": 1, "confidence": 1.0, "method": "code"}
        assert engine._entity_matches(rule, sample_drug_line, match) is True

        match2 = {"table": "YP", "id": 2, "confidence": 1.0, "method": "code"}
        assert engine._entity_matches(rule, sample_drug_line, match2) is False

    def test_entity_matches_no_entity_id(self, engine, sample_drug_line):
        rule = {}
        assert engine._entity_matches(rule, sample_drug_line, None) is True

    def test_entity_matches_project(self, engine, sample_project_line):
        rule = {"xm_a_id": 10}
        match = {"table": "FW", "id": 10, "confidence": 1.0, "method": "code"}
        assert engine._entity_matches(rule, sample_project_line, match) is True

    def test_entity_matches_consumable(self, engine, sample_consumable_line):
        rule = {"hc_id": 5}
        match = {"table": "HC", "id": 5, "confidence": 1.0, "method": "code"}
        assert engine._entity_matches(rule, sample_consumable_line, match) is True

    def test_build_result_violation(self, engine, sample_claim, sample_drug_line):
        rule = {
            "id": 1,
            "rule_code": "TEST-001",
            "rule_category": "YP_SYZ",
            "pillar": "YP",
            "stage": "post_audit",
            "severity": "violation",
            "action": "block",
            "action_message": "违规提示",
            "version": 2,
            "conditions": '{"logic":"AND","conditions":[{"field":"age","op":"gt","value":10}]}',
            "yp_id": 1,
            "diagnosis_codes": '["J18.9"]',
        }
        match = {"id": 1}
        context = {"claim_line": {"age": 5}, "claim_event": {}}

        result = engine._build_result(sample_claim, sample_drug_line, rule, match, context)

        assert isinstance(result, AuditResult)
        assert result.verdict == "violation"
        assert result.action == "block"
        assert result.rule_version == 2
        assert result.rule_code == "TEST-001"
        assert "yp_id" in result.matched_facts
        assert "conditions_checked" in result.matched_facts

    def test_save_results_delegates(self, engine, sample_audit_result):
        engine.save_results([sample_audit_result])
        row = engine.conn.execute("SELECT * FROM audit_result WHERE setl_id = ?", ("TEST001",)).fetchone()
        assert row is not None
        assert row["rule_code"] == "YP-SYZ-GJ01-0001"

    def test_save_claim_delegates(self, engine, sample_claim):
        engine.save_claim(sample_claim)
        row = engine.conn.execute("SELECT * FROM claim_event WHERE setl_id = ?", ("TEST001",)).fetchone()
        assert row is not None
        assert row["psn_name"] == "张三"

    def test_save_lines_delegates(self, engine, sample_lines):
        engine.save_lines(sample_lines)
        rows = engine.conn.execute("SELECT * FROM claim_line WHERE setl_id = ?", ("TEST001",)).fetchall()
        assert len(rows) == 3

    def test_close(self, init_db):
        engine = MedicareAuditEngine(init_db)
        engine.close()
        import sqlite3
        with pytest.raises(sqlite3.ProgrammingError):
            engine.conn.execute("SELECT 1")
