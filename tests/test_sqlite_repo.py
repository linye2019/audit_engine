import pytest
import sqlite3
from datetime import datetime
from audit_engine.repo.sqlite_repo import SQLiteRepository
from audit_engine.models.claim import ClaimEvent, ClaimLine
from audit_engine.models.result import AuditResult


class TestSQLiteRepository:
    @pytest.fixture
    def repo(self, init_db):
        r = SQLiteRepository(init_db)
        yield r
        r.close()

    def _insert_test_rule(self, conn, rule_code="TEST-001", version=1, is_active=1,
                          pillar="YP", stage="post_audit", severity="violation",
                          conditions='{"logic":"AND","conditions":[]}',
                          rule_name=None):
        name = rule_name or f"测试规则{rule_code}"
        conn.execute("""
            INSERT INTO rule_items (
                rule_code, rule_name, rule_category, rule_subcategory,
                pillar, stage, severity, yp_id, xm_a_id, xm_b_id,
                hc_id, diagnosis_codes, procedure_codes,
                conditions, action, action_message, source_batch, source_reference,
                version, effective_date, expired_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_code, name, "YP_SYZ", "",
            pillar, stage, severity, 1, None, None,
            None, '["J18.9"]', '["36.06"]',
            conditions, "block", "违规说明", "GJ18", "",
            version, None, None, is_active
        ))
        conn.commit()

    def test_init_connection(self, repo):
        assert repo.conn is not None
        assert isinstance(repo.conn, sqlite3.Connection)

    def test_close(self, init_db):
        repo = SQLiteRepository(init_db)
        repo.close()
        with pytest.raises(sqlite3.ProgrammingError):
            repo.conn.execute("SELECT 1")

    def test_load_rules_pre_check(self, repo):
        self._insert_test_rule(repo.conn, "R1", stage="pre_check")
        self._insert_test_rule(repo.conn, "R2", stage="post_audit")
        self._insert_test_rule(repo.conn, "R3", pillar="FW", stage="pre_check")

        rules = repo.load_rules(pillar="YP", stage="pre_check")

        assert len(rules) == 1
        assert rules[0]["rule_code"] == "R1"
        assert rules[0]["stage"] == "pre_check"

    def test_load_rules_end_check(self, repo):
        self._insert_test_rule(repo.conn, "R1", stage="pre_check")
        self._insert_test_rule(repo.conn, "R2", stage="end_check")
        self._insert_test_rule(repo.conn, "R3", stage="post_audit")

        rules = repo.load_rules(pillar="YP", stage="end_check")

        assert len(rules) == 2
        codes = {r["rule_code"] for r in rules}
        assert "R1" in codes
        assert "R2" in codes

    def test_load_rules_post_audit(self, repo):
        self._insert_test_rule(repo.conn, "R1", stage="pre_check")
        self._insert_test_rule(repo.conn, "R2", stage="end_check")
        self._insert_test_rule(repo.conn, "R3", stage="post_audit")

        rules = repo.load_rules(pillar="YP", stage="post_audit")

        assert len(rules) == 3

    def test_load_rules_inactive_excluded(self, repo):
        self._insert_test_rule(repo.conn, "R1", is_active=1)
        self._insert_test_rule(repo.conn, "R2", is_active=0)

        rules = repo.load_rules(pillar="YP", stage="post_audit")

        assert len(rules) == 1
        assert rules[0]["rule_code"] == "R1"

    def test_load_rules_by_date_filter(self, repo):
        conn = repo.conn
        conn.execute("""
            INSERT INTO rule_items (
                rule_code, rule_name, rule_category, pillar, stage, severity,
                conditions, action, version, effective_date, expired_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("R-OLD", "旧规则", "YP_SYZ", "YP", "post_audit", "violation",
              '{"logic":"AND"}', "block", 1, "2026-01-01", "2026-05-01", 1))
        conn.execute("""
            INSERT INTO rule_items (
                rule_code, rule_name, rule_category, pillar, stage, severity,
                conditions, action, version, effective_date, expired_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("R-NEW", "新规则", "YP_SYZ", "YP", "post_audit", "violation",
              '{"logic":"AND"}', "block", 2, "2026-05-01", None, 1))
        conn.commit()

        rules = repo.load_rules(pillar="YP", stage="post_audit", audit_date="2026-03-01")
        assert len(rules) == 1
        assert rules[0]["rule_code"] == "R-OLD"

        rules_new = repo.load_rules(pillar="YP", stage="post_audit", audit_date="2026-06-01")
        assert len(rules_new) == 1
        assert rules_new[0]["rule_code"] == "R-NEW"

    def test_load_drg_rules(self, repo):
        conn = repo.conn
        conn.execute("""
            INSERT INTO drg_rules (
                rule_name, rule_type, conditions, threshold_config, severity, stage, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("DRG-001", "cost_overrun", '{"logic":"AND"}', '{"max_cost": 10000}', "warning", "post_audit", 1))
        conn.commit()

        rules = repo.load_drg_rules(stage="post_audit")
        assert len(rules) == 1
        assert rules[0]["rule_name"] == "DRG-001"

    def test_save_claim(self, repo, sample_claim):
        repo.save_claim(sample_claim)

        row = repo.conn.execute("SELECT * FROM claim_event WHERE setl_id = ?", ("TEST001",)).fetchone()
        assert row is not None
        assert row["psn_name"] == "张三"
        assert row["main_diag_code"] == "J18.900"

    def test_save_lines(self, repo, sample_lines):
        repo.save_lines(sample_lines)

        rows = repo.conn.execute("SELECT * FROM claim_line WHERE setl_id = ?", ("TEST001",)).fetchall()
        assert len(rows) == 3

    def test_save_lines_empty(self, repo):
        repo.save_lines([])

    def test_save_results(self, repo, sample_audit_result):
        results = [sample_audit_result]
        repo.save_results(results)

        rows = repo.conn.execute("SELECT * FROM audit_result WHERE setl_id = ?", ("TEST001",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["rule_code"] == "YP-SYZ-GJ01-0001"
        assert rows[0]["rule_version"] == 1

    def test_save_results_empty(self, repo):
        repo.save_results([])

    def test_save_results_replaces_existing(self, repo, sample_audit_result):
        r1 = sample_audit_result
        r1.line_no = 1
        repo.save_results([r1])

        r2 = AuditResult(
            claim_id="TEST001",
            line_no=2,
            rule_code="NEW-001",
            rule_version=1,
        )
        repo.save_results([r2])

        rows = repo.conn.execute("SELECT * FROM audit_result WHERE setl_id = ?", ("TEST001",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["rule_code"] == "NEW-001"

    def test_update_rule_version(self, repo):
        self._insert_test_rule(repo.conn, "UPG-001", version=1, rule_name="旧名称")

        result = repo.update_rule_version(
            rule_code="UPG-001",
            updates={"rule_name": "新名称", "action_message": "新说明"},
            changed_by="admin"
        )

        assert result["old_version"] == 1
        assert result["new_version"] == 2

        old_row = repo.conn.execute(
            "SELECT is_active, expired_date, rule_name FROM rule_items WHERE rule_code = ? AND version = 1",
            ("UPG-001",)
        ).fetchone()
        assert old_row["is_active"] == 0
        assert old_row["expired_date"] is not None
        assert old_row["rule_name"] == "旧名称"

        new_row = repo.conn.execute(
            "SELECT is_active, expired_date, rule_name, action_message, version FROM rule_items WHERE rule_code = ? AND version = 2",
            ("UPG-001",)
        ).fetchone()
        assert new_row["is_active"] == 1
        assert new_row["expired_date"] is None
        assert new_row["rule_name"] == "新名称"
        assert new_row["action_message"] == "新说明"

    def test_update_rule_version_not_found(self, repo):
        with pytest.raises(ValueError, match="Active rule not found"):
            repo.update_rule_version("NONEXIST", {}, "admin")

    def test_create_snapshot(self, repo):
        self._insert_test_rule(repo.conn, "SNAP-001")
        self._insert_test_rule(repo.conn, "SNAP-002")

        result = repo.create_snapshot(
            snapshot_name="test-snap",
            snapshot_desc="测试快照",
            created_by="tester"
        )

        assert result["snapshot_name"] == "test-snap"
        assert result["rule_count"] >= 2

        row = repo.conn.execute(
            "SELECT * FROM rule_set_snapshot WHERE snapshot_name = ?",
            ("test-snap",)
        ).fetchone()
        assert row is not None
        assert row["created_by"] == "tester"

    def test_create_snapshot_expires_prev(self, repo):
        repo.create_snapshot(snapshot_name="v1", created_by="t1")
        repo.create_snapshot(snapshot_name="v2", created_by="t2")

        rows = repo.conn.execute(
            "SELECT snapshot_name, expired_date FROM rule_set_snapshot ORDER BY created_at"
        ).fetchall()
        assert rows[0]["snapshot_name"] == "v1"
        assert rows[0]["expired_date"] is not None
        assert rows[1]["snapshot_name"] == "v2"
        assert rows[1]["expired_date"] is None

    def test_get_snapshots(self, repo):
        repo.create_snapshot(snapshot_name="v1", created_by="t1")
        repo.conn.execute("INSERT INTO rule_set_snapshot (snapshot_name, created_at) VALUES (?, ?)",
                          ("v2", "2100-01-01 00:00:00"))
        repo.conn.commit()

        snapshots = repo.get_snapshots()
        assert len(snapshots) == 2
        assert snapshots[0]["snapshot_name"] == "v2"

    def test_get_changelog_by_rule_code(self, repo):
        self._insert_test_rule(repo.conn, "LOG-001")

        changelog = repo.get_changelog(rule_code="LOG-001", limit=10)
        assert len(changelog) >= 1
        assert changelog[0]["rule_code"] == "LOG-001"

    def test_get_changelog_by_rule_id(self, repo):
        self._insert_test_rule(repo.conn, "LOG-002")
        row = repo.conn.execute("SELECT id FROM rule_items WHERE rule_code = ?", ("LOG-002",)).fetchone()

        changelog = repo.get_changelog(rule_id=row["id"], limit=10)
        assert len(changelog) >= 1
        assert changelog[0]["rule_id"] == row["id"]

    def test_get_changelog_limit(self, repo):
        self._insert_test_rule(repo.conn, "LIMIT-001")

        changelog = repo.get_changelog(rule_code="LIMIT-001", limit=1)
        assert len(changelog) <= 1

    def test_update_rule_version_creates_changelog(self, repo):
        self._insert_test_rule(repo.conn, "VER-CHG-001", version=1)

        before = repo.get_changelog(rule_code="VER-CHG-001")

        repo.update_rule_version("VER-CHG-001", {"rule_name": "更新后"}, "admin")

        after = repo.get_changelog(rule_code="VER-CHG-001")
        assert len(after) > len(before)
