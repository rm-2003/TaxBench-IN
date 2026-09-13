# Sub-plan: 87A Marginal Relief & Surcharge Marginal Relief

## Core idea (same pattern, different threshold)
Both reliefs answer: "is the extra tax owed more than the extra income earned above a threshold?" If yes, cap the tax so the excess equals the extra income — not more.

---

## 87A Marginal Relief

### When it applies
Normal 87A only fires when `total_taxable ≤ 12L`. Marginal relief fires when `total_taxable > 12L` **but** the slab tax on `normal_income` (income excluding STCG/LTCG) exceeds the income that pushed it above 12L.

### Worked example (from reference)
- Total taxable = ₹12,45,000 (₹12,25,000 normal + ₹20,000 STCG)
- Tax on ₹12,25,000 at slab = ₹67,750
- Special tax (STCG) = ₹4,000
- Income above 12L (from normal sources) = ₹25,000
- Fair slab tax cap = ₹25,000 (you earned only ₹25k above the threshold)
- Marginal relief = ₹67,750 − ₹25,000 = ₹42,750
- Tax after rebate = ₹67,750 − ₹42,750 + ₹4,000 = ₹29,000 ✓

### Formula
```
normal_income = total_taxable - special_income   (special = STCG 111A + LTCG 112A + LTCG Other 12.5%)
income_above_threshold = max(0, normal_income - 12_00_000)
marginal_relief_87A = max(0, tax_slab - income_above_threshold)
```

Applied only when `total_taxable > REBATE_87A_THRESHOLD`. The standard rebate path (`total_taxable ≤ 12L`) is unchanged.

### Updated rebate logic in calculator
```python
if total_taxable <= REBATE_87A_THRESHOLD:
    rebate_87A = min(tax_slab, REBATE_87A_MAX)
else:
    income_above_threshold = max(0.0, normal_income - REBATE_87A_THRESHOLD)
    rebate_87A = max(0.0, tax_slab - income_above_threshold)
```

---

## Surcharge Marginal Relief

### When it applies
When income just crosses a surcharge bracket boundary, the extra tax+surcharge should not exceed the extra income above that boundary.

### Worked example (from reference)
- Income = ₹51L; surcharge rate = 10%
- Tax at ₹51L (before surcharge) = ₹13,42,500; surcharge = ₹1,34,250 → total = ₹14,76,750
- Tax at ₹50L (no surcharge) = ₹13,12,500
- Excess income = ₹51L − ₹50L = ₹1,00,000
- Excess tax = ₹14,76,750 − ₹13,12,500 = ₹1,64,250
- Marginal relief = ₹1,64,250 − ₹1,00,000 = ₹64,250
- Final tax = ₹14,76,750 − ₹64,250 = ₹14,12,500 ✓

### Formula
For each surcharge threshold the income crosses, find the previous boundary and apply:
```
tax_at_boundary = compute_slab_tax(threshold) - rebate_at_boundary
  (rebate is 0 since all thresholds are > 12L)
tax_with_surcharge = tax_after_rebate + surcharge  (i.e. tax_after_rebate * (1 + surcharge_rate))
excess_income = total_taxable - threshold
excess_tax = tax_with_surcharge - tax_at_boundary
marginal_relief_surcharge = max(0, excess_tax - excess_income)
final_surcharge = surcharge - marginal_relief_surcharge
```

### Helper function in calculator

Applies to both old and new regimes — caller passes the regime-appropriate slab table and surcharge table so the boundary tax computation uses the correct slabs.

```python
SURCHARGE_BOUNDARIES = [5_000_000, 10_000_000, 20_000_000, 50_000_000]

def compute_surcharge_with_relief(total_taxable, tax_after_rebate, surcharge_rate, slabs, surcharge_table):
    if surcharge_rate == 0.0:
        return 0.0
    # Find the highest boundary crossed
    crossed_boundary = None
    for b in SURCHARGE_BOUNDARIES:
        if total_taxable > b:
            crossed_boundary = b
    if crossed_boundary is None:
        return 0.0
    surcharge_raw = tax_after_rebate * surcharge_rate
    # Tax at the boundary under the same regime's slabs (no 87A rebate — boundary > 12L)
    tax_at_boundary = compute_slab_tax(crossed_boundary, slabs)
    # Tax at boundary also has surcharge = 0 (boundary is the threshold, not above it)
    tax_with_surcharge = tax_after_rebate + surcharge_raw
    excess_income = total_taxable - crossed_boundary
    excess_tax = tax_with_surcharge - tax_at_boundary
    relief = max(0.0, excess_tax - excess_income)
    return max(0.0, surcharge_raw - relief)
```

Call site in `calculate()` (see `plan-surcharge.md` for full surcharge block):
```python
surcharge_table = NEW_REGIME_SURCHARGE_RATES if regime == "new" else OLD_REGIME_SURCHARGE_RATES
slab_table      = NEW_REGIME_SLABS if regime == "new" else OLD_REGIME_SLABS
surcharge = compute_surcharge_with_relief(
    total_taxable, tax_after_rebate, surcharge_rate, slab_table, surcharge_table
)
```

Note: `OLD_REGIME_SLABS` will need to be added as a constant when old regime tax computation is implemented. For now, the function signature is ready; pass `NEW_REGIME_SLABS` for both until old regime slabs are defined.

---

## Script_input.json / Script_output.json changes

None — both fields already exist in output (`"Less: Rebate under Section 87A"`, `"Surcharge"`).

---

## Verification spot-checks
- Income ₹12,25,000, STCG ₹20,000 → rebate_87A = ₹42,750; net slab tax = ₹25,000
- Income ₹12,00,000, no special → rebate = min(60,000, tax_slab) (normal path unchanged)
- Income ₹51L → surcharge after relief = ₹14,12,500 − ₹13,12,500 = ₹1,00,000 net extra
- Income ₹50L → surcharge = 0

---

## CHANGELOG.md note (to be added to v1.2 section)
- Section 87A marginal relief: when total_taxable > ₹12L, slab tax capped at income above ₹12L from normal sources; special rate taxes (STCG/LTCG) always charged in full
- Surcharge marginal relief: at each bracket boundary, excess tax+surcharge capped to excess income above that boundary
