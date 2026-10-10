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

## Follow-up: two defects that made the ground truth undeliverable from the input

The 80CCD(2) fix above was correct but incomplete, and tracing its consequences
turned up two further defects. Both were found by asking a single question: why
was `gross_total_income` wrong in **every one** of nemotron's 36 `script` cases?

Neither is a tax error. The statute was applied correctly in both. That is
exactly why they survived 28 calculator tests and four ITD-estimator checks —
they are defects in what the benchmark *asks*, not in what it computes.

### 1. The government NPS imputation (212 cases)

`tax_calculator.py` set the employer contribution to
`max(declared, 0.14 × (Basic + DA))` for government employees. Government
employers do contribute 14% compulsorily, so the arithmetic was right. But the
amount appears nowhere in the input JSON and the rule nowhere in the system
prompt, so the answer key depended on a figure no model could derive.

All 212 government cases were affected: a median of **90,000** of salary invented
from nothing, up to **272,000**, with **48 cases declaring exactly 0**.

It hid because it **cancelled out of Total Taxable Income** — the 80CCD(2)
deduction equalled the imputed amount in all 212 cases — so the whole tax chain
stayed correct while Gross Salary, Net Salary, GTI, Total Deductions and
80CCD(2) were all wrong. Every test that asserted a *tax* figure passed.

It was caught by the fingerprint: `input_0355` and `input_0381` both showed a
**correct Total Taxable Income with GTI wrong by exactly −70,000**. A right
answer sitting on top of a wrong one.

The declared figure is now taken at face value. A benchmark may only ask what
its inputs support.

### 2. The `Other Interest` name collision (336 cases)

The required output nested `EPF Taxable Interest` inside a container called
`Other Interest`; the input used `Other Interest` as a separate flat number. The
same key meant a container on the way out and an amount on the way in, so the
input's amount entered Gross Total Income — correctly, it is income — with
nowhere to be reported. The invariant "GTI = sum of the reported heads" failed on
exactly the 336 cases carrying a non-zero value.

It also cost measurable accuracy, but **only where code is executed**. A model
writing Python had to infer the input's shape, and the output schema was the only
template the prompt offered, so it read
`data["Other Interest"]["EPF Taxable Interest"]` and hit `TypeError` on an int.
Both retry transcripts in the project do exactly this.

| gemma4-12b, `epf_taxable_interest` | correct |
|---|---|
| zero-shot | **100.0%** |
| script | **63.3%** (6 of 49 conflating the two meanings) |

Same model, same field, same inputs: a 37-point collapse from switching to code
generation. Across all nine zero-shot arms the collision was harmless — **0
conflations and 0 shape errors**, nemotron 508/508 — which locates the defect in
making a model infer input structure, not in the output schema as a
specification.

`Other Interest` is now a reportable amount and `EPF Taxable Interest` its
sibling. The invariant holds: **0 violations in 569 cases.** The prompt also
gained the input schema it never had.

### Effect on the results

Every model gained; none lost; the ordering is unchanged. No inference was
re-run — `tests/rescore.py` re-graded all 1,015 stored outputs offline.

| model | before | after |
|---|---|---|
| nemotron-3-ultra zero-shot | 60.63% | **62.52%** |
| tencent/hy3 | 52.43% | **54.38%** |
| gpt-oss-120b | 51.03% | **52.54%** |
| gemma-4-31b | 49.19% | **50.70%** |
| deepseek-v3 | 45.57% | **47.19%** |
| gpt-oss-20b | 38.22% | **39.57%** |
| gemma4-12b zero-shot | 37.84% | **38.81%** |
| llama-3.3-70b | 36.49% | **37.68%** |
| nemotron-nano-9b | 36.86% | **37.30%** |

The 816 zero-shot answers were preserved rather than discarded. Flattening the
schema moved `epf_taxable_interest`'s path, which would have made every stored
answer unscorable on that field and cost roughly two weeks of free quota to
re-collect. `LEGACY_FIELD_PATHS` in `tests/evaluate_llm.py` reads a field at its
former location when the current path is absent **in the answer only** — expected
values always use the current path, so it never changes what counts as correct.
Verified by re-grading to the same figures measured beforehand.

The two `script` arms *are* being re-collected, because for them the prompt
change is material. Their pre-fix checkpoints are in
`tests/evaluation_checkpoints/v1_preschemafix/`.

### Caveat worth carrying into the write-up

The NPS fix recovered far less than its case count suggests. `80ccd_2` flipped on
all 190 affected nemotron cases, but `gross_salary` on only 42 and
`gross_total_income` on **9** — on the rest a second, independent error sits
underneath. Aggregates is therefore **not** rescued and remains genuinely hard
rather than mis-specified. An estimate made earlier in this session put the
defect at ~5% of every model's score; the measured cost was 1–2 points.
