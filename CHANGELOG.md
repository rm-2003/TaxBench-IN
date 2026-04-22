# Tax Calculator — Version History

---

## v1.1

### What's new
- Full salary computation (fixed + variable components)
- Section 10 exemptions: HRA (10(13A)), LTA (10(5))
- Section 16 deductions: standard (16(ia)), entertainment (16(ii)), professional tax (16(iii))
- Capital gains: STCG/LTCG classification by holding period, LTCG grandfathering (FMV 31 Jan 2018), prior loss offset
- 80C suite: LIP, PPF, EPF (employee), ELSS, NSC, SSY, tax-saving FD, SCSS, home loan principal, stamp duty
- 80CCC: pension scheme premium (current-year portion)
- 80CCD(1), 80CCD(1B), 80CCD(2) at both 10% and 14% of Basic+DA
- 80G: donation exemptions (100%/50% schemes, cash >₹2k exclusion)
- Tax computation: slab tax (New Regime FY 2025-26), STCG at 20%, LTCG at 12.5%, Section 87A rebate, cess at 4%

### Input → Output mapping

| Input Field | Action | Limit / Rule | Output Section |
|---|---|---|---|
| Age, Employment Type, City | Person parameters used downstream | — | Affects HRA %, 80CCD(2) %, Section 16(ii) |
| Gross Salary (all sub-fields) | Summed | None | Under Head Salaries → Gross Salary |
| Actual Rent Paid | HRA exemption = MIN(HRA, metro%×(Basic+DA), Rent − 10%×(Basic+DA)) | Metro 50%, non-metro 40% of Basic+DA | Section 10(13A) |
| LTA Travel Expenses Claimed | LTA exemption = MIN(LTA in salary, expenses claimed) | Eligibility (2/4 block years) assumed verified | Section 10(5) |
| Professional Tax | Deducted from salary | Max ₹2,500 | Section 16(iii) |
| Stock Sale Transactions | >365 days → LTCG (cost = MAX(cost, FMV 31 Jan 2018)); ≤365 days → STCG; STT not deducted from gain | LTCG: ₹1.25L exempt before 12.5% tax | Capital Gains → STCG 111A / LTCG 112A |
| Long/Short Term Capital Loss | Netted against respective gains | Up to 8 prior FYs for LTCG | Capital Gains |
| Other Short/Long Term Capital Gains | Passed through | — | Capital Gains → STCG Other / LTCG Other |
| Savings Bank / Deposit / Other Interest, EPF Taxable Interest | Passed through | — | Income from Other Sources |
| Life Insurance Premium, PPF, EPF employee, ELSS, NSC, SSY, FD (5yr), SCSS, Home Loan Principal, Stamp Duty | Summed; capped at ₹1.5L | ₹1,50,000 combined (80CCE) | Deductions → 80CCE → 80C |
| Pension Scheme Premium | Amount ÷ years paid (current-year portion only) | Within 80CCE ₹1.5L cap | Deductions → 80CCE → 80CCC |
| NPS Tier-1 Self Contribution | Up to 10% of Basic+DA into 80CCD(1); excess up to ₹50k into 80CCD(1B) | 80CCD(1) within 80CCE; 80CCD(1B) extra ₹50k outside cap | Deductions → 80CCD(1) + 80CCD(1B) |
| NPS Tier-1 Employer Contribution | Capped at 10% (private) or 14% (govt) of Basic+DA; both values shown | Total Deductions uses employment-appropriate % | Deductions → 80CCD(2) at 10% / 14% |
| Donations | Cash >₹2k excluded; 100% exempt: PM Cares, Nat. Defence, Sports, Cultural Funds; 50% exempt: PM Drought Relief Fund | Cash/kind >₹2,000 not exempt | Deductions → 80G |
| Health Insurance | Passed through (placeholder) | — | Deductions → 80D |
| Education Loan Interest, 80EE, 80TTA, 80TTB, 80P | Passed through (placeholder) | — | Deductions → respective fields |
| TDS | Subtracted from total tax liability | — | Tax Computation → Less: TDS |

### Tax computation note
Slab tax uses **New Regime FY 2025-26** (configurable constants in `tax_calculator.py`). STCG 111A at 20%, LTCG 112A at 12.5% on gains above ₹1.25L. Section 87A rebate on slab tax only (not STCG/LTCG) for total income ≤ ₹12L. Surcharge = 0 (placeholder). Cess = 4% on tax after rebate.

### Placeholders (not yet computed)
- Section 16(ii) entertainment allowance — no input field; always 0
- 80D (health insurance limits)
- 80E, 80EE, 80TTA, 80TTB, 80P
- Surcharge and marginal relief
- LTCG Other tax rate

---

## v1.1.1

### Input → Output mapping changes from v1.1

| Input Field | Change | Rule | Output Section |
|---|---|---|---|
| `Tax Regime` (new field) | Added; `"old"` or `"new"` | Drives standard deduction amount and 80CCD(2) rate | Affects Section 16(ia), Deductions → 80CCD(2) |
| Section 16(ia) standard deduction | Now regime-aware | Old: ₹50,000; New: ₹75,000 | Under Head Salaries → Section 16(ia) |
| 80CCE | Removed from input and output JSON | Cap of ₹1.5L on 80C + 80CCC + 80CCD(1) is enforced internally; each section's reported value is scaled proportionally; no explicit 80CCE field anywhere | Deductions → 80C, 80CCC, 80CCD(1) (flat fields) |
| `80CCD(2) at 10%` + `80CCD(2) at 14%` | Merged into single `80CCD(2)` | New regime: 14% for all; Old + govt: 14%; Old + private: 10% | Deductions → 80CCD(2) |

---

## v1.2 (in progress)

### v1.2 implementation plans
Detailed per-area plans stored in `.claude/plans/`:
- `plan-misc.md` — Section 16(ii), 80C field removals, 80E, 80TTA/TTB, 80G modes, 80EE/80P removal
- `plan-80d.md` — 80D medical insurance full implementation
- `plan-capital-gains.md` — Capital gains Other per-asset input/output and auto-classification
- `plan-surcharge.md` — Surcharge rate tables (old and new regimes)
- `plan-marginal-relief.md` — 87A marginal relief + surcharge marginal relief (shared helper)
- `plan-mutual-funds.md` — Mutual Fund transactions, CII indexation, type-based classification

### Synthetic data generator (planned)
- Extensible factorial generator: one `PARAMETERS` dict entry per income/expense category, each with N labelled factors
- Case generation via `itertools.product`; each output file includes `_description` and `_expected`
- Runner `run_generated_tests.py` strips meta fields, runs calculator, verifies expected values
- Implementation plan: `.claude/plans/synthetic-data-generator.md`

### v1.2.1

| Area | Change | Rule / Notes |
|---|---|---|
| `Age` field | Changed from string (`"<60"`) to numeric integer | All downstream checks use `>= 60` comparisons |
| `Gross Salary → Entertainment Allowance` | New input field | Used only for Section 16(ii); ignored for non-govt |
| Section 16(ii) | Implemented for government employees | MIN(₹5,000, 20% Basic Salary, entertainment allowance received) |
| 80C eligible instruments | Removed: LIP, Tax Saving FD (5yr), Home Loan Principal, Stamp Duty | Only PPF, EPF, ELSS, NSC, SSY, SCSS remain |
| `Education Loan Interest` | Changed from flat number to `{"Interest Paid": 0, "Year of Repayment": 0}` | Deduction = 0 if Year of Repayment outside [1, 8] |
| 80E | Implemented with 8-year repayment limit | `Interest Paid` deducted only if `Year of Repayment` ∈ [1, 8] |
| 80TTA | Implemented; age < 60 only | MIN(₹10,000, savings bank interest); mutually exclusive with 80TTB |
| 80TTB | Implemented; age ≥ 60 only | MIN(₹50,000, savings bank interest + deposit interest) |
| 80EE, 80P | Removed from schema and calculator | Out of scope |
| 80G modes | Valid modes clarified | `cash`, `cheque`, `upi`, `credit card`, `net banking`; cash >₹2,000 excluded |
| `Health Insurance` | Restructured from flat dict to list of payment entries | Per-entry beneficiary filtering (self/spouse/children/parents only), paid-by check (group insurance excluded), mode check (premium must be non-cash), multi-year premium split (Amount ÷ Years Paid) |
| 80D | Fully implemented | Single ₹5,000 preventive checkup cap across all entries; age-based limits ₹25k/<60, ₹50k/≥60; two independent buckets: self/family and parents |

### v1.2.2

| Area | Change | Rule / Notes |
|---|---|---|
| Surcharge | Implemented for both regimes | Old regime: 0/10/15/25/37%; New regime: 0/10/15/25/25% (capped); regime-aware selection |
| Surcharge marginal relief | Implemented | At each bracket boundary, excess tax+surcharge capped to excess income above that boundary; applied via `compute_surcharge_with_relief()` |
| 87A marginal relief | Implemented | When `total_taxable > ₹12L`: slab tax capped at income above ₹12L from normal sources; special-rate taxes (STCG/LTCG) always charged in full |

### v1.2.3

| Area | Change | Rule / Notes |
|---|---|---|
| `Mutual Fund Transactions` | New input field (list) | Fields: Type, Purchase Date, Sale Date, Purchase Value, Sale Value |
| MF classification | Implemented via `classify_mf_transaction()` | equity/hybrid-equity ≤12m → STCG 111A; >12m → LTCG 112A; ELSS <36m → no taxable event; debt pre-Apr-2023 >24m → LTCG Other @12.5% with CII indexation; debt post-2023 → always slab; gold-ETF 12m threshold; gold-MF/international 24m threshold |
| CII indexation | Embedded `CII_TABLE` (2001–2024); no user input required | Indexed cost = Purchase Value × (CII[sale year] / CII[purchase year]) |
| Capital loss set-off | Corrected to asymmetric rules | STCL offsets STCG first; residual STCL offsets LTCG; LTCL offsets LTCG only |
| MF LTCG Other @12.5% | No ₹1.25L exemption | Exemption applies to equity Section 112A gains only; debt/gold/international MF LTCG taxed in full at 12.5% |
| CII FY key logic | Fixed to use financial year, not calendar year | Dates in Jan–Mar map to the prior FY (e.g. Jan 2024 → FY 2023-24 → key 2023); `fy_start()` helper added |
| CII 2025 | Added CII = 376 for FY 2025-26 | — |
| Capital loss carry-forward eligibility | 8-year limit enforced | Losses with `Financial Year` start > 8 AYs before AY 2025-26 are excluded; applies to both LTCL and STCL entries |

### v1.2.4

| Area | Change | Rule / Notes |
|---|---|---|
| `Other Short/Long Term Capital Gains` | Removed flat input fields | Replaced by per-asset structured inputs |
| `Privately Owned Vehicle` | New input field (Sale Amount, Purchase Amount, Held for duration in years) | Always tax-exempt — gain not added to any capital gains bucket |
| `Bonds`, `Debentures`, `G-Secs` | New input fields (same structure) | Auto-classified: held >1 year → LTCG Non-Equity @12.5%; ≤1 year → STCG Other (slab) |
| `STCG (Other)` output | Changed from flat number to per-asset dict | Keys: Bonds, Debentures, G-Secs, Mutual Funds, Total |
| `LTCG (Other)` output | Renamed to `LTCG (Non-Equity @ 12.5%)`, changed to per-asset dict | Keys: Bonds, Debentures, G-Secs, Mutual Funds, Total |
| `LTCG (Other @ 20%)` output | Added as placeholder | Always 0; no assets assigned yet |
| Tax on LTCG Non-Equity | ₹1.25L exemption shared with 112A | Remaining exemption after 112A applied to non-equity LTCG |
| Capital loss set-off | Expanded to all capital gains buckets | LTCL offsets all LTCG (112A + non-equity) proportionally; STCL offsets all STCG first, residual offsets remaining LTCG proportionally |
| Breakdown consistency | Per-asset breakdown dicts scaled after loss netting | Breakdown values match post-loss-netting totals |

### Placeholders (not yet computed)
- LTCG (Other @ 20%): no assets assigned

---

## v1.3 (in progress)

### v1.3.1

| Area | Change | Rule / Notes |
|---|---|---|
| Old regime slabs | Implemented | ₹0–2.5L 0%, ₹2.5–5L 5%, ₹5–10L 20%, >₹10L 30%; 87A rebate ₹12,500 for income ≤₹5L |
| Regime-aware tax computation | Slab rates, rebate threshold/max, and surcharge slab table now all driven by `Tax Regime` | Previously always used new regime slabs |
| Govt employer NPS (80CCD(2)) | Compulsory for government employees | If govt, employer contribution auto-set to at least 14% of Basic+DA |
| New regime gating | Only Section 16(ia) and 80CCD(2) allowed under new regime | Section 10(13A), 10(5), 16(ii), 16(iii), 80C/CCC/CCD(1)/CCD(1B)/80D/80E/80G/80TTA/80TTB all zeroed out |
| 87A marginal relief | New regime only | Old regime: simple rebate (no marginal relief); New regime: marginal relief when income > ₹12L |

---

### v1.3.2

#### v1.3.2.1
| Area | Change | Rule / Notes |
|---|---|---|
| Synthetic data generator | Implemented via `tests/generate_test_cases.py` | 19 parameters with full factor definitions; generates pairwise, OTA, or full-factorial test cases; imports calculator for ground-truth expected outputs |
| Benchmark profiles | ~10 recognizable taxpayer archetypes (private new-regime, govt old-regime, senior investor, marginal relief, surcharge boundary, zero-salary, maxed-deductions, ultra-high income, govt new-regime, all-sections-active) | Each profile fixes 7–10 parameters to non-trivial values, varies 8–12 remaining parameters; ~50 cases per profile, 500 total; layers on top of generator strategy to test section interactions (caps, loss netting, relief calculations) |

#### v1.3.2.2
| Area | Change | Rule / Notes |
|---|---|---|
| Metro city check (bug fix) | `"metro" in city` → `city == "metro"` | Was matching `"non-metro"` as metro (50% instead of 40%) |
| Entertainment Allowance in Gross Salary (bug fix) | Added to gross salary sum | Was missing — entertainment component not counted in total gross salary |
| Generator implemented | `python3 tests/generate_test_cases.py [pairwise\|ota\|profiles]` | Default mode `profiles` generates 569 test cases across 10 profiles; each JSON contains `input`, `_description`, `_expected` |
| Test cases generated | 569 cases in `tests/generated/` | `input_0001.json` – `input_0569.json`; profile-to-case mapping documented in `benchmark-profiles.md` |

#### v1.3.2.3
| Area | Change | Rule / Notes |
|---|---|---|
| **Output key renames — rates removed** | **7 JSON keys renamed across `Script_output.json`, `tax_calculator.py`, `calculator_tests/run_tests.py`, and all 569 generated test cases** | **LLM must infer tax rates from context, not from field names** |
| `LTCG (Non-Equity @ 12.5%)` | → **`LTCG (Non-Equity)`** | Capital Gains section |
| `LTCG (Other @ 20%)` | → **`LTCG (Other)`** | Capital Gains section |
| `Tax on STCG (Section 111A) at 20%` | → **`Tax on STCG (Section 111A)`** | Tax Computation section |
| `Tax on LTCG (Section 112A) at 12.5%` | → **`Tax on LTCG (Section 112A)`** | Tax Computation section |
| `Tax on LTCG (Non-Equity) at 12.5%` | → **`Tax on LTCG (Non-Equity)`** | Tax Computation section |
| `Tax on LTCG (Other) at 20%` | → **`Tax on LTCG (Other)`** | Tax Computation section |
| `Health and Education Cess (4%)` | → **`Health and Education Cess`** | Tax Computation section |
| **Reusable rename tool** | **`tools/rename_json_keys.py`** | **Edit `MAPPING` dict + `TARGETS` list, run script; handles JSON (recursive key rename) and Python/text (exact string replacement)** |