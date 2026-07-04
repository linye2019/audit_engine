import json
import sqlite3
from datetime import datetime
from typing import Optional
from ..models.claim import ClaimEvent, ClaimLine
from ..models.result import AuditResult


class SQLiteRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def load_rules(self, pillar: str, stage: str, audit_date: str = None) -> list[dict]:
        fields = """
            id, rule_code, rule_name, rule_category, rule_subcategory,
            pillar, stage, severity, yp_id, xm_a_id, xm_b_id,
            hc_id, diagnosis_codes, procedure_codes,
            conditions, action, action_message, source_batch, version
        """

        if audit_date is None:
            audit_date = datetime.now().strftime("%Y-%m-%d")

        date_filter = """
            AND (effective_date IS NULL OR effective_date <= ?)
            AND (expired_date IS NULL OR expired_date > ?)
        """

        if stage == "pre_check":
            query = f"""
                SELECT {fields}
                FROM rule_items
                WHERE pillar = ? AND is_active = 1
                  AND stage = 'pre_check'
                  AND severity = 'violation'
                  {date_filter}
                ORDER BY severity DESC
            """
            rows = self.conn.execute(query, (pillar, audit_date, audit_date)).fetchall()
        elif stage == "mid_check":
            # 在院日终审核：级联 pre_check 规则 + 累计类规则（频次/疗程），仅 violation
            query = f"""
                SELECT {fields}
                FROM rule_items
                WHERE pillar = ? AND is_active = 1
                  AND stage IN ('pre_check', 'mid_check')
                  AND severity = 'violation'
                  {date_filter}
                ORDER BY severity DESC
            """
            rows = self.conn.execute(query, (pillar, audit_date, audit_date)).fetchall()
        elif stage == "end_check":
            query = f"""
                SELECT {fields}
                FROM rule_items
                WHERE pillar = ? AND is_active = 1
                  AND stage IN ('pre_check', 'mid_check', 'end_check')
                  {date_filter}
                ORDER BY severity DESC
            """
            rows = self.conn.execute(query, (pillar, audit_date, audit_date)).fetchall()
        else:
            query = f"""
                SELECT {fields}
                FROM rule_items
                WHERE pillar = ? AND is_active = 1
                  {date_filter}
                ORDER BY severity DESC
            """
            rows = self.conn.execute(query, (pillar, audit_date, audit_date)).fetchall()

        return [dict(row) for row in rows]

    def load_drg_rules(self, stage: str, audit_date: str = None) -> list[dict]:
        if audit_date is None:
            from datetime import datetime
            audit_date = datetime.now().strftime("%Y-%m-%d")

        query = """
            SELECT id, rule_name, rule_type, conditions, threshold_config, severity
            FROM drg_rules
            WHERE (is_active = 1 OR is_active IS NULL)
              AND (stage = ? OR stage = 'post_audit')
              AND (effective_date IS NULL OR effective_date <= ?)
              AND (expired_date IS NULL OR expired_date > ?)
            ORDER BY severity DESC
        """
        rows = self.conn.execute(query, (stage, audit_date, audit_date)).fetchall()
        return [dict(row) for row in rows]

    def save_results(self, results: list[AuditResult]):
        if not results:
            return
        setl_ids = set(r.claim_id for r in results)
        for sid in setl_ids:
            self.conn.execute("DELETE FROM audit_result WHERE setl_id = ?", (sid,))
        for r in results:
            self.conn.execute("""
                INSERT INTO audit_result (
                    setl_id, line_no, rule_id, rule_code, rule_category, pillar, stage,
                    verdict, severity, matched_facts, rule_text, reasoning,
                    action, engine_version, rule_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.claim_id, r.line_no, r.rule_id, r.rule_code, r.rule_category, r.pillar, r.stage,
                r.verdict, r.severity, json.dumps(r.matched_facts, ensure_ascii=False),
                r.rule_text, r.reasoning, r.action, r.engine_version, r.rule_version,
            ))
        self.conn.commit()

    def save_claim(self, claim: ClaimEvent):
        self.conn.execute("""
            INSERT OR REPLACE INTO claim_event (
                setl_id, mdtrt_id, psn_no, psn_name, gend, brdy, insutype,
                insu_region, med_type, adm_date, dscg_date, inhosp_days,
                hosp_lv, dept, adm_way, dscg_way, main_diag_code,
                main_diag_name, diag_codes, main_oprn_code, oprn_codes,
                drg_codg, drg_wt, drg_pay, medfee_sumamt, fund_pay_sumamt,
                acct_pay_sumamt, psn_part_amt, cash_payamt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim.setl_id, claim.mdtrt_id, claim.psn_no, claim.psn_name, claim.gend, claim.brdy,
            claim.insutype, claim.insu_region, claim.med_type, claim.adm_date,
            claim.dscg_date, claim.inhosp_days, claim.hosp_lv, claim.dept,
            claim.adm_way, claim.dscg_way, claim.main_diag_code, claim.main_diag_name,
            json.dumps(claim.diag_codes), claim.main_oprn_code,
            json.dumps(claim.oprn_codes), claim.drg_codg, claim.drg_wt,
            claim.drg_pay, claim.medfee_sumamt, claim.fund_pay_sumamt,
            claim.acct_pay_sumamt, claim.psn_part_amt, claim.cash_payamt,
        ))
        self.conn.commit()

    def save_lines(self, lines: list[ClaimLine]):
        if not lines:
            return
        setl_id = lines[0].setl_id
        self.conn.execute("DELETE FROM claim_line WHERE setl_id = ?", (setl_id,))
        for line in lines:
            self.conn.execute("""
                INSERT INTO claim_line (
                    setl_id, feedetl_sn, mdtrt_id, fee_ocur_time, line_no, list_type,
                    med_list_name, med_list_codg, medins_list_codg,
                    cnt, pric, pric_ut, det_amt, chrgitm_lv, matched_catalog_id,
                    match_confidence, match_method, bilg_drord_no, drord_type,
                    bilg_dept_codg, bilg_dept_name, bilg_dr_codg,
                    bilg_drord_dr_name, acord_dept_codg, acord_dept_name,
                    orders_dr_codg, orders_dr_name, exec_dept_codg, exec_dept_name,
                    dosage_form, tcmdrug_used_way,
                    oprn_code_used, used_qty, hosp_appr_flag, etip_flag,
                    dscg_tkdrug_flag, matn_fee_flag, clr_type, fund_pay_type,
                    comb_no, memo, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                line.setl_id, line.feedetl_sn, line.mdtrt_id, line.fee_ocur_time,
                line.line_no, line.list_type, line.med_list_name,
                line.med_list_codg, line.medins_list_codg,
                line.cnt, line.pric, line.pric_ut, line.det_amt,
                line.chrgitm_lv, line.matched_catalog_id, line.match_confidence,
                line.match_method, line.bilg_drord_no, line.drord_type,
                line.bilg_dept_codg, line.bilg_dept_name, line.bilg_dr_codg,
                line.bilg_drord_dr_name, line.acord_dept_codg, line.acord_dept_name,
                line.orders_dr_codg, line.orders_dr_name,
                line.exec_dept_codg, line.exec_dept_name,
                line.dosage_form, line.tcmdrug_used_way, line.oprn_code_used, line.used_qty,
                line.hosp_appr_flag, line.etip_flag, line.dscg_tkdrug_flag,
                line.matn_fee_flag, line.clr_type, line.fund_pay_type,
                line.comb_no, line.memo, line.raw_data,
            ))
        self.conn.commit()

    def update_rule_version(self, rule_code: str, updates: dict, changed_by: str = "system"):
        current_date = datetime.now().strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT id, version, rule_name, rule_category, rule_subcategory, pillar, stage, severity, "
            "yp_id, xm_a_id, xm_b_id, hc_id, diagnosis_codes, procedure_codes, "
            "conditions, action, action_message, source_batch, source_reference, effective_date "
            "FROM rule_items WHERE rule_code = ? AND is_active = 1 AND (expired_date IS NULL OR expired_date > ?)",
            (rule_code, current_date)
        ).fetchone()

        if not row:
            raise ValueError(f"Active rule not found: {rule_code}")

        old_version = row["version"]
        new_version = old_version + 1

        self.conn.execute(
            "UPDATE rule_items SET is_active = 0, expired_date = ? WHERE id = ?",
            (current_date, row["id"])
        )

        new_effective_date = updates.get("effective_date", current_date)
        new_expired_date = updates.get("expired_date")

        self.conn.execute("""
            INSERT INTO rule_items (
                rule_code, rule_name, rule_category, rule_subcategory, pillar, stage, severity,
                yp_id, xm_a_id, xm_b_id, hc_id, diagnosis_codes, procedure_codes,
                conditions, action, action_message, source_batch, source_reference,
                version, effective_date, expired_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_code,
            updates.get("rule_name", row["rule_name"]),
            updates.get("rule_category", row["rule_category"]),
            updates.get("rule_subcategory", row["rule_subcategory"]),
            updates.get("pillar", row["pillar"]),
            updates.get("stage", row["stage"]),
            updates.get("severity", row["severity"]),
            updates.get("yp_id", row["yp_id"]),
            updates.get("xm_a_id", row["xm_a_id"]),
            updates.get("xm_b_id", row["xm_b_id"]),
            updates.get("hc_id", row["hc_id"]),
            updates.get("diagnosis_codes", row["diagnosis_codes"]),
            updates.get("procedure_codes", row["procedure_codes"]),
            updates.get("conditions", row["conditions"]),
            updates.get("action", row["action"]),
            updates.get("action_message", row["action_message"]),
            updates.get("source_batch", row["source_batch"]),
            updates.get("source_reference", row["source_reference"]),
            new_version,
            new_effective_date,
            new_expired_date,
            1
        ))

        self.conn.commit()
        return {"rule_code": rule_code, "old_version": old_version, "new_version": new_version}

    def create_snapshot(self, snapshot_name: str, snapshot_desc: str = "", created_by: str = "system"):
        current_date = datetime.now().strftime("%Y-%m-%d")
        rule_count = self.conn.execute(
            "SELECT COUNT(*) FROM rule_items WHERE is_active = 1 AND (expired_date IS NULL OR expired_date > ?)",
            (current_date,)
        ).fetchone()[0]

        self.conn.execute("""
            INSERT INTO rule_set_snapshot (
                snapshot_name, snapshot_desc, rule_count, created_by, effective_date
            ) VALUES (?, ?, ?, ?, ?)
        """, (snapshot_name, snapshot_desc, rule_count, created_by, current_date))

        self.conn.execute(
            "UPDATE rule_set_snapshot SET expired_date = ? WHERE expired_date IS NULL AND snapshot_name != ?",
            (current_date, snapshot_name)
        )

        self.conn.commit()
        return {"snapshot_name": snapshot_name, "rule_count": rule_count, "created_at": current_date}

    def get_snapshots(self) -> list[dict]:
        query = """
            SELECT id, snapshot_name, snapshot_desc, rule_count, created_at, created_by, effective_date, expired_date
            FROM rule_set_snapshot
            ORDER BY created_at DESC
        """
        rows = self.conn.execute(query).fetchall()
        return [dict(row) for row in rows]

    def get_changelog(self, rule_id: int = None, rule_code: str = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM rule_changelog WHERE 1=1"
        params = []

        if rule_id:
            query += " AND rule_id = ?"
            params.append(rule_id)
        elif rule_code:
            query += " AND rule_code = ?"
            params.append(rule_code)

        query += " ORDER BY changed_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_rule_version_hash(self) -> str:
        """返回规则表的变更标记，用于缓存失效检测"""
        row = self.conn.execute(
            "SELECT COUNT(*) || '-' || COALESCE(MAX(updated_at), 'never') FROM rule_items"
        ).fetchone()
        return str(row[0])