from dataclasses import dataclass, field
from typing import dict


@dataclass
class EngineConfig:
    db_path: str = "medicare_engine.db"
    log_level: str = "INFO"
    cache_enabled: bool = True
    field_aliases: dict = field(default_factory=lambda: {
        "patient_gender": "gend",
        "patient_age": "age",
        "hospital_level": "hosp_lv",
        "insurance_type": "insutype",
        "diagnosis_codes": "diag_codes",
        "med_list_code": "med_list_codg",
        "project_code": "med_list_codg",
        "visit_type": "med_type",
        "prescription_type": "med_type",
    })