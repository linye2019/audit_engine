import re
from typing import Any


def _safe_compare(a, b) -> int:
    try:
        if isinstance(a, str) and isinstance(b, str) and a.isdigit() and b.isdigit():
            a, b = int(a), int(b)
        if a == b:
            return 0
        return -1 if a < b else 1
    except TypeError:
        try:
            a, b = float(a), float(b)
            if a == b:
                return 0
            return -1 if a < b else 1
        except (ValueError, TypeError):
            return -1


OPERATORS = {}


def register_operator(name: str, func):
    OPERATORS[name] = func


register_operator("eq", lambda a, b: a == b)
register_operator("ne", lambda a, b: a != b)
register_operator("!=", lambda a, b: a != b)
register_operator("gt", lambda a, b: a is not None and b is not None and _safe_compare(a, b) > 0)
register_operator("gte", lambda a, b: a is not None and b is not None and _safe_compare(a, b) >= 0)
register_operator("lt", lambda a, b: a is not None and b is not None and _safe_compare(a, b) < 0)
register_operator("lte", lambda a, b: a is not None and b is not None and _safe_compare(a, b) <= 0)
register_operator("in", lambda a, b: a in (b if isinstance(b, list) else [b]))
register_operator("not_in", lambda a, b: a not in (b if isinstance(b, list) else [b]))
register_operator("contains", lambda a, b: b in str(a) if a else False)
register_operator("not_contains", lambda a, b: b not in str(a) if a else True)
register_operator("regex", lambda a, b: bool(re.search(str(b), str(a))) if a is not None else False)
register_operator("not_regex", lambda a, b: not bool(re.search(str(b), str(a))) if a is not None else True)
register_operator("is_null", lambda a, _: a is None or (isinstance(a, str) and a.strip() == ""))
register_operator("is_not_null", lambda a, _: a is not None and not (isinstance(a, str) and a.strip() == ""))
register_operator("any_contains", lambda a, b: isinstance(a, list) and any(b in str(item) for item in a))
register_operator("none_contains", lambda a, b: isinstance(a, list) and not any(b in str(item) for item in a))


def _op_coexists_with(a, b):
    if isinstance(b, str):
        return isinstance(a, list) and bool(b) and any(b in str(item) for item in a)
    elif isinstance(b, dict):
        return isinstance(a, list) and any(
            any(str(v) in str(item) for v in [
                b.get("med_list_code"), b.get("project_code"),
                b.get("med_list_name"), b.get("project_name")
            ] if v)
            for item in a
        )
    return False


def _op_not_exists(a, b):
    if isinstance(b, str):
        return not (isinstance(a, list) and bool(b) and any(b in str(item) for item in a))
    elif isinstance(b, dict):
        return not any(
            any(str(v) in str(item) for v in [
                b.get("med_list_code"), b.get("project_code"),
                b.get("med_list_name"), b.get("project_name")
            ] if v)
            for item in a
        )
    return True


def _op_not_between(a, b):
    return a is not None and isinstance(b, list) and len(b) == 2 and not (b[0] <= a <= b[1])


def _op_len_gt(a, b):
    return isinstance(a, (list, str, dict)) and len(a) > b


def _op_len_gte(a, b):
    return isinstance(a, (list, str, dict)) and len(a) >= b


register_operator("coexists_with", _op_coexists_with)
register_operator("not_exists", _op_not_exists)
register_operator("not_between", _op_not_between)
register_operator("len_gt", _op_len_gt)
register_operator("len_gte", _op_len_gte)