---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 8584983581cff71c15107d5026ec0e62_4a9b810e774711f19641525400d9a7a1
    ReservedCode1: CUfM/ZizltjwXU8gZNnnLU2O05mVJcXuclXrtPsq3FyfvFGqdC82SM4ZbD0ouiZqCQL7KG12nsk04e6+H5vm/0kpnBcLKGuhgU7Xh/nGRCaIaOFWv+ok8Jh4GLHpBzSY4Bac1lFpI1CxL3DgujIUdzV2j7kCwWZFehqG1GMImoumCWFC3N0G/KdTXcQ=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 8584983581cff71c15107d5026ec0e62_4a9b810e774711f19641525400d9a7a1
    ReservedCode2: CUfM/ZizltjwXU8gZNnnLU2O05mVJcXuclXrtPsq3FyfvFGqdC82SM4ZbD0ouiZqCQL7KG12nsk04e6+H5vm/0kpnBcLKGuhgU7Xh/nGRCaIaOFWv+ok8Jh4GLHpBzSY4Bac1lFpI1CxL3DgujIUdzV2j7kCwWZFehqG1GMImoumCWFC3N0G/KdTXcQ=
---

# Loop Configuration — Medicare Audit Engine

## Active Loops

| Pattern | Cadence | Tool | Status | Command |
|---------|---------|------|--------|---------|
| Daily Triage | 1d (weekdays) | Claude Code | L1 report-only | `/loop 1d Run $loop-triage. Update STATE.md. Report-only, no auto-fix.` |

## Planned Loops (future phases)

| Pattern | Cadence | Phase | Prerequisite |
|---------|---------|-------|--------------|
| Dependency Sweeper | 6h–1d | L2 | Daily Triage stable for 2 weeks |
| PR Babysitter | 10–15m | L2 | Team agreement on AI draft PRs |
| Changelog Drafter | 1d or on tag | L2 | Release workflow established |

## Multi-loop Priority

CI Sweeper → PR Babysitter → Dependency Sweeper → Changelog Drafter → Daily Triage (report)

Only Daily Triage is active in L1. Other loops will be introduced one at a time after the previous stabilizes.

## Human Gates

- **L1 (current)**: no auto-fix. All findings go to STATE.md for human review.
- **L2 (future)**: auto-fix on allowlist paths only. All denylist paths require human gate.
- Full denylist and safety gates: see `loop-constraints.md`.

Gate escalation triggers:
- Any change touching `audit_engine/core/` → escalate
- Any change to `schema.sql` → escalate
- Major dependency version bump → escalate
- 3 failed fix attempts on same item → escalate
- Token budget exceed 80% → switch to report-only

## Worktrees

- L2+: one isolated `git worktree` per fix attempt
- Discard worktree on verifier REJECT or human escalation
- Never modify working directory directly

## Connectors (MCP)

- MCP already configured in `.atomcode/mcp.json`
- L1: GitHub read-only for issue/PR discovery
- L2+: expand to read + comment; no write actions without human approval

## Budget

- Daily token cap: 100k (L1)
- Max sub-agent spawns per run: 0 (L1), 2 (L2)
- Kill switch: `loop-pause-all` flag in `STATE.md`
- Budget details: `loop-budget.md`

## Observability

- Run history: `loop-run-log.md` (appended each run)
- State drift detection: `npx @cobusgreyling/loop-sync .`
- Cost estimation: `npx @cobusgreyling/loop-cost --pattern daily-triage`

## Links

- Pattern: [daily-triage](https://github.com/cobusgreyling/loop-engineering/blob/main/patterns/daily-triage.md)
- Checklist: [loop-design-checklist](https://github.com/cobusgreyling/loop-engineering/blob/main/docs/loop-design-checklist.md)
- Constraints: `loop-constraints.md`
- Project conventions: `AGENTS.md`
*（内容由AI生成，仅供参考）*
