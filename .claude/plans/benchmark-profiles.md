# Plan: Benchmark Profiles (Option A)

## Context
The synthetic data generator (see `synthetic-data-generator.md`) defines 19 parameters with full factor definitions, trap cases, and gotcha scenarios. However, pairwise combination produces many sparse cases where most sections are "none" — trivially easy for an LLM to compute. Real tax filings have 10+ active sections interacting simultaneously (cap scaling, loss netting, surcharge relief, etc.).

This plan layers on top of the generator: define ~10 realistic "base taxpayer profiles" that fix 10–12 parameters to non-trivial values, then vary the remaining parameters to cover gotchas. Each case is dense enough that an LLM can't shortcut by computing sections in isolation.

**Target: 500 total cases.**

---

## Design

### Structure
```
PROFILES = {
    "profile_name": {
        "fixed": { param_name: factor_label, ... },   # 10–12 params pinned to specific factors
        "vary":  [param_name, ...],                    # remaining params cycle through all factors
    },
    ...
}
```

For each profile:
1. Start with the fixed factor selections — these form the dense "skeleton"
2. Vary the remaining parameters across all their factors using pairwise or full factorial (depending on count)
3. Each generated case inherits the profile's fixed skeleton + one combination of the varied parameters
4. `build_case()` from the generator merges all overrides, resolves cross-dependencies, runs the calculator

### Why this works for benchmarking
- Every case has 10+ active sections → LLM must handle interactions (80CCE cap scaling, loss netting across CG buckets, surcharge relief, etc.)
- Varied parameters inject gotchas into an already-complex context → harder to notice a trap when there's real computation happening around it
- Profiles map to recognizable taxpayer archetypes → results can be sliced by profile ("how did the model do on senior citizens vs. high-income govt employees?")

---

## Profiles (~10 profiles × ~50 cases each = 500)

### Profile 1: `mid_salary_private_new_metro` (~50 cases)
*Typical private sector employee, new regime, metro city, mid-career*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `mid` | Normal slab computation, no rebate/surcharge |
| hra_city | `metro_pct_binding` | Active HRA exemption (50% of basic+DA binding) — but new regime should zero it out |
| lta | `claim_less_than_salary_lta` | Active LTA claim — new regime should zero it out |
| employment_type | `private` | Entertainment allowance trap (always 0) |
| entertainment_allowance | `high_5k_cap_binding` | Non-zero input but private employee → must be 0 |
| tax_regime | `new` | **Key test**: LLM sees non-zero HRA, LTA, 80C, 80D inputs but must output 0 for all except 16(ia), 16(iii), 80CCD(2) |
| age_and_interest | `young_low_interest` | Age 35, modest interest income |
| deductions_80c_cce | `partial_under_cap` | PPF 50k, ELSS 30k — but new regime should zero these out |
| tds | `partial` | Positive net tax |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| stock_stcg | 3 | STCG gain/loss in presence of salary income |
| stock_ltcg | 4 | LTCG exemption threshold, FMV benefit |
| equity_mf | 4 | Equity MF layered on top of stock CG |
| non_equity_mf | 7 | Debt MF CII gotcha, gold ETF, all in new regime context |
| capital_loss_carryforward | 6 | Loss netting with multiple CG sources active |
| nps | 5 | CCD(2) is the ONLY NPS deduction that works in new regime |
| health_insurance_80d | 7 | All 80D entries should be 0 in new regime — traps still matter |
| donations_80g | 5 | 80G should be 0 in new regime |

Varied: 8 params → pairwise ≈ **49 cases** (max factor count = 7)

**Key gotchas exercised**: New regime zeroing out HRA/LTA/80C/80D/80G while NPS CCD(2) still works. Entertainment for private = 0. Loss netting across stocks + MFs.

---

### Profile 2: `high_salary_govt_old_nonmetro` (~50 cases)
*Senior government employee, old regime, non-metro, high income triggering surcharge*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `just_above_50L` | 10% surcharge + marginal relief |
| hra_city | `nonmetro_40pct_binding` | Active HRA at 40% (non-metro) |
| employment_type | `government` | Entertainment deduction active, 14% NPS employer cap |
| entertainment_allowance | `high_5k_cap_binding` | ₹5,000 cap is binding (govt gets this) |
| tax_regime | `old` | All deductions active, standard deduction = ₹50k |
| age_and_interest | `young_high_interest` | Age 45, 80TTA capped at 10k |
| deductions_80c_cce | `over_cap_proportional` | 80CCE cap hit → proportional scaling across 80C/80CCC/80CCD(1) |
| nps | `with_employer` | Both self and employer NPS — CCD(2) at 14% for govt |
| tds | `partial` | Positive net tax after surcharge |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | LTA exemption with high salary |
| stock_stcg | 3 | STCG interacting with surcharge calculation |
| stock_ltcg | 4 | LTCG exemption + surcharge on special income |
| equity_mf | 4 | MF gains adding to already-high income |
| non_equity_mf | 7 | Debt MF CII, gold — all taxable in old regime |
| capital_loss_carryforward | 6 | Loss netting at high income levels |
| other_assets | 4 | Bonds/G-Secs/vehicle in high-income context |
| health_insurance_80d | 7 | Full 80D computation, all traps |
| education_loan_80e | 3 | 80E in old regime |
| donations_80g | 5 | 80G fully active in old regime |

Varied: 10 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: Surcharge marginal relief, 80CCE proportional scaling, entertainment for govt, NPS CCD(2) at 14%, vehicle exemption trap, 80D beneficiary traps, all in old regime where everything is active.

---

### Profile 3: `senior_citizen_old_investment_heavy` (~50 cases)
*Retired senior, old regime, income primarily from investments and interest*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `low_below_rebate` | Modest pension-like salary |
| hra_city | `none` | No rent (owns home) |
| employment_type | `private` | Retired from private sector |
| entertainment_allowance | `none` | No entertainment component |
| tax_regime | `old` | Old regime for maximum deductions |
| age_and_interest | `senior_above_limit` | Age 72, 80TTB capped at 50k (savings+deposits) |
| deductions_80c_cce | `components_sum_exactly_1_5L` | Maxed out 80C at exactly 1.5L |
| health_insurance_80d | `senior_parent_50k_limit` | Self (age 72 → senior → 50k limit) + parent (age 65 → senior → 50k limit) |
| tds | `partial` | Some TDS from interest income |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | LTA with low salary |
| stock_stcg | 3 | Short-term stock trades |
| stock_ltcg | 4 | Long-term stock with FMV grandfathering |
| equity_mf | 4 | Equity MFs — LTCG 112A shares exemption with stocks |
| non_equity_mf | 7 | Debt MF CII indexation, gold — major income source for retiree |
| capital_loss_carryforward | 6 | Loss netting across investment portfolio |
| other_assets | 4 | Bonds/debentures — typical retiree holdings |
| nps | 5 | NPS in retirement context |
| education_loan_80e | 3 | Possibly paying for grandchild's education |
| donations_80g | 5 | Charitable donations |

Varied: 10 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: 80TTB (not 80TTA) for senior, 80D senior limits (both self and parent are seniors), LTCG 1.25L exemption shared across stocks + equity MFs, CII indexation for debt MFs, 80CCE at exact cap boundary.

---

### Profile 4: `marginal_relief_new_regime` (~50 cases)
*Income just above 12L, new regime — tests 87A marginal relief with special income*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `just_above_12L_marginal` | Normal income ≈ 12.25L → marginal relief on slab tax |
| hra_city | `metro_rent_10pct_binding` | HRA input present — new regime must zero it |
| employment_type | `private` | Standard private |
| entertainment_allowance | `none` | Clean — focus on marginal relief |
| tax_regime | `new` | 87A marginal relief: slab tax capped at income above 12L |
| age_and_interest | `young_low_interest` | Age 35, modest interest |
| tds | `none` | Full tax payable — easier to verify marginal relief math |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | LTA zeroed by new regime |
| stock_stcg | 3 | STCG adds special-rate tax ON TOP of marginal relief |
| stock_ltcg | 4 | LTCG special-rate tax — still charged in full even with 87A |
| equity_mf | 4 | MF gains as special income interacting with rebate |
| non_equity_mf | 7 | Debt MF at slab (new regime) — affects normal income near 12L |
| capital_loss_carryforward | 6 | Losses reducing CG could push total taxable below/above 12L |
| other_assets | 4 | Other CG near the 12L boundary |
| deductions_80c_cce | 4 | Must be 0 in new regime |
| nps | 5 | CCD(2) could reduce taxable income across the 12L line |
| health_insurance_80d | 7 | Must be 0 in new regime |
| donations_80g | 5 | Must be 0 in new regime |
| education_loan_80e | 3 | Must be 0 in new regime |

Varied: 12 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: 87A marginal relief (slab tax capped at income above 12L, special-rate taxes charged in full), new regime zeroing deductions, CG losses potentially changing whether marginal relief kicks in.

---

### Profile 5: `surcharge_boundary_old_regime` (~50 cases)
*Very high income, old regime — tests surcharge at 1Cr boundary with marginal relief*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `just_above_1Cr` | 15% surcharge + marginal relief |
| hra_city | `metro_hra_received_binding` | HRA received is binding (large HRA, even larger rent) |
| employment_type | `private` | Private sector executive |
| entertainment_allowance | `low_amount_binding` | Non-zero but private → must be 0 |
| tax_regime | `old` | Old regime surcharge rates (37% at >5Cr vs 25% new) |
| age_and_interest | `young_high_interest` | Age 45, high interest income |
| deductions_80c_cce | `over_cap_proportional` | Maxed out deductions |
| nps | `with_employer` | Employer NPS at 10% (private + old regime) |
| tds | `partial` | Large TDS but still net payable |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | LTA exemption active in old regime |
| stock_stcg | 3 | STCG adding to already-surcharge-level income |
| stock_ltcg | 4 | LTCG as special income in surcharge calculation |
| equity_mf | 4 | MF gains compounding surcharge |
| non_equity_mf | 7 | Non-equity MF at slab rate — adds to normal income |
| capital_loss_carryforward | 6 | Losses could pull income below surcharge boundary |
| other_assets | 4 | Additional CG sources |
| health_insurance_80d | 7 | Full 80D active, all traps |
| education_loan_80e | 3 | 80E deduction reducing taxable |
| donations_80g | 5 | 80G active |

Varied: 10 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: Surcharge marginal relief at 1Cr boundary, entertainment for private = 0, 80CCE proportional scaling, NPS CCD(2) at 10% (private + old), losses potentially crossing the surcharge boundary.

---

### Profile 6: `zero_salary_capital_gains_only` (~50 cases)
*No salary — income entirely from capital gains and investments (e.g., day trader / investor)*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `zero` | No salary at all |
| hra_city | `none` | No HRA (no salary) |
| lta | `none` | No LTA (no salary) |
| employment_type | `private` | Nominal — irrelevant with zero salary |
| entertainment_allowance | `none` | No salary components |
| age_and_interest | `young_high_interest` | Age 45, significant interest income |
| tax_regime | `old` | Old regime — though with zero salary, Section 16 deductions are 0 anyway |
| tds | `excess_refund` | TDS from interest/CG sources exceeds tax → refund |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| stock_stcg | 3 | Primary income source |
| stock_ltcg | 4 | Primary income source |
| equity_mf | 4 | Major investment vehicle |
| non_equity_mf | 7 | Debt MFs, gold — CII indexation |
| capital_loss_carryforward | 6 | Loss netting is the core complexity here |
| other_assets | 4 | Bonds, G-Secs, vehicle |
| deductions_80c_cce | 4 | 80C still works in old regime even without salary |
| nps | 5 | NPS with zero salary — CCD(1) limit = 10% of 0 = 0 |
| health_insurance_80d | 7 | 80D still available |
| education_loan_80e | 3 | 80E available |
| donations_80g | 5 | 80G available |

Varied: 11 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: Standard deduction = min(75k, gross salary) = 0, NPS CCD(1) limit = 10% of 0 = 0 (trap — LLM might still deduct), LTCG 1.25L exemption shared across stocks + equity MFs + non-equity, complex loss netting across 4+ CG buckets, TDS refund.

---

### Profile 7: `low_income_old_regime_maxed_deductions` (~50 cases)
*Low salary, old regime — tests whether deductions can exceed income and what happens*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `low_below_rebate` | Gross salary ≈ 8–10L |
| hra_city | `metro_rent_10pct_binding` | Active HRA |
| employment_type | `government` | Entertainment allowance active |
| entertainment_allowance | `low_amount_binding` | 3k — amount is binding |
| tax_regime | `old` | All deductions active, 87A rebate threshold = 5L |
| age_and_interest | `young_low_interest` | Age 35, modest interest |
| deductions_80c_cce | `components_sum_exactly_1_5L` | Full 1.5L 80C used |
| nps | `spills_to_ccd1b` | NPS spillover to CCD(1B) — extra 50k deduction |
| health_insurance_80d | `senior_parent_50k_limit` | Large 80D claim (self 25k + parent 50k) |
| tds | `none` | Should be minimal/zero tax due to deductions |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | LTA exemption reducing already-low income |
| stock_stcg | 3 | Small CG on low income |
| stock_ltcg | 4 | LTCG exemption — might not even need it |
| equity_mf | 4 | MF gains |
| non_equity_mf | 7 | Debt MF taxation |
| capital_loss_carryforward | 6 | Losses on low-income profile |
| other_assets | 4 | Misc assets |
| education_loan_80e | 3 | 80E stacking with other deductions |
| donations_80g | 5 | 80G on top of everything |

Varied: 9 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: Entertainment for govt (3-way min), 80CCE at exact 1.5L + NPS CCD(1B) spillover, heavy deductions potentially driving taxable income very low, 87A rebate in old regime (threshold = 5L), 80D with senior parent.

---

### Profile 8: `above_2cr_new_regime` (~50 cases)
*Ultra-high income, new regime — 25% surcharge cap, minimal deductions*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `above_2Cr` | Taxable ≈ 2.1Cr, 25% surcharge (new regime cap) |
| hra_city | `metro_pct_binding` | Large HRA input — new regime must zero it |
| employment_type | `private` | Private executive |
| entertainment_allowance | `high_5k_cap_binding` | Non-zero input, private → must be 0 |
| tax_regime | `new` | 25% surcharge cap (vs 37% in old), only 16(ia) + 80CCD(2) |
| age_and_interest | `young_high_interest` | Age 45, high interest income |
| nps | `with_employer` | CCD(2) is the only real deduction in new regime |
| tds | `partial` | Large TDS but still net payable |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | Must be 0 in new regime |
| stock_stcg | 3 | STCG at 20% on top of 25% surcharge |
| stock_ltcg | 4 | LTCG with 25% surcharge |
| equity_mf | 4 | MF gains in ultra-high income context |
| non_equity_mf | 7 | All MF types |
| capital_loss_carryforward | 6 | Losses at this income level |
| other_assets | 4 | Additional CG |
| deductions_80c_cce | 4 | Must be 0 in new regime |
| health_insurance_80d | 7 | Must be 0 in new regime |
| education_loan_80e | 3 | Must be 0 in new regime |
| donations_80g | 5 | Must be 0 in new regime |

Varied: 11 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: New regime 25% surcharge cap (LLM might use old regime 37%), all deductions except 16(ia) and CCD(2) must be 0 despite non-zero inputs, entertainment for private = 0, cess on (tax + surcharge).

---

### Profile 9: `govt_new_regime_nps_focus` (~50 cases)
*Government employee, new regime — tests NPS CCD(2) at 14% as the key active deduction*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `mid` | Normal income, no surcharge |
| hra_city | `nonmetro_40pct_binding` | HRA input present — new regime must zero it |
| employment_type | `government` | 14% CCD(2) rate, entertainment eligible |
| entertainment_allowance | `high_5k_cap_binding` | Non-zero but new regime → must be 0 for Section 16(ii) |
| tax_regime | `new` | Only 16(ia) + 80CCD(2) active. Entertainment is Section 16(ii) so also 0 in new regime. |
| age_and_interest | `senior_below_limit` | Age 62, senior — 80TTB applicable but zeroed by new regime |
| deductions_80c_cce | `over_cap_proportional` | Heavy 80C input — all zeroed by new regime |
| nps | `with_employer` | CCD(2) at 14% for govt in new regime — the main deduction |
| tds | `partial` | Positive net tax |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| lta | 3 | Must be 0 |
| stock_stcg | 3 | CG computation |
| stock_ltcg | 4 | LTCG with exemption |
| equity_mf | 4 | MF gains |
| non_equity_mf | 7 | All MF types |
| capital_loss_carryforward | 6 | Loss netting |
| other_assets | 4 | Other CG |
| health_insurance_80d | 7 | Must be 0 in new regime |
| education_loan_80e | 3 | Must be 0 |
| donations_80g | 5 | Must be 0 |

Varied: 10 params → pairwise ≈ **49 cases**

**Key gotchas exercised**: Govt + new regime: entertainment (Section 16(ii)) is 0 even for govt in new regime (LLM might think govt always gets it), CCD(2) at 14%, 80TTB zeroed by new regime even though age qualifies, 80CCE zeroed despite large inputs.

---

### Profile 10: `mixed_income_old_all_active` (~56 cases)
*Mid-income, old regime, every section active — maximum complexity stress test*

| Fixed param | Factor | Why fixed |
|-------------|--------|-----------|
| salary_level | `mid` | Normal slab computation |
| hra_city | `metro_pct_binding` | Active HRA |
| lta | `claim_less_than_salary_lta` | Active LTA |
| employment_type | `government` | Entertainment active |
| entertainment_allowance | `low_amount_binding` | Amount binding (3k) |
| tax_regime | `old` | All deductions active |
| age_and_interest | `young_high_interest` | Age 45, 80TTA capped |
| deductions_80c_cce | `over_cap_proportional` | 80CCE scaling |
| nps | `with_employer` | CCD(1) + CCD(1B) + CCD(2) all active |
| health_insurance_80d | `senior_parent_50k_limit` | Both self and parent buckets active |

| Varied param | Factors | What it tests in this profile |
|--------------|---------|-------------------------------|
| stock_stcg | 3 | STCG computation |
| stock_ltcg | 4 | LTCG with exemption |
| equity_mf | 4 | Equity MF layered on stocks |
| non_equity_mf | 7 | All non-equity MF types |
| capital_loss_carryforward | 6 | Full loss netting complexity |
| other_assets | 4 | Bonds, G-Secs, vehicle trap |
| education_loan_80e | 3 | 80E stacking |
| donations_80g | 5 | Mixed 80G rates |
| tds | 3 | Payable / refund |

Varied: 9 params → pairwise ≈ **49 cases** (pad to 56 with random combos to hit 500 total)

**Key gotchas exercised**: Everything active simultaneously — the hardest cases. LLM must handle HRA + LTA + entertainment + 80CCE scaling + CCD(1B) spillover + 80D dual-bucket + 80G mixed rates + LTCG exemption shared across stocks and MFs + loss netting + CII indexation, all in one case.

---

## Case Count Summary (Actual)

| # | Profile | Fixed | Varied | Cases | File Range |
|---|---------|-------|--------|-------|------------|
| 1 | mid_salary_private_new_metro | 9 | 8 | 62 | `input_0001.json` – `input_0062.json` |
| 2 | high_salary_govt_old_nonmetro | 9 | 10 | 59 | `input_0063.json` – `input_0121.json` |
| 3 | senior_citizen_old_investment_heavy | 9 | 10 | 48 | `input_0122.json` – `input_0169.json` |
| 4 | marginal_relief_new_regime | 7 | 12 | 64 | `input_0170.json` – `input_0233.json` |
| 5 | surcharge_boundary_old_regime | 9 | 10 | 59 | `input_0234.json` – `input_0292.json` |
| 6 | zero_salary_capital_gains_only | 8 | 11 | 62 | `input_0293.json` – `input_0354.json` |
| 7 | low_income_old_regime_maxed_deductions | 10 | 9 | 48 | `input_0355.json` – `input_0402.json` |
| 8 | above_2cr_new_regime | 8 | 11 | 62 | `input_0403.json` – `input_0464.json` |
| 9 | govt_new_regime_nps_focus | 9 | 10 | 59 | `input_0465.json` – `input_0523.json` |
| 10 | mixed_income_old_all_active | 10 | 9 | 46 | `input_0524.json` – `input_0569.json` |
| | | | **Total** | **569** | |

---

## Gotcha coverage across profiles

| Trap | Covered by profiles |
|------|---------------------|
| New regime zeroes HRA/LTA/80C/80D/80G/80TTA/80TTB | 1, 4, 8, 9 |
| New regime zeroes entertainment (even for govt) | 9 |
| Entertainment for private = 0 | 1, 5, 6, 8 |
| NPS Tier-2 = 0 | 1, 3, 4, 6, 7, 8, 9, 10 (via varied nps) |
| NPS CCD(1) limit = 10% of 0 for zero salary | 6 |
| 80D cash premium = 0 | All profiles (via varied health_insurance_80d) |
| 80D group medical = 0 | All profiles (via varied health_insurance_80d) |
| 80D sibling = 0 | All profiles (via varied health_insurance_80d) |
| 80G cash > 2k = 0 | All profiles with varied donations |
| 80E year > 8 = 0 | All profiles with varied education_loan_80e |
| Vehicle gain = tax-exempt | 2, 3, 5, 6, 10 (via varied other_assets) |
| LTCL cannot offset STCG | All profiles with varied capital_loss_carryforward |
| Loss > 8 years = ignored | All profiles with varied capital_loss_carryforward |
| Debt MF post-2023 = slab | All profiles with varied non_equity_mf |
| CII Jan-Mar vs Apr-Dec FY gotcha | All profiles with varied non_equity_mf |
| 87A marginal relief | 4 |
| Surcharge marginal relief | 2, 5 |
| 80CCE proportional scaling | 2, 5, 9, 10 |
| LTCG 1.25L exemption shared across stocks + MFs | 3, 6, 10 |

---

## Implementation

The generator script (`tests/generate_test_cases.py`) needs a `--mode profiles` flag (or a separate entry point) that:
1. Reads PROFILES definitions
2. For each profile, generates pairwise combos of the varied parameters
3. Pins the fixed parameters and calls `build_case()` for each combo
4. Writes to `tests/generated/profile_<name>/case_NNN.json`

All factor definitions, `BASE_INPUT`, `deep_merge()`, `resolve_cross_dependencies()`, and `build_case()` are reused from the base generator — profiles are just a different combination strategy layered on top.
