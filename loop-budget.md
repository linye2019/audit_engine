---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 8584983581cff71c15107d5026ec0e62_4b898203774711f19641525400d9a7a1
    ReservedCode1: KQWhW9X0RamxyYYe7Zn5t1mWVV0tExww1vRsiDujBCaADH6LqFOi9lEvZYW26rVGd0dUAtKNDfEQsQe8G5pS+H2W5823CUh69HA8Hsi6LLjLzyJTj8r/SPkiDXza2N18d8pPlMmJud+OwRrIoKu1A4pFLlJHQL8onS5ekV5NQHY7DLnsR4rrql/qS+A=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 8584983581cff71c15107d5026ec0e62_4b898203774711f19641525400d9a7a1
    ReservedCode2: KQWhW9X0RamxyYYe7Zn5t1mWVV0tExww1vRsiDujBCaADH6LqFOi9lEvZYW26rVGd0dUAtKNDfEQsQe8G5pS+H2W5823CUh69HA8Hsi6LLjLzyJTj8r/SPkiDXza2N18d8pPlMmJud+OwRrIoKu1A4pFLlJHQL8onS5ekV5NQHY7DLnsR4rrql/qS+A=
---

# Loop Budget — Medicare Audit Engine

> Primary loop: **Daily Triage** (Claude Code, L1 report-only)

## Daily Limits

| Loop | Max runs/day | Max tokens/day | Max sub-agent spawns/run |
|------|--------------|----------------|--------------------------|
| Daily Triage | 2 | 100,000 | 0 (L1) / 2 (L2) |
| Dependency Sweeper | 4 (L2) | 200,000 (L2) | 1 (L2) |
| PR Babysitter | 48 (L2) | 300,000 (L2) | 2 (L2) |

## Monthly Estimate (L1 only)

| Item | Estimate |
|------|----------|
| Runs per month | ~22 weekdays |
| Tokens per run | ~3,000 – 8,000 (report-only) |
| Monthly token budget | ~66,000 – 176,000 |

## On Budget Exceed

1. Pause all schedulers immediately
2. Append `BUDGET_EXCEEDED` event to `loop-run-log.md`
3. Update `STATE.md` High Priority section
4. Human review: adjust budget or optimize loop

## Kill Switch

- Set `loop-pause-all: true` in `STATE.md` → all loops exit on next cycle
- Resume only after human removes the flag and confirms in `STATE.md`

## Estimate Spend

```bash
npx @cobusgreyling/loop-cost --pattern daily-triage --level L1
```
*（内容由AI生成，仅供参考）*
