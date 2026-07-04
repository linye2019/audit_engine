import json
import sqlite3
from typing import Any, Optional
from ..models.claim import ClaimEvent, ClaimLine


class ContextBuilder:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def build_line_context(self, claim: ClaimEvent, line: ClaimLine,
                           all_lines: list[ClaimLine] = None) -> dict:
        all_diagnoses = [claim.main_diag_code] + claim.diag_codes
        co_claimed_names = []
        co_claimed_lines = []
        if all_lines:
            for ln in all_lines:
                is_same_line = (ln.feedetl_sn == line.feedetl_sn) if ln.feedetl_sn else (ln.line_no == line.line_no)
                if not is_same_line and ln.med_list_name:
                    co_claimed_names.append(ln.med_list_name)
                    co_claimed_lines.append({
                        "med_list_name": ln.med_list_name,
                        "med_list_codg": ln.med_list_codg,
                        "cnt": ln.cnt,
                        "pric": ln.pric,
                        "list_type": ln.list_type,
                    })

        daily_quantity = line.cnt or 0
        usage_days = 1
        if claim.adm_date and claim.dscg_date:
            try:
                from datetime import datetime
                adm = datetime.strptime(str(claim.adm_date)[:10], "%Y-%m-%d")
                dscg = datetime.strptime(str(claim.dscg_date)[:10], "%Y-%m-%d")
                usage_days = max(1, (dscg - adm).days)
            except (ValueError, TypeError):
                pass

        period_quantity = 0
        if all_lines:
            for ln in all_lines:
                if ln.med_list_codg == line.med_list_codg and ln.cnt:
                    period_quantity += ln.cnt

        is_internet = "互联网" in str(claim.hosp_lv or "") or "互联网" in str(claim.med_type or "")

        same_incision_group_count = 0
        if all_lines:
            for ln in all_lines:
                if ln.oprn_code_used and ln.oprn_code_used != line.oprn_code_used:
                    same_incision_group_count += 1

        is_discounted = False
        if line.pric and line.cnt and line.det_amt is not None:
            try:
                is_discounted = float(line.det_amt) < float(line.pric) * float(line.cnt)
            except (ValueError, TypeError):
                pass

        duration_hours = 0
        if claim.adm_date and claim.dscg_date:
            try:
                from datetime import datetime
                adm = datetime.strptime(str(claim.adm_date)[:10], "%Y-%m-%d")
                dscg = datetime.strptime(str(claim.dscg_date)[:10], "%Y-%m-%d")
                duration_hours = max(0, (dscg - adm).total_seconds() / 3600)
            except (ValueError, TypeError):
                pass

        ward_type = ""
        dept_lower = str(claim.dept or "")
        ward_mapping = {
            "ICU": "危重症", "重症": "危重症", "危重": "危重症",
            "新生儿": "新生儿", "早产": "新生儿",
            "精神": "精神病",
            "干细胞": "干细胞", "移植": "器官移植",
        }
        for keyword, wtype in ward_mapping.items():
            if keyword in dept_lower:
                ward_type = wtype
                break

        same_surcharge_category_count = 0
        if line.med_list_codg and len(line.med_list_codg) >= 15:
            current_cat = line.med_list_codg[-2]
            if all_lines:
                for ln in all_lines:
                    if (ln.med_list_codg and len(ln.med_list_codg) >= 15
                            and ln.med_list_codg[-2] == current_cat
                            and ln.feedetl_sn != line.feedetl_sn):
                        same_surcharge_category_count += 1

        has_multiple_surcharges = False
        if all_lines:
            surcharge_count = sum(
                1 for ln in all_lines
                if ln.med_list_codg and len(ln.med_list_codg) >= 15
                and ln.med_list_codg[-2] in ('1', '2', '3', '4', '5', '6', '7', '8', '9')
            )
            has_multiple_surcharges = surcharge_count > 1

        calculation_method = "unknown"

        same_session_modes_count = 0
        if all_lines:
            same_session_modes_count = sum(
                1 for ln in all_lines
                if ln.med_list_name and "放疗" in str(ln.med_list_name)
            )

        is_highest_price = True
        if all_lines and line.pric:
            for ln in all_lines:
                if ln.pric and float(ln.pric) > float(line.pric):
                    is_highest_price = False
                    break

        same_body_site = None
        is_charged_separately = True

        price_margin = 0
        if line.pric and line.cnt and line.det_amt is not None:
            try:
                price_margin = float(line.det_amt) - float(line.pric) * float(line.cnt)
            except (ValueError, TypeError):
                pass

        is_basic_material = False
        is_special_function = False
        is_clinically_necessary = False
        is_procurement_platform_listed = False

        if line.list_type == "31" and line.med_list_name:
            try:
                bm_rows = self.conn.execute(
                    "SELECT match_keywords, hc_list_name FROM HCML WHERE is_basic = 1 AND match_keywords != ''"
                ).fetchall()
                for bm_row in bm_rows:
                    keywords = bm_row[0].split(",")
                    if any(kw.strip() in line.med_list_name for kw in keywords if kw.strip()):
                        is_basic_material = True
                        break
            except sqlite3.OperationalError:
                pass

            try:
                sm_row = None
                if line.med_list_codg:
                    sm_row = self.conn.execute(
                        "SELECT is_special_function, is_clinically_necessary, is_platform_listed, match_keywords "
                        "FROM HCML WHERE hc_list_codg = ?",
                        (line.med_list_codg,)
                    ).fetchone()
                if not sm_row:
                    sm_rows = self.conn.execute(
                        "SELECT is_special_function, is_clinically_necessary, is_platform_listed, match_keywords "
                        "FROM HCML WHERE is_special_function = 1"
                    ).fetchall()
                    for sr in sm_rows:
                        kws = sr[3].split(",") if sr[3] else []
                        if any(kw.strip() in line.med_list_name for kw in kws if kw.strip()):
                            sm_row = sr
                            break
                if sm_row:
                    is_special_function = bool(sm_row[0])
                    is_clinically_necessary = bool(sm_row[1])
                    is_procurement_platform_listed = bool(sm_row[2])
            except sqlite3.OperationalError:
                pass

        scan_type = None
        has_informed_consent = None

        return {
            "claim_event": {
                "setl_id": claim.setl_id,
                "mdtrt_id": claim.mdtrt_id,
                "gend": claim.gend,
                "age": claim.age,
                "med_type": claim.med_type,
                "hosp_lv": claim.hosp_lv,
                "dept": claim.dept,
                "main_diag_code": claim.main_diag_code,
                "main_diag_name": claim.main_diag_name,
                "diag_codes": claim.diag_codes,
                "all_diagnoses": all_diagnoses,
                "main_oprn_code": claim.main_oprn_code,
                "insutype": claim.insutype,
                "adm_date": claim.adm_date,
                "dscg_date": claim.dscg_date,
                "los": claim.los,
                "age": claim.age,
                "co_claimed_names": co_claimed_names,
                "claim_lines": co_claimed_lines,
                "is_internet": is_internet,
                "same_incision_group_count": same_incision_group_count,
                "ward_type": ward_type,
                "same_surcharge_category_count": same_surcharge_category_count,
                "same_session_modes_count": same_session_modes_count,
                "same_body_site": same_body_site,
            },
            "claim_line": {
                "feedetl_sn": line.feedetl_sn,
                "mdtrt_id": line.mdtrt_id,
                "fee_ocur_time": line.fee_ocur_time,
                "list_type": line.list_type,
                "med_list_name": line.med_list_name,
                "med_list_codg": line.med_list_codg,
                "medins_list_codg": line.medins_list_codg,
                "cnt": line.cnt,
                "pric": line.pric,
                "det_amt": line.det_amt,
                "bilg_dept_codg": line.bilg_dept_codg,
                "bilg_dr_codg": line.bilg_dr_codg,
                "acord_dept_codg": line.acord_dept_codg,
                "orders_dr_codg": line.orders_dr_codg,
                "exec_dept_codg": line.exec_dept_codg,
                "exec_dept_name": line.exec_dept_name,
                "oprn_code_used": line.oprn_code_used,
                "used_qty": line.used_qty,
                "hosp_appr_flag": line.hosp_appr_flag,
                "chrgitm_lv": line.chrgitm_lv,
                "etip_flag": line.etip_flag,
                "dscg_tkdrug_flag": line.dscg_tkdrug_flag,
                "matn_fee_flag": line.matn_fee_flag,
                "clr_type": line.clr_type,
                "comb_no": line.comb_no,
                "daily_quantity": daily_quantity,
                "usage_days": usage_days,
                "period_quantity": period_quantity,
                "is_discounted": is_discounted,
                "duration_hours": duration_hours,
                "has_multiple_surcharges": has_multiple_surcharges,
                "calculation_method": calculation_method,
                "is_highest_price": is_highest_price,
                "is_charged_separately": is_charged_separately,
                "price_margin": price_margin,
                "is_basic_material": is_basic_material,
                "is_special_function": is_special_function,
                "is_clinically_necessary": is_clinically_necessary,
                "is_procurement_platform_listed": is_procurement_platform_listed,
                "scan_type": scan_type,
                "has_informed_consent": has_informed_consent,
            },
            "staff": self._build_staff_context(line),
        }

    def _build_staff_context(self, line: ClaimLine) -> dict:
        """构建人员资质上下文"""
        staff = {}
        for role, codg in [("bilg_dr", line.bilg_dr_codg),
                           ("orders_dr", line.orders_dr_codg)]:
            if not codg:
                staff[role] = {"staff_codg": "", "title": "", "qualifications": []}
                continue
            try:
                rows = self.conn.execute(
                    "SELECT staff_name, title, qualification, cert_level FROM ryzz WHERE staff_codg = ? AND is_active = 1",
                    (codg,)
                ).fetchall()
                quals = [dict(r) for r in rows]
                staff[role] = {
                    "staff_codg": codg,
                    "staff_name": quals[0]["staff_name"] if quals else "",
                    "title": quals[0]["title"] if quals else "",
                    "qualifications": [q["qualification"] for q in quals],
                    "cert_levels": [q["cert_level"] for q in quals if q["cert_level"]],
                }
            except Exception:
                staff[role] = {"staff_codg": codg, "title": "", "qualifications": []}
        return staff

    def _build_staff_context_from_event(self, claim) -> dict:
        return {}

    def build_event_context(self, claim: ClaimEvent) -> dict:
        return {
            "claim_event": {
                "setl_id": claim.setl_id,
                "mdtrt_id": claim.mdtrt_id,
                "psn_no": claim.psn_no,
                "med_type": claim.med_type,
                "gend": claim.gend,
                "age": claim.age,
                "main_diag_code": claim.main_diag_code,
                "main_oprn_code": claim.main_oprn_code,
                "los": claim.los,
                "inhosp_days": claim.inhosp_days,
                "medfee_sumamt": claim.medfee_sumamt,
                "fund_pay_sumamt": claim.fund_pay_sumamt,
                "psn_part_amt": claim.psn_part_amt,
                "drg_codg": claim.drg_codg,
                "drg_wt": claim.drg_wt,
                "drg_pay": claim.drg_pay,
                "diag_codes": claim.diag_codes,
                "oprn_codes": claim.oprn_codes,
                "adm_date": claim.adm_date,
                "dscg_date": claim.dscg_date,
                "dscg_way": claim.dscg_way,
                "hosp_lv": claim.hosp_lv,
                "dept": claim.dept,
            },
        }
        ctx["staff"] = self._build_staff_context_from_event(claim)
        return ctx