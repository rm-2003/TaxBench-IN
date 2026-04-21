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

## v1.2 (planned)

### Changes from v1.1.1
- Section 16(ii) entertainment allowance — government employees; MIN(₹5,000, 20% of Basic Salary, total entertainment allowance received in FY)
- 80EE and 80P removed (out of scope)
- Surcharge computation for income >₹50L (slabs pending clarification)
- Section 87A marginal relief for STCG/LTCG pushing income just above ₹12L
- Surcharge marginal relief at each slab boundary (pending clarification)

### Synthetic data generator (planned)
- Extensible factorial generator: one `PARAMETERS` dict entry per income/expense category, each with N labelled factors
- Case generation via `itertools.product`; each output file includes `_description` and `_expected`
- Runner `run_generated_tests.py` strips meta fields, runs calculator, verifies expected values
- Combination strategy and factor value config placement pending final decision

### Placeholders (not yet computed)
- 80D (health insurance limits)
- 80E, 80TTA, 80TTB
- LTCG Other tax rate
- Age-based differentiation (<60 / 60-80 / >80)
- Surcharge and marginal relief (pending clarification)
