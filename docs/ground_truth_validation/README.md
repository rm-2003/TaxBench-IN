# Ground-truth validation against the ITD Income & Tax Calculator

Four cases from `tests/generated/` were entered by hand into the Income Tax
Department's own "Income & Tax Calculator" (AY 2026-27, New Tax Regime, age
below 60) and its printed output saved here. The cases were chosen to isolate
each way the disputed s.87A reading shows up in the benchmark.

**Two of the four reproduce the stored ground truth exactly. Two do not**, for
reasons that are about data entry rather than the s.87A question — see below.

## Result

| Case | Estimator total tax | Ground truth | Verdict |
|---|---|---|---|
| `input_0170` | 41,600 | 41,600 | **matches, every line** |
| `input_0172` | 68,120 | 68,120 | **matches, every line** |
| `input_0176` | 51,896 | 10,296 | differs — deduction not applied |
| `input_0186` | 53,884 | 1,885 | differs — LTCG mis-entered by 80,000 |

## What this settles: the s.87A threshold is measured against normal income

`input_0172` is decisive and carries no confound, because it has **no
deductions at all**. Normal income is 12,40,000 and total income is 15,69,000 —
3.69 lakh above the 12 lakh threshold — and the department's calculator still
granted a **26,000 rebate**:

| Line | Estimator | Ground truth |
|---|---|---|
| Gross Total Income | 1,569,000 | 1,569,000 |
| Taxable Income | 1,569,000 | 1,569,000 |
| Tax at Normal Rates | 66,000 | 66,000 |
| Tax at Special Rates | 25,500 | 25,500 |
| Total Tax before Rebate | 91,500 | 91,500 |
| **Less: Tax Rebate u/s 87A** | **26,000** | **26,000** |
| Health & Education Cess | 2,620 | 2,620 |
| **Total Tax on Income** | **68,120** | **68,120** |

So the 12 lakh ceiling is tested against income excluding special-rate income,
and marginal relief is computed as though the capital gains were not there.
This is the shape that covers 40 of the 56 affected cases, and it is the group
the earlier three-scenario check never tested.

`input_0170` confirms the marginal-relief formula on its own: no capital gains,
total income 12,40,000, slab tax 66,000, rebate 26,000, total 41,600.

The estimator splits LTCG differently from `tax_calculator.py` — it reported the
whole 3,29,000 of `input_0172`'s gains under "LTCG covered u/s 112A" where the
calculator splits 1,99,000 of s.112A from 1,30,000 of non-equity. The tax is
identical either way (25,500), because the shared 1,25,000 exemption is applied
once and both buckets are charged at 12.5%.

## RESOLVED: the estimator was right and the ground truth was wrong

The section below was written before page 7 of `Input_176_Portal.pdf` was read.
It records a hypothesis — that the 50,000 had been typed into a field the new
regime disallows — which **the PDF disproves**: the amount sits on the
`Deductions u/s 80CCD (2) (Employers contribution towards NPS)` line, correctly
entered, with every other deduction line at 0. It is left here unedited because
the reasoning it contains is what the next section corrects.

The actual cause was a bug in `tax_calculator.py`. `gross_salary` was built from
ten named salary components, and the employer's NPS contribution is not one of
them — but it was then deducted under 80CCD(2). The same rupees were excluded
from income and subtracted from it. Under s.17(1)(viii) an employer's
contribution to NPS **is** salary, and 80CCD(2) then relieves it: net neutral up
to the cap, but it has to enter income before it can be taken out.

`input_0176` after the fix:

| Line | Estimator | Ground truth (fixed) | Ground truth (before) |
|---|---|---|---|
| Gross Salary | 13,50,000 implied | 13,50,000 | 13,00,000 |
| Taxable Income | 12,89,500 | **12,89,500** | 12,39,500 |
| Total Tax on Income | 51,896 | **51,896** | 10,296 |

`input_0186` reconciles too. It now computes to 43,485 against the estimator's
53,884, and the gap is exactly the 80,000 of LTCG that was over-entered:
80,000 x 12.5% = 10,000, plus 4% cess = 10,400, and 53,885 - 43,485 = 10,400.
All four PDFs are therefore fully accounted for, three matching to the rupee and
the fourth explained by a known entry error.

**Scope of the correction: 367 of 569 cases carried a non-zero 80CCD(2)** (227
old regime, 140 new; 212 government, 155 private) and every one had its taxable
income understated by the contribution — median 70,000, up to 3,22,000.
Regenerating `_expected` moved 378 cases in all, the extra 11 being low-salary
cases where the 75,000 standard deduction had been capped by a gross salary
below it. All collected model outputs were re-graded offline with
`tests/rescore.py`; no inference was re-run.

Two things worth recording about how this was missed. The bug survived all 27
calculator tests because only one involved a government employer and that test
asserted nothing beyond `Section 16(ii)` — the error lived in the interaction
between salary construction and a deduction, which no single test spanned.
`test28_80ccd2_employer_nps_in_salary.json` now covers it. And it was found only
because two of four estimator checks *disagreed*: had all four matched, it would
have shipped.

## Superseded hypothesis: whether 80CCD(2) survives in the new regime

`input_0176`'s income entries are correct — the 9,900 of special-rate tax is
exactly 49,500 x 20%, and the estimator's Taxable Income of 12,89,500 equals the
stored Gross Total Income to the rupee. The single difference is the 50,000
deduction: the estimator **displays** `Deductions 50000` and then does not
subtract it, taxing the full 12,89,500. The ground truth deducts it and taxes
12,39,500.

That 50,000 is **80CCD(2), the employer's NPS contribution**, which s.115BAC
preserves in the new regime — unlike 80C, 80CCD(1B) and most of Chapter VI-A.
The most likely explanation is therefore a data-entry mistake: the amount went
into a field the new regime correctly disallows. The estimator echoing the
figure and then zeroing it is consistent with that.

**This is unresolved and the exposure is larger than the s.87A question was:
140 of the 247 new-regime cases carry a non-zero 80CCD(2), a quarter of the
whole benchmark.**

To close it, re-run `input_0176` alone with the 50,000 entered specifically in
**"Deductions u/s 80CCD(2) — Employers contribution towards NPS"**. Expected if
the ground truth is right: Taxable Income 12,39,500, Total Tax on Income 10,296.

`input_0186` needs no interpretation — it was simply entered wrong. The
estimator's Taxable Income of 14,59,500 exceeds the stored GTI of 13,79,500 by
80,000, and its 11,812 of special-rate tax implies 2,19,500 of LTCG against the
1,39,500 in the input. The same 80,000. It carries the 80CCD(2) issue too, so it
should be redone after `input_0176` resolves.

## Standing caveat

The estimator is the department's own tool, which makes agreement with it the
right standard for a benchmark of Indian income tax — but it is administrative
practice, not the statute. This issue was contested for AY 2025-26, when the
filing utility was changed mid-season to block the rebate against s.111A gains.
The write-up should say "validated against the ITD estimator", not "proven
correct". The calculator's own printed disclaimer says the same thing.

## Provenance

Entered manually by a third party on the public e-filing portal; PDFs are the
calculator's own print output, unedited. The figures in the tables above were
read back from these PDFs and checked against `tests/generated/input_*.json`
`_expected` blocks field by field.
