# Plan: Synthetic Benchmark Data Generator

## Context
The tax calculator is being used as a benchmark to evaluate LLM accuracy: an LLM is given a `Script_input.json` and must produce a `Script_output.json`. The benchmark needs test cases that cover every rule, limit, and "not allowed" condition so that LLM failures on specific clauses are detectable and attributable. The generator programmatically produces (input JSON + ground-truth expected output) pairs by combining factor levels across tax parameters.

---

## Key Design Decisions

### Combination strategy
Decide after counting factors per parameter. Generator prints the full factorial count at startup so user can choose. Supports:
- `"pairwise"` — every pair of factor values appears in at least one test case (~200–400 cases)
- `"ota"` — baseline + one variation each (cheapest, for smoke tests)
- `"full_factorial"` — all combos, guarded by MAX_CASES

### Factor values location
All in a top-level `PARAMETERS` dict. Adding a category = adding one dict entry, zero logic change.

### Expected values
Computed inline by importing `tax_calculator.calculate()` at generation time. Ground truth always in sync.

### Cross-parameter dependencies at build time
Some factor values depend on others in the same case:
- **Self/spouse/children Beneficiary Age** in health_insurance_80d entries: derived from the taxpayer's `Age` (set by `age_and_interest`) at case-build time, not hardcoded in the factor. Only parent Beneficiary Age is set explicitly.
- **NPS `with_employer` factor**: uses a fixed employer contribution amount; the calculator caps it at the appropriate % of basic+DA based on regime and employment type.

### Prerequisite: calculator must enforce new regime deduction rules
Under new regime, only Section 16(ia) (standard deduction ₹75k), Section 16(iii) (professional tax), and 80CCD(2) (employer NPS) apply. All other exemptions and deductions must be zeroed out. The calculator currently does NOT enforce this — it computes all deductions regardless of regime. **The calculator must be updated before the generator can produce correct expected values for new regime cases.**

---

## PARAMETERS — Full Scenario Matrix (19 parameters)

### 1. `salary_level` (7 factors)
Tests: slab transitions, 87A rebate (full + marginal relief), surcharge tiers + marginal relief at boundaries

| Factor | Basic | DA | HRA | LTA | Other components | Purpose |
|--------|-------|----|-----|-----|-----------------|---------|
| `zero` | 0 | 0 | 0 | 0 | all 0 | No salary at all |
| `low_below_rebate` | 300,000 | 50,000 | 80,000 | 20,000 | small | Total taxable ≤ 12L → full 87A rebate = min(slab tax, 60k) |
| `just_above_12L_marginal` | 400,000 | 60,000 | 100,000 | 25,000 | tuned so normal income ≈ 12.25L | 87A marginal relief: slab tax capped at income above 12L; special-rate taxes (STCG/LTCG) still charged in full |
| `mid` | 800,000 | 100,000 | 200,000 | 50,000 | moderate | Normal slab computation, no rebate, no surcharge |
| `just_above_50L` | 2,000,000 | 300,000 | 500,000 | 80,000 | tuned so taxable ≈ 51L | 10% surcharge + surcharge marginal relief |
| `just_above_1Cr` | 3,500,000 | 500,000 | 800,000 | 100,000 | tuned so taxable ≈ 1.02Cr | 15% surcharge + marginal relief |
| `above_2Cr` | 7,000,000 | 800,000 | 1,500,000 | 150,000 | tuned so taxable ≈ 2.1Cr | 25% surcharge (new regime cap) |

### 2. `hra_city` (5 factors)
Tests: 3-way min(HRA received, metro% of basic+DA, rent − 10% of basic+DA) + metro vs non-metro (50% vs 40%)

| Factor | City | Rent Paid | Purpose |
|--------|------|-----------|---------|
| `none` | metro | 0 | No rent → 0 exemption regardless of HRA in salary |
| `metro_rent_10pct_binding` | metro | Low rent | Rent − 10% of basic+DA is the binding (smallest) value; city = metro (50%) |
| `metro_pct_binding` | metro | High rent | 50% of basic+DA is binding |
| `metro_hra_received_binding` | metro | Very high rent | HRA component itself is binding |
| `nonmetro_40pct_binding` | non-metro | Moderate rent | 40% of basic+DA is binding; tests the non-metro path |

### 3. `lta` (3 factors)
Tests: min(LTA in salary, LTA claimed)

| Factor | LTA Claimed | Purpose |
|--------|-------------|---------|
| `none` | 0 | No claim |
| `claim_less_than_salary_lta` | < LTA component | Actual claim is binding |
| `claim_exceeds_salary_lta` | > LTA component | Salary LTA is binding (excess is taxable) |

### 4. `employment_type` (2 factors)
Tests: entertainment allowance eligibility, 80CCD(2) rate, compulsory employer NPS

| Factor | Employment Type |
|--------|----------------|
| `private` | "private" — no entertainment deduction, 10% NPS employer cap (old regime) |
| `government` | "government" — entertainment deduction eligible, 14% NPS employer cap, compulsory employer NPS contribution |

### 5. `entertainment_allowance` (3 factors)
Tests: govt-only 3-way min(₹5,000, 20% of basic, amount received); private gets 0

| Factor | Amount | Purpose |
|--------|--------|---------|
| `none` | 0 | No entertainment component |
| `low_amount_binding` | 3,000 | Amount < 5000 and < 20% basic → amount is binding |
| `high_5k_cap_binding` | 50,000 | Amount and 20% basic both > 5000 → ₹5,000 cap is binding |

Note: When `employment_type=private`, all factors produce 0 — this is intentional (trap for LLM).

### 6. `stock_stcg` (3 factors)
Tests: STCG 111A (20%), short-term loss. Independent of stock_ltcg — both can coexist.

| Factor | Transactions | Purpose |
|--------|-------------|---------|
| `none` | empty | No short-term stock transactions |
| `stcg_gain` | 1 stock held 200 days, sold at profit | STCG 111A gain (taxed at 20%) |
| `stcg_loss` | 1 stock held 200 days, sold at loss | Negative STCG → raw loss feeds into loss netting |

### 7. `stock_ltcg` (4 factors)
Tests: LTCG 112A (12.5% above 1.25L), FMV grandfathering. Independent of stock_stcg.

| Factor | Transactions | Purpose |
|--------|-------------|---------|
| `none` | empty | No long-term stock transactions |
| `ltcg_below_exempt` | 1 stock held 400 days, gain = 80,000 | LTCG < 1.25L → 0 tax |
| `ltcg_above_exempt` | 1 stock held 400 days, gain = 300,000 | LTCG > 1.25L → (300k − 1.25L) × 12.5% |
| `ltcg_fmv_benefit` | 1 stock held 400 days, FMV > cost price | Cost basis = max(cost, FMV) reduces taxable gain |

### 8. `capital_loss_carryforward` (6 factors)
Tests: asymmetric loss set-off rules (STCL offsets any CG, LTCL only LTCG), 8-year limit

| Factor | Prior Losses | Purpose |
|--------|-------------|---------|
| `none` | no carryforward | Baseline |
| `stcl_offsets_stcg` | ST loss < STCG | STCL partially reduces STCG 111A |
| `stcl_spills_to_ltcg` | ST loss > STCG | Residual STCL reduces LTCG (cross-type offset) |
| `ltcl_offsets_ltcg` | LT loss < LTCG | LTCL reduces LTCG only (cannot touch STCG) |
| `ltcl_exceeds_ltcg` | LT loss > LTCG, STCG present | Excess LTCL doesn't touch STCG — trap for LLM |
| `loss_beyond_8_years` | FY > 8 years ago | Should be ignored (beyond carry-forward window) |

### 9. `other_assets` (4 factors)
Tests: Bonds/Debentures/G-Secs classification, vehicle exemption

| Factor | Assets | Purpose |
|--------|--------|---------|
| `none` | all zeros | No other assets |
| `bonds_short_term` | Bonds held < 1 year, profit | → STCG Other (slab rate) |
| `gsecs_long_term` | G-Secs held > 1 year, profit | → LTCG Non-Equity @ 12.5% |
| `vehicle_gain` | Vehicle sold at profit | Always tax-exempt — trap for LLM that might tax it |

### 10. `equity_mf` (4 factors)
Tests: Equity, hybrid-equity, and ELSS mutual funds. Independent of non_equity_mf.

| Factor | Type | Purchase Date | Sale Date | Purpose |
|--------|------|--------------|-----------|---------|
| `none` | — | — | — | No equity MF transactions |
| `equity_stcg` | equity | 2025-06-01 | 2025-11-15 | Held < 12m → STCG 111A at 20% |
| `equity_ltcg` | equity | 2024-01-15 | 2025-06-15 | Held > 12m → LTCG 112A at 12.5% |
| `elss_matured` | elss | 2022-01-01 | 2025-06-01 | Held ≥ 36m → LTCG 112A (ELSS cannot be sold before 36-month lock-in) |

### 11. `non_equity_mf` (7 factors)
Tests: Debt (pre/post 2023), CII indexation with Jan-Mar vs Apr-Dec purchase, gold ETF, international. Independent of equity_mf.

| Factor | Type | Purchase Date | Sale Date | Purpose |
|--------|------|--------------|-----------|---------|
| `none` | — | — | — | No non-equity MF transactions |
| `debt_pre2023_jan_mar` | debt | 2022-03-15 | 2025-06-01 | Bought Jan-Mar → FY 2021-22 (CII=317). LLM must map Jan-Mar to *prior* FY for CII lookup |
| `debt_pre2023_apr_dec` | debt | 2021-09-10 | 2025-06-01 | Bought Apr-Dec → FY 2021-22 (CII=317). Same FY as above but date is in the same calendar year as FY start. Contrasts with Jan-Mar to test whether LLM applies FY mapping correctly in both directions |
| `debt_post2023_slab` | debt | 2023-06-01 | 2025-12-01 | Bought after Apr 2023 → always slab rate regardless of holding period |
| `gold_etf_stcg` | gold-etf | 2025-03-01 | 2025-09-01 | Held ≤ 12m → STCG Other (slab rate) |
| `gold_etf_ltcg` | gold-etf | 2024-01-01 | 2025-06-01 | Held > 12m → LTCG Other 12.5% |
| `international_ltcg` | international | 2023-01-01 | 2025-06-01 | Held > 24m → LTCG Other 12.5% |

#### CII indexation gotcha: Jan-Mar vs Apr-Dec purchase
Both `debt_pre2023_jan_mar` and `debt_pre2023_apr_dec` land in FY 2021-22 (CII=317), but via different date→FY mappings:
- **2022-03-15** → month < Apr → FY = 2022-1 = **2021** (prior calendar year)
- **2021-09-10** → month ≥ Apr → FY = **2021** (same calendar year)
- Same CII, but an LLM that naively uses `year` instead of `fy_start(date)` will get the Jan-Mar case wrong
- **Indexed cost**: `Purchase Value × (CII[sale_FY] / CII[purchase_FY])`

#### Rule: MF purchase dates must be ≥ FY 2001-02
The calculator's CII table starts at FY 2001 (CII=100). All generated MF purchase dates must fall on or after 2001-04-01 to ensure a valid CII lookup. No factor should produce a purchase date before this.

### 12. `deductions_80c_cce` (4 factors)
Tests: 80C individual components, 80CCE combined cap with 80CCC/80CCD(1), proportional scaling

| Factor | 80C items | 80CCC | 80CCD(1) | Purpose |
|--------|-----------|-------|----------|---------|
| `none` | all 0 | 0 | 0 | No deductions |
| `partial_under_cap` | PPF 50k, ELSS 30k | 0 | 0 | Sum = 80k, well under 1.5L |
| `components_sum_exactly_1_5L` | PPF 80k, EPF 40k, ELSS 30k | 0 | 0 | Exactly 1.5L — no scaling needed |
| `over_cap_proportional` | PPF 100k, ELSS 80k | 20k (pen 60k/3yr) | NPS self 40k (10% of basic+DA) | Sum = 240k > 1.5L → scale down proportionally |

### 13. `nps` (5 factors)
Tests: CCD(1) limit, CCD(1B) spillover, CCD(2) employer rate, Tier-2 trap, missing employer contribution

| Factor | NPS Self (Tier-1) | NPS Employer (Tier-1) | Tier-2 | Purpose |
|--------|-------------------|-----------------------|--------|---------|
| `none` | 0 | 0 | 0 | No NPS |
| `self_only_within_ccd1` | 30,000 | 0 | 0 | Self < 10% of basic+DA → all in CCD(1). Employer = 0 — when combined with govt employment, tests missing compulsory contribution (CCD(2) = 0) |
| `spills_to_ccd1b` | 200,000 | 0 | 0 | Self > 10% of basic+DA → excess spills to CCD(1B), capped at 50k |
| `with_employer` | 50,000 | 50,000 | 0 | Both self and employer contribute. Calculator caps employer at 14%/10% of basic+DA. When combined with govt, this is the realistic scenario. |
| `tier2_only_trap` | 0 | 0 | 1,000 | Tier-2 minimum to keep account active (₹1,000). NO tax benefit — LLM should give 0 for all CCD sections |

Note on govt employees: In reality, employer NPS contribution is compulsory for government employees. The `self_only_within_ccd1` and `spills_to_ccd1b` factors have Employer=0, which creates a "missing compulsory contribution" scenario when combined with `employment_type=government`. The calculator correctly outputs CCD(2)=0 for Employer=0 input. The `with_employer` factor is the realistic govt scenario.

### 14. `health_insurance_80d` (7 factors)
Tests: valid/invalid beneficiary, cash exclusion, group insurance exclusion, senior citizen limits, preventive checkup cap

| Factor | Entries | Purpose |
|--------|---------|---------|
| `none` | empty | No health insurance |
| `valid_cheque_self` | Self, cheque, 15,000 | Standard valid claim |
| `cash_premium_excluded` | Self, cash, 25,000 | **Insurance premium in cash → 0** (trap) |
| `group_medical_excluded` | Self, paid by "group medical insurance", 25,000 | **Group medical → 0** (trap) |
| `invalid_beneficiary_sibling` | "sibling", cheque, 20,000 | **Sibling not in valid set → 0** (trap) |
| `senior_parent_50k_limit` | Self cheque 20k + Parent (age 65) cheque 45k | Self bucket = 25k limit; Parent bucket = 50k limit (senior) |
| `preventive_checkup_cap` | Preventive checkup 8,000 | Capped at 5,000 regardless of amount |

**Age derivation rule**: Self/spouse/children `Beneficiary Age` is derived from the taxpayer's `Age` (set by `age_and_interest`) at case-build time — never hardcoded in the factor. Only parent `Beneficiary Age` is set explicitly (e.g., 65 in `senior_parent_50k_limit`). This prevents contradictions like taxpayer age=30 but self beneficiary age=65.

### 15. `education_loan_80e` (3 factors)
Tests: 8-year repayment window

| Factor | Year of Repayment | Purpose |
|--------|-------------------|---------|
| `none` | 0 | No education loan |
| `within_8yr_window` | 5 | Year 5 → deduction applies (no cap on amount) |
| `beyond_8yr_trap` | 9 | Year 9 → **deduction = 0** (trap) |

### 16. `donations_80g` (5 factors)
Tests: 100% vs 50% exempt schemes, cash >2k exclusion, multiple donations mixing both rates

| Factor | Donations | Purpose |
|--------|-----------|---------|
| `none` | empty | No donations |
| `cash_over_2k_excluded` | PM Cares, cash, 5,000 | **Cash > ₹2,000 → excluded** (trap) |
| `full_exempt_100pct` | PM Cares, non-cash, 10,000 | 100% of 10,000 = 10,000 deduction |
| `half_exempt_50pct` | PM Drought Relief, non-cash, 10,000 | 50% of 10,000 = 5,000 deduction |
| `mixed_100_and_50_pct` | PM Cares 10k non-cash + Drought Relief 8k non-cash | 10,000 + 4,000 = 14,000 total — LLM must apply different rates per scheme |

### 17. `age_and_interest` (4 factors)
Tests: 80TTA vs 80TTB mutual exclusion, age-gated limits

| Factor | Age | Savings Interest | Deposit Interest | Purpose |
|--------|-----|-----------------|-----------------|---------|
| `young_low_interest` | 35 | 5,000 | 10,000 | 80TTA = 5,000 (< 10k cap); 80TTB = 0 |
| `young_high_interest` | 45 | 25,000 | 30,000 | 80TTA = 10,000 (capped); 80TTB = 0 |
| `senior_below_limit` | 62 | 20,000 | 15,000 | 80TTA = 0; 80TTB = 35,000 (savings+deposits < 50k) |
| `senior_above_limit` | 72 | 30,000 | 40,000 | 80TTA = 0; 80TTB = 50,000 (capped) |

**Age values chosen to avoid collision with `health_insurance_80d`**: The 80D parameter has parent beneficiary age = 65 in `senior_parent_50k_limit`. Taxpayer ages here (35, 45, 62, 72) are all different from 65. Self/spouse/children beneficiary ages in 80D entries are derived from these ages at case-build time (see 80D note above).

### 18. `tax_regime` (2 factors)
Tests: new regime deduction restrictions — under new regime, most exemptions and deductions are NOT available

| Factor | Regime | Purpose |
|--------|--------|---------|
| `new` | "new" | **Only Section 16(ia) (₹75k), Section 16(iii) (prof tax), and 80CCD(2) (employer NPS) apply.** All other deductions and exemptions (HRA, LTA, entertainment, 80C, 80CCC, 80CCD(1), 80CCD(1B), 80D, 80E, 80G, 80TTA, 80TTB) must be 0 regardless of input values. This is a major trap — LLM sees non-zero inputs but must output 0 for these sections. |
| `old` | "old" | All deductions and exemptions apply normally. Standard deduction = ₹50k. 80CCD(2) rate = 14% for govt, 10% for private. |

### 19. `tds` (3 factors)

| Factor | TDS | Purpose |
|--------|-----|---------|
| `none` | 0 | Full tax payable |
| `partial` | < total tax | Positive net tax |
| `excess_refund` | > total tax | Negative net tax (refund) |

---

## Complete "Not Allowed" / Trap Case Summary

These are deliberately included to test whether the LLM blindly applies deductions or correctly rejects them:

| # | Input condition | Expected output | Parameter |
|---|----------------|-----------------|-----------|
| 1 | NPS Tier-2 only contribution (₹1,000) | All CCD sections = 0 | `nps: tier2_only_trap` |
| 2 | Entertainment allowance for private employee | Section 16(ii) = 0 | `entertainment + employment_type: private` |
| 3 | Health insurance premium paid in cash | That 80D entry = 0 | `health_insurance: cash_premium_excluded` |
| 4 | Health insurance paid by group medical | That 80D entry = 0 | `health_insurance: group_medical_excluded` |
| 5 | Health insurance for sibling | That 80D entry = 0 | `health_insurance: invalid_beneficiary_sibling` |
| 6 | Donation in cash > ₹2,000 | That 80G entry = 0 | `donations: cash_over_2k_excluded` |
| 7 | Education loan repayment year > 8 | 80E = 0 | `education_loan: beyond_8yr_trap` |
| 8 | Privately owned vehicle sold at profit | Not in any STCG/LTCG bucket | `other_assets: vehicle_gain` |
| 9 | LTCL trying to offset STCG | STCG untouched | `capital_loss: ltcl_exceeds_ltcg` |
| 10 | Loss carryforward > 8 years old | Loss ignored | `capital_loss: loss_beyond_8_years` |
| 11 | Debt MF bought post Apr 2023, held > 24m | Taxed at slab rate, NOT 12.5% | `non_equity_mf: debt_post2023_slab` |
| 12 | New regime + non-zero 80C/80D/80G/HRA/LTA inputs | All those deductions = 0 | `tax_regime: new` + any deduction parameter |
| 13 | Debt MF Jan-Mar purchase: naive `year` gives wrong CII | Indexed cost must use `fy_start()` FY, not calendar year | `non_equity_mf: debt_pre2023_jan_mar` vs `debt_pre2023_apr_dec` |

---

## Factor Count Summary

| # | Parameter | Factors |
|---|-----------|---------|
| 1 | salary_level | 7 |
| 2 | hra_city | 5 |
| 3 | lta | 3 |
| 4 | employment_type | 2 |
| 5 | entertainment_allowance | 3 |
| 6 | stock_stcg | 3 |
| 7 | stock_ltcg | 4 |
| 8 | capital_loss_carryforward | 6 |
| 9 | other_assets | 4 |
| 10 | equity_mf | 4 |
| 11 | non_equity_mf | 7 |
| 12 | deductions_80c_cce | 4 |
| 13 | nps | 5 |
| 14 | health_insurance_80d | 7 |
| 15 | education_loan_80e | 3 |
| 16 | donations_80g | 5 |
| 17 | age_and_interest | 4 |
| 18 | tax_regime | 2 |
| 19 | tds | 3 |
| | **Total parameters** | **19** |
| | **Full factorial** | **7×5×3×2×3×3×4×6×4×4×7×4×5×7×3×5×4×2×3 ≈ 213 billion** |
| | **Pairwise (L2)** | **~200–400 cases** |

---

## Files

| File | Action |
|------|--------|
| `tests/generate_test_cases.py` | Create — PARAMETERS dict + combination logic + inline expected computation |
| `tests/generated/` | Created at runtime by generator |

### Critical existing files (read-only, imported)
- `tax_calculator.py` — `calculate()` function imported for ground-truth computation (must be updated to enforce new regime deduction rules first)
- `Script_input.json` — reference for BASE_INPUT template
- `Script_output.json` — reference for expected output structure

---

## `generate_test_cases.py` — structure

```
BASE_INPUT        # neutral JSON: all zeros, age=35, private, metro, new regime
PARAMETERS        # dict of 19 parameters as above — overrides only
```

### Function descriptions

**`deep_merge(base, overrides) -> dict`**
Recursively merges an override dict onto a copy of the base dict. For nested dicts it recurses; for lists and scalars the override replaces the base value entirely. This is how each factor's overrides get layered onto BASE_INPUT without mutating it.

**`resolve_cross_dependencies(case, combo) -> dict`**
Runs after all factor overrides are merged. Fixes values that depend on other parameters in the same case:
- Sets `Beneficiary Age` for self/spouse/children entries in Health Insurance to the taxpayer's `Age` (from `age_and_interest`)
- Any future cross-parameter fixups go here

**`generate_pairwise(params) -> list[list[int]]`**
Takes the PARAMETERS dict and returns a list of index-tuples where every pair of (param_i=factor_x, param_j=factor_y) appears in at least one tuple. Uses `allpairspy` library or an inline greedy covering-array algorithm. This is the default strategy — produces ~200–400 cases for 19 parameters.

**`generate_ota(params) -> list[list[int]]`**
"One at a time" — returns the baseline case (all index-0 factors) plus one case per non-zero factor where only that factor is changed. Produces exactly `1 + sum(len(factors)-1 for each param)` cases. Useful for quick smoke tests where you want to isolate each factor's effect.

**`generate_full_factorial(params, max_cases) -> list[list[int]]`**
Cartesian product of all factor indices via `itertools.product`. Guarded by MAX_CASES — if the product exceeds the limit, it raises an error rather than silently generating billions of cases.

**`build_case(combo: dict[str, factor]) -> dict`**
Takes one combination (a dict mapping parameter name → selected factor) and:
1. Deep-merges all factor overrides onto a fresh copy of BASE_INPUT
2. Calls `resolve_cross_dependencies` to fix derived values
3. Imports and calls `tax_calculator.calculate()` on the merged input to get the ground-truth expected output
4. Returns `{"input": {...}, "_description": "salary_level=mid|hra_city=metro_pct|...", "_expected": {...}}`

**`__main__` block**
Entry point. Reads strategy from CLI arg (default "pairwise"), prints factor counts and full factorial size, generates combinations via the selected strategy, builds each case, and writes each to `tests/generated/case_NNN_<label_slug>.json`.
