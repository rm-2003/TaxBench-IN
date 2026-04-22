# Plan Index: V1.2 changes from Reference.md diff

Six sub-plans. Implement in order (misc first since other plans depend on clean schema).

| Order | File | Covers |
|---|---|---|
| 1 | [plan-misc.md](plan-misc.md) | Section 16(ii), 80C narrowing, 80E, 80TTA/TTB, 80G modes, 80EE/80P removal |
| 2 | [plan-80d.md](plan-80d.md) | 80D medical insurance — full implementation with mode enforcement, multi-year split, age limits |
| 3 | [plan-capital-gains.md](plan-capital-gains.md) | Capital gains Other — per-asset input, auto-classification, per-asset output breakdown |
| 4 | [plan-surcharge.md](plan-surcharge.md) | Surcharge rate table (new regime) |
| 5 | [plan-marginal-relief.md](plan-marginal-relief.md) | 87A marginal relief + surcharge marginal relief (shared helper function) |
| 6 | [plan-mutual-funds.md](plan-mutual-funds.md) | Mutual Fund transactions — all types, CII indexation, auto-classification |

After all six: update CHANGELOG.md v1.2 section with implemented items and revised placeholder list.

---

## Deferred
- Income from Other Sources new sub-items (lottery, commission, other)
- LTCG @ 20% tax rate (output field exists as placeholder)
