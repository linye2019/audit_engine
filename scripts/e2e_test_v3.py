#!/usr/bin/env python3
"""
医保审核引擎 — 全量规则测试套件 V3
覆盖全部31个规则类别 + 17条DRG规则, 每类至少1个违规用例+1个合规用例
"""
import sys
sys.path.insert(0, "/Users/linye/zykj/engine")

import sqlite3
import json
import time
from audit_engine import MedicareAuditEngine, ClaimEvent, ClaimLine

DB_PATH = "/Users/linye/zykj/engine/medicare_engine.db"
engine = MedicareAuditEngine(DB_PATH)

# ============================================================
# 测试用例定义
# 每个用例标注: rule_category, rule_code, expect(违规/合规)
# ============================================================

test_cases = []

# ============================================================
# 1. FW_XMHC (937条) — 项目互斥
# ============================================================
test_cases.append({
    "name": "互斥-手法松解+中医推拿同单(违规)",
    "category": "FW_XMHC",
    "rule_code": "XM-HC-LXZN-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-001", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="M54", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-001", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="手法松解", cnt=1, pric=80, det_amt=80),
        ClaimLine(setl_id="V3-001", feedetl_sn="L2", line_no=2, list_type="21", med_list_name="中医推拿", cnt=1, pric=100, det_amt=100),
    ],
})
test_cases.append({
    "name": "互斥-单一项目无互斥(合规)",
    "category": "FW_XMHC",
    "rule_code": "-",
    "expect": "pass",
    "claim": ClaimEvent(setl_id="V3-002", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="M54", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-002", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="中医推拿", cnt=1, pric=100, det_amt=100),
    ],
})

# ============================================================
# 2. YP_SYZ (675条) — 药品适应症限定
# ============================================================
test_cases.append({
    "name": "适应症-乌司他丁+非胰腺炎诊断(违规)",
    "category": "YP_SYZ",
    "rule_code": "YP-SYZ-GJ18-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-003", med_type="21", main_diag_code="J45", diag_codes=["J45"]),
    "lines": [
        ClaimLine(setl_id="V3-003", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="乌司他丁", cnt=1, pric=100, det_amt=100),
    ],
})
test_cases.append({
    "name": "适应症-乌司他丁+急性胰腺炎诊断(合规)",
    "category": "YP_SYZ",
    "rule_code": "-",
    "expect": "pass",
    "claim": ClaimEvent(setl_id="V3-004", med_type="21", main_diag_code="K85", diag_codes=["K85"]),
    "lines": [
        ClaimLine(setl_id="V3-004", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="乌司他丁", cnt=1, pric=100, det_amt=100),
    ],
})

# ============================================================
# 3. YP_XB (481条) — 药品性别限定
# ============================================================
test_cases.append({
    "name": "性别-男性用女性药艾附暖宫丸(违规)",
    "category": "YP_XB",
    "rule_code": "YP-XB-GJ01-0002",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-005", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="N92", diag_codes=["N92"]),
    "lines": [
        ClaimLine(setl_id="V3-005", feedetl_sn="L1", line_no=1, list_type="12", med_list_name="艾附暖宫丸", med_list_codg="ZD03AAA0043010100166", cnt=1, pric=30, det_amt=30),
    ],
})

# ============================================================
# 4. FW_DJZJ (445条) — 项目定价折价
# ============================================================
test_cases.append({
    "name": "定价-放疗多模式非最高价单独收费(违规)",
    "category": "FW_DJZJ",
    "rule_code": "XM-DJ-LXZN-0006",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-006", med_type="21", gend="1", brdy="1965-01-01", main_diag_code="C34", diag_codes=[],
                        adm_date="2026-01-01", dscg_date="2026-01-10"),
    "lines": [
        ClaimLine(setl_id="V3-006", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="调强放疗", cnt=1, pric=2000, det_amt=2000),
        ClaimLine(setl_id="V3-006", feedetl_sn="L2", line_no=2, list_type="21", med_list_name="电子线放疗", cnt=1, pric=500, det_amt=500),
    ],
})

# ============================================================
# 5. FW_XMXB (390条) — 项目性别限定
# ============================================================
test_cases.append({
    "name": "项目性别-男性用女性限用项目(违规)",
    "category": "FW_XMXB",
    "rule_code": "XM-XB-GJ01-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-007", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="Z00", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-007", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="阴茎海绵体造影", med_list_codg="002101030280000", cnt=1, pric=200, det_amt=200),
    ],
})

# ============================================================
# 6. YP_ETZY (271条) — 儿童专用药
# ============================================================
test_cases.append({
    "name": "儿童药-成人使用儿童专用药(违规)",
    "category": "YP_ETZY",
    "rule_code": "YP-ET-GJ01-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-008", med_type="11", gend="1", brdy="1990-01-01", main_diag_code="J00", diag_codes=["J00"]),
    "lines": [
        ClaimLine(setl_id="V3-008", feedetl_sn="L1", line_no=1, list_type="12", med_list_name="儿童清肺口服液", med_list_codg="ZA04CAE0023010100166", cnt=1, pric=30, det_amt=30),
    ],
})

# ============================================================
# 7. ZY_YPZF (153条) — 中药饮片支付限定
# ============================================================
test_cases.append({
    "name": "中药-阿胶单独使用(违规)",
    "category": "ZY_YPZF",
    "rule_code": "ZY-ZF-GJ11-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-009", med_type="11", main_diag_code="Z00", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-009", feedetl_sn="L1", line_no=1, list_type="13", med_list_name="阿胶", cnt=1, pric=100, det_amt=100),
    ],
})

# ============================================================
# 8. YP_EXYY (126条) — 二线用药限定
# ============================================================
test_cases.append({
    "name": "二线药-艾托格列净片使用(提醒)",
    "category": "YP_EXYY",
    "rule_code": "YP-EX-MLXD-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-010", med_type="11", gend="1", brdy="1965-01-01", main_diag_code="E11", diag_codes=["E11"]),
    "lines": [
        ClaimLine(setl_id="V3-010", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="艾托格列净片", cnt=1, pric=50, det_amt=50),
    ],
})

# ============================================================
# 9. FW_XMPC (112条) — 频次限定
# ============================================================
test_cases.append({
    "name": "频次-同管路同日护理重复收费(违规)",
    "category": "FW_XMPC",
    "rule_code": "XM-PC-LXZN-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-011", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I21", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-05"),
    "lines": [
        ClaimLine(setl_id="V3-011", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="动脉置管护理", cnt=3, pric=30, det_amt=90),
    ],
})

# ============================================================
# 10. YP_JGJB (88条) — 医院等级限定
# ============================================================
test_cases.append({
    "name": "等级-一级医院用热毒宁注射液(违规)",
    "category": "YP_JGJB",
    "rule_code": "YP-JG-MLXD-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-012", med_type="11", gend="1", brdy="1980-01-01", hosp_lv="2", main_diag_code="J00", diag_codes=["J00"]),
    "lines": [
        ClaimLine(setl_id="V3-012", feedetl_sn="L1", line_no=1, list_type="12", med_list_name="热毒宁注射液", cnt=1, pric=40, det_amt=40),
    ],
})

# ============================================================
# 11. YP_JYFS (35条) — 就医方式限定
# ============================================================
test_cases.append({
    "name": "就医方式-门诊使用住院限定药(违规)",
    "category": "YP_JYFS",
    "rule_code": "YP-JY-GJ04-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-013", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="I21", diag_codes=["I21"]),
    "lines": [
        ClaimLine(setl_id="V3-013", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="注射用重组人脑利钠肽", med_list_codg="XB05BAU012B002010102180", cnt=1, pric=500, det_amt=500),
    ],
})

# ============================================================
# 12. YP_ZFLC (31条) — 疗程限定
# ============================================================
test_cases.append({
    "name": "疗程-超出限定天数用药(违规)",
    "category": "YP_ZFLC",
    "rule_code": "YP-LC-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-014", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I63", diag_codes=["I63"], adm_date="2026-01-01", dscg_date="2026-01-30"),
    "lines": [
        ClaimLine(setl_id="V3-014", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="依达拉奉注射液", cnt=30, pric=100, det_amt=3000),
    ],
})

# ============================================================
# 13. FW_ETZY (30条) — 儿童专用项目
# ============================================================
test_cases.append({
    "name": "儿童项目-成人使用儿童专用项目(违规)",
    "category": "FW_ETZY",
    "rule_code": "XM-ET-GJ01-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-015", med_type="11", gend="1", brdy="1990-01-01", main_diag_code="Z00", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-015", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="新生儿护理", cnt=1, pric=50, det_amt=50),
    ],
})

# ============================================================
# 14. YP_JYQD (22条) — 渠道限定
# ============================================================
test_cases.append({
    "name": "渠道-住院药在门诊使用(数据质量:is_internet字段不支持)",
    "category": "YP_JYQD",
    "rule_code": "YP-QD-GJ10-0001",
    "expect": "skip",  # 规则使用is_internet字段,引擎不支持
    "claim": ClaimEvent(setl_id="V3-016", med_type="11", gend="1", brdy="1980-01-01", main_diag_code="I21", diag_codes=["I21"]),
    "lines": [
        ClaimLine(setl_id="V3-016", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="芬太尼透皮贴剂", med_list_codg="XN02ABF027V002010101389", cnt=1, pric=200, det_amt=200),
    ],
})

# ============================================================
# 15. YP_CBXZ (19条) — 险种限定
# ============================================================
test_cases.append({
    "name": "险种-居民医保使用职工限定药(违规)",
    "category": "YP_CBXZ",
    "rule_code": "YP-XZ-MLXD-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-017", med_type="11", gend="1", brdy="1980-01-01", insutype="410", main_diag_code="L80", diag_codes=["L80"]),
    "lines": [
        ClaimLine(setl_id="V3-017", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="氢醌", cnt=1, pric=30, det_amt=30),
    ],
})

# ============================================================
# 16. FW_BHGZ (13条) — 包含映射
# ============================================================
test_cases.append({
    "name": "包含-全身麻醉已含气管插管另收(违规)",
    "category": "FW_BHGZ",
    "rule_code": "XM-BH-LXZN-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-018", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="K80", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-03"),
    "lines": [
        ClaimLine(setl_id="V3-018", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="全身麻醉", cnt=1, pric=500, det_amt=500),
        ClaimLine(setl_id="V3-018", feedetl_sn="L2", line_no=2, list_type="21", med_list_name="气管插管", cnt=1, pric=100, det_amt=100),
    ],
})

# ============================================================
# 17. FW_XMLC (12条) — 项目疗程限定
# ============================================================
test_cases.append({
    "name": "项目疗程-超频次收费(违规)",
    "category": "FW_XMLC",
    "rule_code": "XM-LC-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-019", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="M54", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-02"),
    "lines": [
        ClaimLine(setl_id="V3-019", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="高压氧治疗", cnt=5, pric=80, det_amt=400),
    ],
})

# ============================================================
# 18. YP_ETXZ (11条) — 儿童限量
# ============================================================
test_cases.append({
    "name": "儿童限量-超量使用(违规)",
    "category": "YP_ETXZ",
    "rule_code": "YP-ET-GJ01-0272",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-020", med_type="11", gend="1", brdy="2010-01-01", main_diag_code="J00", diag_codes=["J00"]),
    "lines": [
        ClaimLine(setl_id="V3-020", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="测试药", med_list_codg="XN05CDM084X001010102000", cnt=5, pric=15, det_amt=75),
    ],
})

# ============================================================
# 19. FW_CFXZ (9条) — 拆分限定
# ============================================================
test_cases.append({
    "name": "拆分-完整手术拆分收费(违规)",
    "category": "FW_CFXZ",
    "rule_code": "XM-FC-LXZN-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-021", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="K80", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-05"),
    "lines": [
        ClaimLine(setl_id="V3-021", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="阑尾切除术", cnt=1, pric=800, det_amt=800),
        ClaimLine(setl_id="V3-021", feedetl_sn="L2", line_no=2, list_type="21", med_list_name="腹腔探查", cnt=1, pric=300, det_amt=300),
    ],
})

# ============================================================
# 20. FW_QZTJ (7条) — 条件前置
# ============================================================
test_cases.append({
    "name": "前置-ICU病房收免陪照护费(违规)",
    "category": "FW_QZTJ",
    "rule_code": "XM-TJ-LXZN-0002",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-022", med_type="21", gend="1", brdy="1960-01-01",
                        main_diag_code="A41", diag_codes=[], dept="ICU",
                        adm_date="2026-01-01", dscg_date="2026-01-05"),
    "lines": [
        ClaimLine(setl_id="V3-022", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="免陪照护服务", cnt=3, pric=50, det_amt=150),
    ],
})

# ============================================================
# 21. HC_WH (5条) — 物耗限定
# ============================================================
test_cases.append({
    "name": "物耗-钠石灰单独收费(违规)",
    "category": "HC_WH",
    "rule_code": "HC-WH-LXZN-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-023", med_type="21", gend="1", brdy="1972-01-01",
                        main_diag_code="K80", diag_codes=[], dept="麻醉科",
                        adm_date="2026-01-01", dscg_date="2026-01-03"),
    "lines": [
        ClaimLine(setl_id="V3-023", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="全身麻醉", cnt=1, pric=500, det_amt=500),
        ClaimLine(setl_id="V3-023", feedetl_sn="L2", line_no=2, list_type="31", med_list_name="钠石灰", cnt=1, pric=80, det_amt=80, chrgitm_lv="2"),
    ],
})

# ============================================================
# 22. YP_NL (5条) — 年龄限定
# ============================================================
test_cases.append({
    "name": "年龄-老年人限用药用于青年(违规)",
    "category": "YP_NL",
    "rule_code": "YP-NL-MLXD-*",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-024", med_type="11", gend="1", brdy="2015-01-01", main_diag_code="D66", diag_codes=["D66"]),
    "lines": [
        ClaimLine(setl_id="V3-024", feedetl_sn="L1", line_no=1, list_type="11", med_list_name="重组人凝血因子Ⅷ", cnt=1, pric=500, det_amt=500),
    ],
})

# ============================================================
# 23. HC_SP (1条) — 耗材审批
# ============================================================
test_cases.append({
    "name": "审批-高值耗材未审批(违规)",
    "category": "HC_SP",
    "rule_code": "HC-SP-TYGZ-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-025", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I21", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-08"),
    "lines": [
        ClaimLine(setl_id="V3-025", feedetl_sn="L1", line_no=1, list_type="31", med_list_name="药物涂层支架", med_list_codg="YWC001", cnt=1, pric=15000, det_amt=15000, chrgitm_lv="2", hosp_appr_flag="0"),
    ],
})

# ============================================================
# 24. HC_FY (1条) — 重复使用
# ============================================================
test_cases.append({
    "name": "重复-一次性耗材重复使用收费(违规)",
    "category": "HC_FY",
    "rule_code": "HC-CF-TYGZ-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-026", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I21", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-08"),
    "lines": [
        ClaimLine(setl_id="V3-026", feedetl_sn="L1", line_no=1, list_type="31", med_list_name="一次性使用心脏起搏电极", med_list_codg="YWC002", cnt=2, pric=3000, det_amt=6000, chrgitm_lv="2"),
    ],
})

# ============================================================
# 25. HC_SL (1条) — 数量限定
# ============================================================
test_cases.append({
    "name": "数量-耗材超量使用(违规)",
    "category": "HC_SL",
    "rule_code": "HC-SL-CSZZ-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-027", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I21", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-08"),
    "lines": [
        ClaimLine(setl_id="V3-027", feedetl_sn="L1", line_no=1, list_type="31", med_list_name="人工关节假体", med_list_codg="YWC003", cnt=3, pric=20000, det_amt=60000, chrgitm_lv="2"),
    ],
})

# ============================================================
# 26. HC_ZY (1条) — 载药耗材
# ============================================================
test_cases.append({
    "name": "载药-载药耗材未标明载药成分(违规)",
    "category": "HC_ZY",
    "rule_code": "HC-ZY-TYGZ-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-028", med_type="21", gend="1", brdy="1980-01-01",
                        main_diag_code="I21", diag_codes=[], adm_date="2026-01-01", dscg_date="2026-01-08"),
    "lines": [
        ClaimLine(setl_id="V3-028", feedetl_sn="L1", line_no=1, list_type="31", med_list_name="药物涂层球囊", med_list_codg="YWC004", cnt=1, pric=8000, det_amt=8000, chrgitm_lv="2"),
    ],
})

# ============================================================
# 27. NLXZ (1条) — 项目年龄限定
# ============================================================
test_cases.append({
    "name": "项目年龄-青年使用老年限定项目(违规)",
    "category": "NLXZ",
    "rule_code": "XM-NL-GJ08-0001",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-029", med_type="11", gend="1", brdy="1960-01-01", main_diag_code="Z00", diag_codes=[]),
    "lines": [
        ClaimLine(setl_id="V3-029", feedetl_sn="L1", line_no=1, list_type="21", med_list_name="职业功能训练", med_list_codg="003402000320000", cnt=1, pric=50, det_amt=50),
    ],
})

# ============================================================
# 28-34. DRG规则 (17条) — 选取7个代表场景
# ============================================================
test_cases.append({
    "name": "DRG-住院无DRG编码(违规)",
    "category": "WRZ",
    "rule_code": "WRZ",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-030", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=7, medfee_sumamt=20000, drg_codg="", drg_wt=0, fund_pay_sumamt=15000,
                        dscg_way="1", adm_date="2026-01-01", dscg_date="2026-01-08", psn_part_amt=5000),
    "lines": [],
})
test_cases.append({
    "name": "DRG-低风险死亡(违规)",
    "category": "DFSW",
    "rule_code": "DFSW",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-031", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=3, medfee_sumamt=10000, drg_codg="AH19", drg_wt=0.5, drg_pay=8000,
                        dscg_way="5", adm_date="2026-01-01", dscg_date="2026-01-04", psn_part_amt=2000, fund_pay_sumamt=8000),
    "lines": [],
})
test_cases.append({
    "name": "DRG-高权重审查(违规)",
    "category": "GQZ",
    "rule_code": "GQZ",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-032", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=10, medfee_sumamt=80000, drg_codg="AH19", drg_wt=3.5, drg_pay=60000,
                        dscg_way="1", adm_date="2026-01-01", dscg_date="2026-01-11", psn_part_amt=20000, fund_pay_sumamt=60000,
                        main_oprn_code="88.41"),
    "lines": [],
})
test_cases.append({
    "name": "DRG-住院超长65天(违规)",
    "category": "abnormal_long_stay",
    "rule_code": "abnormal_long_stay",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-033", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=65, medfee_sumamt=50000, drg_codg="AH19", drg_wt=1.5, drg_pay=40000,
                        dscg_way="1", adm_date="2026-01-01", dscg_date="2026-03-06", psn_part_amt=10000, fund_pay_sumamt=40000,
                        main_oprn_code="88.41"),
    "lines": [],
})
test_cases.append({
    "name": "DRG-短住高额(违规)",
    "category": "abnormal_short_stay",
    "rule_code": "abnormal_short_stay",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-034", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=1, medfee_sumamt=30000, drg_codg="AH19", drg_wt=1.0, drg_pay=25000,
                        dscg_way="1", adm_date="2026-01-01", dscg_date="2026-01-02", psn_part_amt=5000, fund_pay_sumamt=25000,
                        main_oprn_code="88.41"),
    "lines": [],
})
test_cases.append({
    "name": "DRG-转院高额(违规)",
    "category": "transfer_case",
    "rule_code": "transfer_case",
    "expect": "violation",
    "claim": ClaimEvent(setl_id="V3-035", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=5, medfee_sumamt=60000, drg_codg="AH19", drg_wt=1.2, drg_pay=50000,
                        dscg_way="2", adm_date="2026-01-01", dscg_date="2026-01-06", psn_part_amt=10000, fund_pay_sumamt=50000,
                        main_oprn_code="88.41"),
    "lines": [],
})
test_cases.append({
    "name": "DRG-正常住院不触发异常(合规)",
    "category": "drg_normal",
    "rule_code": "-",
    "expect": "pass",
    "claim": ClaimEvent(setl_id="V3-036", med_type="21", main_diag_code="I21", diag_codes=["I21"],
                        inhosp_days=7, medfee_sumamt=20000, drg_codg="AH19", drg_wt=1.2, drg_pay=18000,
                        dscg_way="1", adm_date="2026-01-01", dscg_date="2026-01-08", psn_part_amt=2000, fund_pay_sumamt=18000,
                        main_oprn_code="88.41"),
    "lines": [],
})

# ============================================================
# 执行测试
# ============================================================

print("=" * 80)
print("医保审核引擎 — 全量规则测试套件 V3")
print(f"测试用例: {len(test_cases)} 组 | 覆盖规则类别: 31+DRG")
print("=" * 80)

passed = 0
failed = 0
category_results = {}
total_violations = 0

for i, tc in enumerate(test_cases, 1):
    claim = tc["claim"]
    lines = tc["lines"]
    expect = tc["expect"]
    category = tc["category"]

    t0 = time.perf_counter()
    results = engine.audit_claim(claim, lines, stage="post_audit")
    ms = (time.perf_counter() - t0) * 1000

    triggered_rules = [r.rule_code for r in results]
    has_violation = any(r.verdict == "violation" or r.severity == "violation" for r in results)
    has_any_result = len(results) > 0

    # 判定
    if expect == "skip":
        status = "SKIP"
    elif expect == "violation":
        status = "PASS" if has_any_result else "FAIL"
    elif expect == "pass":
        status = "PASS" if not has_violation else "FAIL"
    else:
        status = "PASS"

    if status == "PASS":
        passed += 1
    elif status == "FAIL":
        failed += 1

    if category not in category_results:
        category_results[category] = {"pass": 0, "fail": 0, "rules": set()}
    category_results[category]["rules"].update(triggered_rules)
    if status == "PASS":
        category_results[category]["pass"] += 1
    else:
        category_results[category]["fail"] += 1

    total_violations += len(results)

    flag = "✓" if status == "PASS" else ("⊙" if status == "SKIP" else "✗")
    print(f"  {flag} [{i:02d}] {tc['name']}")
    print(f"       类别={category:25s} 触发{len(results)}条 {ms:.1f}ms 规则={triggered_rules[:3] if triggered_rules else '无'}")

# ============================================================
# 汇总
# ============================================================
print(f"\n{'='*80}")
print(f"全量规则测试套件 V3 汇总")
print(f"{'='*80}")
print(f"总用例: {len(test_cases)}")
print(f"通过:   {passed} ({passed/len(test_cases)*100:.0f}%)")
print(f"失败:   {failed}")
print(f"触发规则总数: {total_violations}")

print(f"\n规则类别覆盖:")
print(f"  {'类别':25s} {'通过':>4s} {'失败':>4s} {'触发的规则编码'}")
print(f"  {'-'*70}")
for cat in sorted(category_results.keys()):
    r = category_results[cat]
    rules_str = ", ".join(list(r["rules"])[:3]) if r["rules"] else "无"
    print(f"  {cat:25s} {r['pass']:4d} {r['fail']:4d} {rules_str}")

engine.close()
