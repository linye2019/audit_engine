# Performance Analyzer Subagent

**Model**: sonnet
**Tools**: Read, Grep, Glob, Bash

## Analysis Focus

Analyze the audit_engine for performance bottlenecks:

### Critical Path: Precheck (<200ms SLA)
- DSL expression evaluation hot path (`audit_engine/dsl/evaluator.py`)
- Catalog matching latency (`audit_engine/matcher/catalog.py`)
- SQLite query performance (indexes, query plans)
- Cache hit ratios in `audit_engine/core/`

### Database Performance
- Missing indexes (check `schema.sql` and actual query patterns)
- N+1 queries in bulk audit processing
- Write-ahead log (WAL) configuration
- Connection pooling

### Python Performance
- Hot loops in core engine (`audit_engine/core/engine.py`)
- Unnecessary object allocations in `reasoning.py`
- Slow imports or module loading

## Output Format

```
## Performance Analysis: {file}

### Hot Path
- {function}: {avg_time}ms, called {n} times
- {bottleneck description}

### Recommendations
1. {specific actionable fix}
2. ...

### Expected Improvement
- {metric}: {before} → {after}
```
