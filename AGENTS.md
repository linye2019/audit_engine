---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 8584983581cff71c15107d5026ec0e62_498d81e6774711f19641525400d9a7a1
    ReservedCode1: IImKofr2n8aTyW1QPu4LbzyM0Fzo4InOAQ4GzyAt/gFWN8PbYSrurFzSDh3Yo+wyinDfy9VmQJ1wZOOoJK3o8JcbWhvUTBD7YxS+3UADaxjQ1HAvucc2a4C6XJpLDfkGuf8w2g34IQiJh0W3jlb1wNem4cIEG1OdnZgzFv4mQIML2A9U/OYgYXbWXpg=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 8584983581cff71c15107d5026ec0e62_498d81e6774711f19641525400d9a7a1
    ReservedCode2: IImKofr2n8aTyW1QPu4LbzyM0Fzo4InOAQ4GzyAt/gFWN8PbYSrurFzSDh3Yo+wyinDfy9VmQJ1wZOOoJK3o8JcbWhvUTBD7YxS+3UADaxjQ1HAvucc2a4C6XJpLDfkGuf8w2g34IQiJh0W3jlb1wNem4cIEG1OdnZgzFv4mQIML2A9U/OYgYXbWXpg=
---

# AGENTS.md — Medicare Audit Engine

## Build & Install
```bash
pip install -e ".[dev]"
```

## Test
```bash
# 全量测试
python -m pytest tests/ -v

# 跳过慢速测试
python -m pytest tests/ -v -m "not slow"

# 仅单元测试（跳过集成测试）
python -m pytest tests/ -v -m "not integration"

# 带覆盖率
python -m pytest tests/ -v --cov=audit_engine --cov-report=term
```

## Lint & Format
```bash
ruff check .          # 代码检查 (E, F, I, W, UP)
ruff format --check . # 格式检查（双引号、LF 换行、120 字符行长）
```

## Run API
```bash
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

## Project Conventions
- **Python**: >=3.9, type hints required
- **Framework**: FastAPI + Pydantic v2
- **Database**: SQLite, schema defined in `schema.sql`
- **API routes**: defined in `api/routes/`, schemas in `api/schemas.py`
- **Core engine**: `audit_engine/core/` — audit pipeline (pre_check / end_check / post_audit)
- **DSL**: `audit_engine/dsl/` — 18 operators, AND/OR/NOT logic
- **Matching**: `audit_engine/matcher/` — medical catalog matching
- **Models**: `audit_engine/models/` — claim / result Pydantic models
- **Repository**: `audit_engine/repo/` — SQLite data access
- **Tests**: one test file per module, `conftest.py` for shared fixtures

## Review Norms
- All PRs must pass `pytest` and `ruff check` before merge
- API changes require updating `docs/API_DOCS.md`
- Schema changes require `schema.sql` update + migration notes + tests
- DSL operator changes require `docs/RULE_BOOK.md` update
- Never merge PRs that disable or skip existing tests

## Loop Conventions
- Report-only week one (L1) before enabling auto-fix (L2)
- See LOOP.md for cadence and human gates
- All loop actions run in isolated git worktrees
- Verifier sub-agent must pass `pytest` before any commit
*（内容由AI生成，仅供参考）*
