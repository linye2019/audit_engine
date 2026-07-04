import re
import sqlite3
from typing import Optional
from ..models.claim import ClaimLine


class CatalogMatcher:
    """
    将 claim_line 中的 item_name/item_code 匹配到三目录之一。
    匹配策略优先级: 精确匹配 > 编码匹配 > 别名匹配 > 模糊匹配

    优化: 启动时全量加载目录到内存，后续匹配零 DB 查询。
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._loaded = False
        self._match_cache: dict[str, Optional[dict]] = {}

        # 内存索引 — 药品 (YP)
        self._drug_by_code: dict[str, int] = {}
        self._drug_by_name: dict[str, int] = {}
        self._drug_names: list[str] = []
        self._drug_names_clean: list[tuple[str, int, str]] = []  # (cleaned_name, id, original_name)

        # 内存索引 — 项目 (FW)
        self._project_by_code: dict[str, int] = {}
        self._project_by_name: dict[str, int] = {}
        self._project_names_clean: list[tuple[str, int, str]] = []

        # 内存索引 — 耗材 (HC)
        self._material_by_code: dict[str, int] = {}
        self._material_by_ccode: dict[str, int] = {}
        self._material_by_name: dict[str, int] = {}

        # 别名索引 — project_catalog_aliases
        self._alias_by_name: dict[str, int] = {}

    def _ensure_loaded(self):
        """一次性全量加载三目录到内存"""
        if self._loaded:
            return

        # 自适应检测 FW 的列名（测试库用 med_list_name，生产库用 name）
        proj_cols = [c[1] for c in self.conn.execute("PRAGMA table_info(FWXM)").fetchall()]
        proj_name_col = "med_list_name" if "med_list_name" in proj_cols else "name"

        # 药品目录
        rows = self.conn.execute(
            "SELECT id, drug_name, chs_code FROM YPML"
        ).fetchall()
        for row in rows:
            if row["chs_code"]:
                self._drug_by_code[row["chs_code"]] = row["id"]
            name = row["drug_name"]
            if name:
                self._drug_by_name[name] = row["id"]
                self._drug_names.append(name)
                clean = re.sub(r"[\s\-_（）()（）]", "", name)
                self._drug_names_clean.append((clean, row["id"], name))

        # 项目目录
        rows = self.conn.execute(
            f"SELECT id, \"{proj_name_col}\", med_list_codg FROM FWXM"
        ).fetchall()
        for row in rows:
            if row["med_list_codg"]:
                self._project_by_code[row["med_list_codg"]] = row["id"]
            name = row[proj_name_col]
            if name:
                self._project_by_name[name] = row["id"]
                clean = re.sub(r"[\s\-_（）()（）]", "", name)
                self._project_names_clean.append((clean, row["id"], name))

        # 耗材目录
        rows = self.conn.execute(
            "SELECT id, hc_list_name, hc_list_codg, ccode FROM HCML"
        ).fetchall()
        for row in rows:
            if row["med_list_codg"]:
                self._material_by_code[row["med_list_codg"]] = row["id"]
            if row["ccode"]:
                self._material_by_ccode[row["ccode"]] = row["id"]
            if row["med_list_name"]:
                self._material_by_name[row["med_list_name"]] = row["id"]

        # 别名
        rows = self.conn.execute(
            "SELECT project_id, alias_name FROM project_catalog_aliases"
        ).fetchall()
        for row in rows:
            self._alias_by_name[row["alias_name"]] = row["project_id"]

        self._loaded = True
        # 全量加载完成后可关闭连接引用（不再需要 DB 查询）

    def load_from_data(self, *,
                       drug_by_code: dict[str, int] = None,
                       drug_by_name: dict[str, int] = None,
                       drug_names_clean: list = None,
                       project_by_code: dict[str, int] = None,
                       project_by_name: dict[str, int] = None,
                       project_names_clean: list = None,
                       material_by_code: dict[str, int] = None,
                       material_by_ccode: dict[str, int] = None,
                       material_by_name: dict[str, int] = None,
                       alias_by_name: dict[str, int] = None):
        """从预构建的数据加载（主要用于测试，跳过 DB 查询）"""
        if drug_by_code is not None:
            self._drug_by_code = drug_by_code
        if drug_by_name is not None:
            self._drug_by_name = drug_by_name
        if drug_names_clean is not None:
            self._drug_names_clean = drug_names_clean
        if project_by_code is not None:
            self._project_by_code = project_by_code
        if project_by_name is not None:
            self._project_by_name = project_by_name
        if project_names_clean is not None:
            self._project_names_clean = project_names_clean
        if material_by_code is not None:
            self._material_by_code = material_by_code
        if material_by_ccode is not None:
            self._material_by_ccode = material_by_ccode
        if material_by_name is not None:
            self._material_by_name = material_by_name
        if alias_by_name is not None:
            self._alias_by_name = alias_by_name
        self._loaded = True

    def match(self, line: ClaimLine) -> Optional[dict]:
        self._ensure_loaded()

        cache_key = f"{line.list_type}_{line.med_list_codg}_{line.med_list_name}"
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        # 优先级1: 编码匹配
        if line.med_list_codg:
            result = self._match_by_code(line)
            if result:
                self._match_cache[cache_key] = result
                return result

        # 优先级2: 名称精确匹配
        result = self._match_by_name_exact(line)
        if result:
            return result

        # 优先级3: 别名匹配（仅项目）
        result = self._match_by_alias(line)
        if result:
            return result

        # 优先级4: 名称模糊匹配
        result = self._match_by_name_fuzzy(line)
        if result:
            self._match_cache[cache_key] = result
            return result

        self._match_cache[cache_key] = None
        return None

    def _match_by_code(self, line: ClaimLine) -> Optional[dict]:
        code = line.med_list_codg.strip() if line.med_list_codg else ""
        if not code:
            return None

        if line.list_type in ("11", "12", "13"):
            id_ = self._drug_by_code.get(code)
            if id_ is not None:
                return {"table": "YP", "id": id_, "confidence": 1.0, "method": "code"}
        elif line.list_type == "31":
            id_ = self._material_by_ccode.get(code) or self._material_by_code.get(code)
            if id_ is not None:
                return {"table": "HC", "id": id_, "confidence": 1.0, "method": "code"}
        elif line.list_type == "21":
            id_ = self._project_by_code.get(code)
            if id_ is not None:
                return {"table": "FW", "id": id_, "confidence": 1.0, "method": "code"}
        return None

    def _match_by_name_exact(self, line: ClaimLine) -> Optional[dict]:
        name = line.med_list_name.strip() if line.med_list_name else ""
        if not name:
            return None

        if line.list_type in ("11", "12", "13"):
            id_ = self._drug_by_name.get(name)
            if id_ is not None:
                return {"table": "YP", "id": id_, "confidence": 1.0, "method": "exact"}
        elif line.list_type == "31":
            id_ = self._material_by_name.get(name)
            if id_ is not None:
                return {"table": "HC", "id": id_, "confidence": 1.0, "method": "exact"}
        elif line.list_type == "21":
            id_ = self._project_by_name.get(name)
            if id_ is not None:
                return {"table": "FW", "id": id_, "confidence": 1.0, "method": "exact"}
        return None

    def _match_by_alias(self, line: ClaimLine) -> Optional[dict]:
        name = line.med_list_name.strip() if line.med_list_name else ""
        if not name or line.list_type not in ("21",):
            return None
        id_ = self._alias_by_name.get(name)
        if id_ is not None:
            return {"table": "FW", "id": id_, "confidence": 0.95, "method": "alias"}
        return None

    def _match_by_name_fuzzy(self, line: ClaimLine) -> Optional[dict]:
        name = re.sub(r"[\s\-_（）()（）]", "", line.med_list_name or "")
        if not name or len(name) < 2:
            return None

        if line.list_type in ("11", "12", "13"):
            for clean, id_, original in self._drug_names_clean:
                if clean == name or (len(clean) > 2 and (name in clean or clean in name)):
                    return {"table": "YP", "id": id_, "confidence": 0.7, "method": "fuzzy"}
        elif line.list_type == "21":
            for clean, id_, original in self._project_names_clean:
                if clean == name or (len(clean) > 2 and (name in clean or clean in name)):
                    return {"table": "FW", "id": id_, "confidence": 0.7, "method": "fuzzy"}
        # 耗材模糊匹配：由于 HC 条数可能不多，直接用名称遍历
        elif line.list_type == "31":
            for mat_name, mat_id in self._material_by_name.items():
                clean = re.sub(r"[\s\-_（）()（）]", "", mat_name)
                if clean == name or (len(clean) > 2 and (name in clean or clean in name)):
                    return {"table": "HC", "id": mat_id, "confidence": 0.7, "method": "fuzzy"}
        return None
