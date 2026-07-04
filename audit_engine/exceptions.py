class MedicareEngineError(Exception):
    """医保审核引擎基础异常"""
    pass


class RuleParseError(MedicareEngineError):
    """规则解析异常"""
    pass


class ConditionEvalError(MedicareEngineError):
    """条件评估异常"""
    pass


class CatalogMatchError(MedicareEngineError):
    """目录匹配异常"""
    pass


class DatabaseError(MedicareEngineError):
    """数据库操作异常"""
    pass