-- ============================================================================
-- 医保智能审核引擎 — 全量建表脚本 (SQLite)
-- 版本: 1.1.0
-- 日期: 2026-07-03
-- 对应文档: ARCHITECTURE.md
-- 更新说明: 合并耗材表(consumables+basic_material_catalog+special_material_attr→HC),
--           删除空表(diagnosis_procedure_map, consumable_procedure_pair, consumable_indications,
--                     consumable_qty_limits, drug_loaded_component, drg_reference, split_stay_tracking)
-- ============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- ============================================================================
-- 第一层: 知识目录层 (Knowledge Catalog Layer)
-- "只描述是什么" — 药品/项目/耗材/诊断/手术的客观属性
-- ============================================================================

-- 1.1 诊疗项目分类表 (project_category)
CREATE TABLE IF NOT EXISTS FW_category (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    parent_id       INTEGER REFERENCES project_category(id),
    level           INTEGER DEFAULT 1,         -- 1=一级类, 2=二级类
    display_order   INTEGER DEFAULT 0
);

-- 1.2 药品目录 (YP)
CREATE TABLE IF NOT EXISTS YPML (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name           TEXT NOT NULL UNIQUE,   -- 药品通用名（唯一键）
    dosage_form         TEXT,                   -- 剂型
    atc_code            TEXT,                   -- ATC 分类代码
    pharmacological_class TEXT,                 -- 药理分类
    payment_type        TEXT DEFAULT '乙类',    -- 甲/乙/丙类（药品分类属性，非规则）
    label_indications   TEXT,                   -- 说明书适应症（NMPA批准的客观事实）
    restriction_raw     TEXT,                   -- 原医保目录限制文本（归档备查）
    chs_code            TEXT,                   -- 国家医保药品编码（CHS 23位）
    evidence_source     TEXT,                   -- 数据来源
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- 1.3 诊疗项目目录 (FW)
-- 字段命名对齐国家医保局《医疗保障信息平台定点医药机构接口规范》V1.1.85
CREATE TABLE IF NOT EXISTS FWXM(
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    med_list_codg       TEXT NOT NULL UNIQUE,   -- 目录编码（15位立项指南编码）
    med_list_name       TEXT NOT NULL,           -- 目录名称
    med_list_type       TEXT DEFAULT '21',       -- 目录类型: 21=诊疗项目（基线版）
    category_id         INTEGER REFERENCES project_category(id),
    billing_unit        TEXT,                   -- 计价单位（次/日/部位等）
    service_output      TEXT,                   -- 服务产出（立项指南原文）
    pricing_composition TEXT,                   -- 价格构成（立项指南原文）
    chrgitm_lv          TEXT,                   -- 收费项目等级: 1=甲,2=乙,3=自费
    evidence_source     TEXT,                   -- 来源标记
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- 1.4 统一耗材目录 (HC)
-- 合并原 consumables + basic_material_catalog + special_material_attr 三张表
CREATE TABLE IF NOT EXISTS HCML (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hc_type       TEXT NOT NULL DEFAULT 'normal', -- basic=基本物耗, special=特殊功能, normal=普通耗材
    hc_list_name       TEXT NOT NULL,                  -- 耗材/物耗名称
    hc_list_codg       TEXT,                           -- 耗材编码
    ccode               TEXT,                           -- CUC编码（20位）
    category            TEXT,                           -- 分类
    payment_type        TEXT,                           -- 甲/乙类
    payment_ratio       REAL,                           -- 自付比例
    drug_loaded         INTEGER DEFAULT 0,              -- 是否载药
    drug_component      TEXT,                           -- 载药成分
    is_basic            INTEGER DEFAULT 0,              -- 1=基本物耗(不可单独收费)
    is_special_function INTEGER DEFAULT 0,              -- 1=特殊功能耗材
    is_clinically_necessary INTEGER DEFAULT 0,          -- 1=临床必须
    is_platform_listed  INTEGER DEFAULT 0,              -- 1=集采平台挂网
    price_reduction_rule TEXT,                          -- 排除时价格减收规则
    source_project_name TEXT,                           -- 关联的诊疗项目名称
    source_project_codg TEXT,                           -- 关联的诊疗项目编码
    match_keywords      TEXT,                           -- 匹配关键词
    evidence_source     TEXT,                           -- 政策出处
    evidence_summary    TEXT,                           -- 证据摘要
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- 1.5 疾病诊断实体 (icd_10)
CREATE TABLE IF NOT EXISTS icd_10 (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chs_code            TEXT NOT NULL UNIQUE,   -- ICD-10 医保版2.0编码
    name                TEXT NOT NULL,           -- 诊断名称（医保版2.0）
    is_gray_code        INTEGER DEFAULT 0,      -- 是否灰码（不可作主诊断）
    chapter             TEXT,                   -- 章节编码
    chapter_name        TEXT,                   -- 章节名称
    drg_group_type      TEXT,                   -- DRG分组类型: MDC/ADRG
    is_mcc              INTEGER DEFAULT 0,      -- 是否主要合并症/并发症
    is_cc               INTEGER DEFAULT 0,      -- 是否合并症/并发症
    guolin_code         TEXT,                   -- 国临版2.0编码
    guolin_name         TEXT,                   -- 国临版2.0名称
    need_review         TEXT,                   -- 是否需要论证
    review_reason       TEXT,                   -- 原因备注
    review_type         TEXT,                   -- 类型（编码一致名称不一致等）
    evidence_source     TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- 1.6 手术操作实体 (icd_9)
CREATE TABLE IF NOT EXISTS icd_9 (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chs_code            TEXT NOT NULL UNIQUE,   -- ICD-9-CM-3 医保版编码
    name                TEXT NOT NULL,           -- 手术/操作名称
    category            TEXT,                   -- 一级分类
    is_major            INTEGER DEFAULT 0,      -- 是否主要手术/操作
    drg_effect          TEXT,                   -- DRG修正效应: major/minor/none
    guolin_code         TEXT,                   -- 国临版3.0手术代码
    guolin_name         TEXT,                   -- 国临版3.0手术名称
    op_input_option     TEXT NOT NULL,           -- 手术操作录入选项（必选/选择性/中医必选，必填）
    op_level            TEXT,                   -- 手术级别（一/二/三/四级）
    incision_type       TEXT,                   -- 切口类别（0/I/II/III）
    evidence_source     TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);



-- ============================================================================
-- 第二层: 规则层 (Rule Layer)
-- "只描述怎么管" — 审核规则、约束条件、处置措施
-- ============================================================================

-- 2.1 核心规则表 (rule_items)
-- 四柱归属: drug / consumable / project / drg
-- 三阶段归属: pre_check / end_check / post_audit
CREATE TABLE IF NOT EXISTS rule_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_code           TEXT NOT NULL,           -- 规则编码
    rule_name           TEXT NOT NULL,           -- 规则名称
    rule_category       TEXT NOT NULL,           -- 规则大类
    rule_subcategory    TEXT,                   -- 规则子类
    pillar              TEXT NOT NULL,           -- YP / HC / FW / BZ
    stage               TEXT DEFAULT 'post_audit',  -- pre_check / mid_check / end_check / post_audit
    severity            TEXT DEFAULT 'suspicious',  -- violation / suspicious / info
    yp_id             INTEGER REFERENCES YPML(id),
    xm_a_id        INTEGER REFERENCES FWXM(id),
    xm_b_id        INTEGER REFERENCES FWXM(id),  -- 配对项目
    hc_id       INTEGER REFERENCES HCML(id),
    diagnosis_codes     TEXT,                   -- JSON数组，关联ICD-10编码
    procedure_codes     TEXT,                   -- JSON数组，关联ICD-9-CM-3编码
    conditions          TEXT NOT NULL,          -- JSON条件体（条件DSL）
    action              TEXT DEFAULT 'warn',    -- block / warn / tag / pass
    action_message      TEXT,                   -- 提示消息模板
    source_batch        TEXT,                   -- 两库来源批次
    source_reference    TEXT,                   -- 政策文件引用
    version             INTEGER DEFAULT 1,
    effective_date      TEXT,
    expired_date        TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now','localtime')),
    updated_at          TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(rule_code, version)
);

-- 2.2 DRG规则子表 (drg_rules)
CREATE TABLE IF NOT EXISTS drg_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name           TEXT NOT NULL,
    rule_type           TEXT NOT NULL,           -- GT/FJ/DB/SJ/ZSBP/PY
    conditions          TEXT,                   -- JSON条件体
    threshold_config    TEXT,                   -- JSON阈值配置
    pillar              TEXT DEFAULT 'BZ',
    stage               TEXT DEFAULT 'post_audit',
    severity            TEXT DEFAULT 'suspicious',
    is_active           INTEGER DEFAULT 1,      -- 是否启用
    evidence_source     TEXT,
    effective_date      TEXT,
    expired_date        TEXT,
    version             INTEGER DEFAULT 1,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================================
-- 第三层: 桥表层 (Bridge Layer)
-- 目录 ↔ 编码、目录 ↔ 别名、目录 ↔ 约束的关联关系
-- ============================================================================

-- 3.1 项目↔国家编码 (project_catalog_codes)
CREATE TABLE IF NOT EXISTS project_catalog_codes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    code_type           TEXT NOT NULL,           -- national / regional / internal
    code_value          TEXT NOT NULL,
    region_code         TEXT,                   -- 地区编码（地方编码时）
    is_primary          INTEGER DEFAULT 0,
    evidence_source     TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(project_id, code_type, code_value)
);

-- 3.2 项目↔别名 (project_catalog_aliases)
CREATE TABLE IF NOT EXISTS project_catalog_aliases (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    alias_name          TEXT NOT NULL,
    alias_source        TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_proj_alias ON project_catalog_aliases(alias_name);

-- 3.3 项目内涵 (project_connotation)
CREATE TABLE IF NOT EXISTS project_connotation (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES FW(id),
    included_project_id INTEGER REFERENCES FW(id),
    included_item_type  TEXT,                   -- project / consumable / service
    included_item_name  TEXT,
    description         TEXT,
    evidence_source     TEXT,
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================================
-- 第四层: DRG参考层 (DRG Reference Layer)
-- DRG分组的参考标准数据
-- ============================================================================

-- ============================================================================
-- 第五层: 审核输入层 (Claim Input Layer)
-- "被审核的对象" — 结算事件与费用明细
-- ============================================================================

-- 5.1 结算事件 (claim_event) — 对齐国家医保信息平台接口规范 V1.1.85
CREATE TABLE IF NOT EXISTS claim_event (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    setl_id             TEXT NOT NULL UNIQUE,
    mdtrt_id            TEXT,
    psn_no              TEXT,
    psn_name            TEXT,
    gend                TEXT,
    brdy                TEXT,
    insutype            TEXT,
    insu_region         TEXT,
    med_type            TEXT,
    adm_date            TEXT,
    dscg_date           TEXT,
    inhosp_days         INTEGER,
    hosp_lv             TEXT,
    dept                TEXT,
    adm_way             TEXT,
    dscg_way            TEXT,
    main_diag_code      TEXT,
    main_diag_name      TEXT,
    diag_codes          TEXT,
    main_oprn_code      TEXT,
    oprn_codes          TEXT,
    drg_codg            TEXT,
    drg_wt              REAL,
    drg_pay             REAL,
    medfee_sumamt       REAL,
    fund_pay_sumamt     REAL,
    acct_pay_sumamt     REAL,
    psn_part_amt        REAL,
    cash_payamt         REAL,
    data_source         TEXT,
    imported_at         TEXT DEFAULT (datetime('now','localtime'))
);

-- 5.2 费用明细 (claim_line) — 对齐国家医保信息平台接口规范 V1.1.85
CREATE TABLE IF NOT EXISTS claim_line (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    feedetl_sn          TEXT NOT NULL,
    setl_id             TEXT NOT NULL REFERENCES claim_event(setl_id),
    mdtrt_id            TEXT,
    fee_ocur_time       TEXT,
    line_no             INTEGER,              -- 引擎内部序号（辅助标识）
    list_type           TEXT NOT NULL,
    med_list_name       TEXT,
    med_list_codg       TEXT,
    medins_list_codg    TEXT,
    cnt                 REAL,
    pric                REAL,
    pric_ut             TEXT,
    det_amt             REAL,
    chrgitm_lv          TEXT,
    matched_catalog_id  INTEGER,
    match_confidence    REAL,
    match_method        TEXT,
    bilg_drord_no       TEXT,
    drord_type          TEXT,
    bilg_dept_codg      TEXT,
    bilg_dept_name      TEXT,
    bilg_dr_codg        TEXT,
    bilg_drord_dr_name  TEXT,
    acord_dept_codg     TEXT,
    acord_dept_name     TEXT,
    orders_dr_codg      TEXT,
    orders_dr_name      TEXT,
    exec_dept_codg      TEXT,                   -- 执行科室编码
    exec_dept_name      TEXT,                   -- 执行科室名称
    dosage_form         TEXT,
    tcmdrug_used_way    TEXT,
    oprn_code_used      TEXT,
    used_qty            REAL,
    hosp_appr_flag      TEXT,
    etip_flag           TEXT,
    dscg_tkdrug_flag    TEXT,
    matn_fee_flag       TEXT,
    clr_type            TEXT,
    fund_pay_type       TEXT,
    comb_no             TEXT,
    memo                TEXT,
    raw_data            TEXT,
    imported_at         TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_claim_line_setl ON claim_line(setl_id);
CREATE INDEX IF NOT EXISTS idx_claim_line_list_type ON claim_line(list_type);

-- ============================================================================
-- 第六层: 审核输出层 (Audit Output Layer)
-- 审核结果 + 变更日志
-- ============================================================================

-- 6.1 审核结果 (audit_result)
CREATE TABLE IF NOT EXISTS audit_result (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    setl_id             TEXT NOT NULL REFERENCES claim_event(setl_id),
    line_no             INTEGER,
    rule_id             INTEGER REFERENCES rule_items(id),
    rule_code           TEXT,
    rule_category       TEXT,
    pillar              TEXT,
    stage               TEXT,
    verdict             TEXT NOT NULL,           -- pass / warning / violation
    severity            TEXT,
    matched_facts       TEXT,                   -- JSON推理链
    rule_text           TEXT,
    reasoning           TEXT,
    action              TEXT,
    engine_version      TEXT,
    rule_version        INTEGER DEFAULT 1,
    audited_at          TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_audit_setl ON audit_result(setl_id);
CREATE INDEX IF NOT EXISTS idx_audit_verdict ON audit_result(verdict);
CREATE INDEX IF NOT EXISTS idx_audit_pillar ON audit_result(pillar);

-- 6.2 规则变更日志 (rule_changelog)
CREATE TABLE IF NOT EXISTS rule_changelog (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id             INTEGER NOT NULL REFERENCES rule_items(id),
    rule_code           TEXT,
    change_type         TEXT NOT NULL,           -- create / update / deactivate / delete / version_upgrade
    changed_fields      TEXT,                   -- JSON before/after
    changed_by          TEXT,
    changed_at          TEXT DEFAULT (datetime('now','localtime'))
);

-- 6.3 规则集快照 (rule_set_snapshot)
-- 用于规则版本管理：每次批量变更时打快照标记，支持回滚和时间旅行查询
CREATE TABLE IF NOT EXISTS rule_set_snapshot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_name       TEXT NOT NULL UNIQUE,    -- 快照名称，如 v2026Q3
    snapshot_desc       TEXT,                   -- 快照描述
    rule_count          INTEGER,                -- 快照时活跃规则数
    created_at          TEXT DEFAULT (datetime('now','localtime')),
    created_by          TEXT,
    effective_date      TEXT,                   -- 生效日期
    expired_date        TEXT                    -- 失效日期（空=当前活跃）
);
CREATE INDEX IF NOT EXISTS idx_snapshot_active ON rule_set_snapshot(expired_date);

-- ============================================================================
-- 七、人员资质表
-- ============================================================================

CREATE TABLE IF NOT EXISTS ryzz (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_codg      TEXT NOT NULL,       -- 人员编码
    staff_name      TEXT NOT NULL,       -- 人员姓名
    staff_type      TEXT NOT NULL,       -- 医师/药师/技师/护士
    dept_codg       TEXT,                -- 所属科室
    title           TEXT,                -- 职称（住院医师/主治医师/副主任医师/主任医师）
    qualification   TEXT NOT NULL,       -- 资质编码
    cert_level      TEXT,                -- 资质等级
    effective_date  TEXT,                -- 生效日期
    expired_date    TEXT,                -- 失效日期
    is_active       INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_staff_codg ON ryzz(staff_codg);
CREATE INDEX IF NOT EXISTS idx_staff_qual ON ryzz(staff_codg, qualification);

-- ============================================================================
-- 索引补充 (rule_items 查询加速)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_rule_pillar ON rule_items(pillar);
CREATE INDEX IF NOT EXISTS idx_rule_stage ON rule_items(stage);
CREATE INDEX IF NOT EXISTS idx_rule_severity ON rule_items(severity);
CREATE INDEX IF NOT EXISTS idx_rule_yp ON rule_items(yp_id);
CREATE INDEX IF NOT EXISTS idx_rule_xm ON rule_items(xm_a_id);
CREATE INDEX IF NOT EXISTS idx_rule_active ON rule_items(is_active);

-- ============================================================================
-- 触发器: rule_items 变更自动写入 changelog
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_rule_insert AFTER INSERT ON rule_items
BEGIN
    INSERT INTO rule_changelog (rule_id, rule_code, change_type, changed_fields, changed_by)
    VALUES (NEW.id, NEW.rule_code, 'create', 
        json_object(
            'rule_code', NEW.rule_code, 
            'rule_name', NEW.rule_name,
            'pillar', NEW.pillar, 
            'severity', NEW.severity,
            'stage', NEW.stage,
            'version', NEW.version,
            'effective_date', NEW.effective_date,
            'expired_date', NEW.expired_date
        ), 'system');
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_update AFTER UPDATE ON rule_items
BEGIN
    INSERT INTO rule_changelog (rule_id, rule_code, change_type, changed_fields, changed_by)
    VALUES (NEW.id, NEW.rule_code, 
        CASE WHEN OLD.version != NEW.version THEN 'version_upgrade' ELSE 'update' END,
        json_object(
            'rule_name', json_object('before', OLD.rule_name, 'after', NEW.rule_name),
            'pillar', json_object('before', OLD.pillar, 'after', NEW.pillar),
            'severity', json_object('before', OLD.severity, 'after', NEW.severity),
            'stage', json_object('before', OLD.stage, 'after', NEW.stage),
            'action', json_object('before', OLD.action, 'after', NEW.action),
            'conditions', json_object('before', OLD.conditions, 'after', NEW.conditions),
            'version', json_object('before', OLD.version, 'after', NEW.version),
            'effective_date', json_object('before', OLD.effective_date, 'after', NEW.effective_date),
            'expired_date', json_object('before', OLD.expired_date, 'after', NEW.expired_date),
            'is_active', json_object('before', OLD.is_active, 'after', NEW.is_active)
        ), 'system');
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_deactivate AFTER UPDATE OF is_active ON rule_items
WHEN NEW.is_active = 0 AND OLD.is_active = 1
BEGIN
    INSERT INTO rule_changelog (rule_id, rule_code, change_type, changed_fields, changed_by)
    VALUES (NEW.id, NEW.rule_code, 'deactivate', 
        json_object('rule_code', NEW.rule_code, 'reason', 'is_active set to 0', 'version', NEW.version), 'system');
END;
