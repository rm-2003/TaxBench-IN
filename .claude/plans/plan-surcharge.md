# Sub-plan: Surcharge

## Background
Reference has separate rate tables for old and new regimes. The only difference is the >₹5Cr bracket: old regime = 37%, new regime = 25% (capped). All other brackets are identical. The calculator already reads `regime` from the input (`"old"` or `"new"`), so surcharge simply picks the right table.

Surcharge rate tables:

| Total Taxable Income | Old Regime | New Regime |
|---|---|---|
| ≤ ₹50L | 0% | 0% |
| > ₹50L to ₹1Cr | 10% | 10% |
| > ₹1Cr to ₹2Cr | 15% | 15% |
| > ₹2Cr to ₹5Cr | 25% | 25% |
| > ₹5Cr | 37% | 25% (capped) |

Surcharge applies to `tax_after_rebate`. Marginal relief is applied in `plan-marginal-relief.md`.

---

## Script_input.json changes

None.

---

## Script_output.json changes

None — `"Surcharge": 0` field already exists; will now be populated.

---

## tax_calculator.py changes

### Add two constants at top of file (replace the single `NEW_REGIME_SURCHARGE_RATES`):
```python
OLD_REGIME_SURCHARGE_RATES = [
    (5_000_000,    0.00),   # ≤ 50L
    (10_000_000,   0.10),   # 50L–1Cr
    (20_000_000,   0.15),   # 1Cr–2Cr
    (50_000_000,   0.25),   # 2Cr–5Cr
    (float("inf"), 0.37),   # >5Cr
]

NEW_REGIME_SURCHARGE_RATES = [
    (5_000_000,    0.00),   # ≤ 50L
    (10_000_000,   0.10),   # 50L–1Cr
    (20_000_000,   0.15),   # 1Cr–2Cr
    (50_000_000,   0.25),   # 2Cr–5Cr
    (float("inf"), 0.25),   # >5Cr (capped at 25%)
]
```

### Replace `surcharge = 0.0` placeholder with:
```python
surcharge_table = NEW_REGIME_SURCHARGE_RATES if regime == "new" else OLD_REGIME_SURCHARGE_RATES
surcharge_rate = 0.0
for upper, rate in surcharge_table:
    if total_taxable <= upper:
        surcharge_rate = rate
        break
# Marginal relief applied via compute_surcharge_with_relief() — see plan-marginal-relief.md
surcharge = compute_surcharge_with_relief(total_taxable, tax_after_rebate, surcharge_rate, surcharge_table)
```

Cess remains `(tax_after_rebate + surcharge) * CESS_RATE` — no change.

---

## CHANGELOG.md note (to be added to v1.2 section)
- Surcharge: both old regime (0/10/15/25/37%) and new regime (0/10/15/25/25% capped) rate tables implemented; regime-aware selection; marginal relief applied (see marginal relief entry)
