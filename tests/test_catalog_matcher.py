import pytest
from audit_engine.matcher.catalog import CatalogMatcher
from audit_engine.models.claim import ClaimLine


class TestCatalogMatcher:
    @pytest.fixture
    def matcher(self):
        m = CatalogMatcher(None)  # conn=None，不走 DB
        m.load_from_data(
            drug_by_code={"XL01EMA057": 1, "ZC001": 20, "ZY001": 30},
            drug_by_name={"阿莫西林": 1, "板蓝根颗粒": 20, "人参": 30},
            drug_names_clean=[("阿莫西林", 1, "阿莫西林"), ("板蓝根颗粒", 20, "板蓝根颗粒"), ("人参", 30, "人参")],
            project_by_code={"PRJ001": 10},
            project_by_name={"推拿治疗": 10},
            project_names_clean=[("推拿治疗", 10, "推拿治疗"), ("针灸治疗", 11, "针灸治疗")],
            material_by_ccode={"CUC001": 5},
            material_by_code={"MAT001": 5},
            material_by_name={"一次性输液器": 5},
            alias_by_name={"CT": 10},
        )
        return m

    def _create_line(self, list_type, med_list_codg="", med_list_name=""):
        return ClaimLine(
            setl_id="TEST001",
            feedetl_sn="L001",
            list_type=list_type,
            med_list_codg=med_list_codg,
            med_list_name=med_list_name
        )

    def test_match_drug_by_code(self, matcher):
        line = self._create_line("11", "XL01EMA057", "阿莫西林")
        result = matcher.match(line)

        assert result is not None
        assert result["id"] == 1
        assert result["method"] == "code"
        assert result["confidence"] == 1.0
        assert result["table"] == "YP"

    def test_match_project_by_code(self, matcher):
        line = self._create_line("21", "PRJ001", "推拿治疗")
        result = matcher.match(line)

        assert result is not None
        assert result["id"] == 10
        assert result["table"] == "FW"

    def test_match_consumable_by_code(self, matcher):
        line = self._create_line("31", "CUC001", "一次性输液器")
        result = matcher.match(line)

        assert result is not None
        assert result["id"] == 5
        assert result["table"] == "HC"

    def test_match_by_code_not_found_then_fuzzy(self, matcher):
        # UNKNOWN 编码不存在 → 降级到模糊匹配
        # 再注入一个模糊匹配能命中的药品名
        matcher.load_from_data(
            drug_names_clean=[("阿莫西林胶囊", 1, "阿莫西林胶囊"), ("头孢拉定", 2, "头孢拉定")],
        )
        line = self._create_line("11", "UNKNOWN", "阿莫西林胶囊")

        result = matcher.match(line)

        assert result is not None
        assert result["id"] == 1
        assert result["method"] == "fuzzy"
        assert result["confidence"] == 0.7

    def test_match_by_name_exact(self):
        matcher = CatalogMatcher(None)
        matcher.load_from_data(
            drug_by_name={"阿莫西林": 1},
        )
        line = self._create_line("11", "", "阿莫西林")

        result = matcher.match(line)

        assert result is not None
        assert result["method"] == "exact"
        assert result["confidence"] == 1.0

    def test_match_by_alias(self):
        matcher = CatalogMatcher(None)
        matcher.load_from_data(
            alias_by_name={"CT": 10},
        )
        line = self._create_line("21", "", "CT")

        result = matcher.match(line)

        assert result is not None
        assert result["method"] == "alias"
        assert result["confidence"] == 0.95

    def test_match_fuzzy_project(self, matcher):
        line = self._create_line("21", "", "推拿")

        result = matcher.match(line)

        assert result is not None
        assert result["id"] == 10
        assert result["method"] == "fuzzy"

    def test_match_no_result(self, matcher):
        line = self._create_line("11", "", "未知药品")

        result = matcher.match(line)

        assert result is None

    def test_match_caching(self, matcher):
        line = self._create_line("11", "XL01EMA057", "阿莫西林")

        result1 = matcher.match(line)
        result2 = matcher.match(line)

        assert result1["id"] == result2["id"]

    def test_match_short_name_skip_fuzzy(self, matcher):
        line = self._create_line("11", "", "A")

        result = matcher.match(line)

        assert result is None

    def test_match_unknown_list_type(self, matcher):
        line = self._create_line("99", "CODE", "名称")
        result = matcher.match(line)
        assert result is None

    def test_match_empty_name_empty_code(self, matcher):
        line = self._create_line("11", "", "")
        result = matcher.match(line)
        assert result is None

    def test_match_tcm_drug_by_code(self, matcher):
        line = self._create_line("12", "ZC001", "板蓝根颗粒")
        result = matcher.match(line)

        assert result is not None
        assert result["table"] == "YP"

    def test_match_herb_drug_by_code(self, matcher):
        line = self._create_line("13", "ZY001", "人参")
        result = matcher.match(line)

        assert result is not None
        assert result["table"] == "YP"
