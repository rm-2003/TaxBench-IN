# Changelog

The answer key for AY2026-Bench is produced by `tax_calculator.py`. When a rule in the engine
was corrected, `_expected` was recomputed from each case's stored `input`; the taxpayer inputs
themselves never changed. Every stored model answer was then re-scored offline with
`tests/rescore.py`, so a correction never required re-running a model. Case counts below are
the cases whose answer key changed.

## Answer-key corrections

| Rule | What was wrong | Fix | Cases |
|---|---|---|---|
| Debt mutual funds (Finance Act 2024) | Long-term gains on debt funds bought before 1 Apr 2023 were indexed | Indexation removed for sales on or after 23 Jul 2024: flat gain at 12.5% | 126 |
| s.16(iii) professional tax | Capped at ₹2,500 | Cap ₹5,000, per the CBDT ITR-2 validation rules for AY 2026-27 | 0 (no input above ₹2,500) |
| s.80A(2) | Deductions could exceed gross total income, giving negative taxable income | Chapter VI-A deductions capped at GTI | 11 |
| s.17(1)(viii) employer NPS | The employer's contribution was deducted under 80CCD(2) but never added to salary | Added to gross salary, then relieved by 80CCD(2) up to its cap | 378 |
| Government employer NPS | A 14% contribution was imputed for government employees although the input never states it | The declared contribution is used as is | 212 |
| Output schema | `EPF Taxable Interest` was nested inside an `Other Interest` key, so the input's Other Interest entered GTI with nowhere to be reported | Both are flat fields; GTI now equals the sum of the reported heads in all cases. The system prompt also gained an explicit input schema | 569 (layout only) |
| s.55(2)(ac) grandfathering | The 31 Jan 2018 FMV step-up applied to shares bought after the cutoff, with FMV not capped at the sale price | Step-up only for shares bought before 1 Feb 2018; cost is the higher of actual cost and min(FMV, sale price) | 143 |
| s.112A(2) vs s.112 | The ₹1,25,000 equity LTCG relief spilled over onto non-equity LTCG | Relief applies to s.112A gains only; non-equity LTCG taxed at a flat 12.5% | 94 |
| Old-regime slabs by age | Basic exemption ₹2,50,000 at every age | ₹3,00,000 for 60–79, ₹5,00,000 for 80+ | 48 |
| Surcharge on special-rate income | 25%/37% surcharge applied to capital-gains tax | Surcharge on s.111A/112A/112 income capped at 15% | 48 |
| s.111A(2), s.112A(6) | Chapter VI-A deductions set against special-rate gains | Deductions limited to GTI less those gains | 25 |
| Surcharge marginal relief | Tax at the threshold computed as if all income were slab income | Threshold tax keeps the actual special-rate income | 129 |
| s.80G(4) qualifying limit | Not implemented | 10% of adjusted GTI for "with qualifying limit" donations | 0 (not in dataset) |
| s.80CCD(1B) | When 80C filled the ₹1,50,000 80CCE cap, NPS self-contribution was squeezed out of 80CCD(1) and lost | The part with no room under 80CCE is claimed under 80CCD(1B), up to ₹50,000 | 243 |

The statutory-audit corrections (s.112A(2) through s.80G(4)) were applied in one pass that
changed 208 cases in total.

**Checked against the Income Tax Department's calculator, no change needed:** the new-regime
s.87A rebate threshold is measured on income excluding special-rate gains, with marginal relief
computed the same way (56 cases). See `docs/ground_truth_validation/`.

## Scoring

- **35 scored fields (was 37).** `Tax on STCG (Other)` and `Tax on LTCG (Other)` are 0 in every
  case, so they could not distinguish between models. They remain in the output schema but are
  not scored.
- Four scored fields copy an input value verbatim (savings interest, deposit interest, EPF
  interest, TDS). Reports show accuracy with and without them.

## Evaluation harness

- **Script method:** each retry sends only the latest script and its error. A repeated script
  gets one warning, and a second repeat ends the case. The longest code block in a reply is the
  one executed. A script that exits cleanly but prints nothing gets feedback instead of a zero.
- **Tool-call method:** a reply with neither tool calls nor JSON gets up to two prompts to continue.
- **Infrastructure failures are never scored as model failures:** empty completions, provider
  errors returned inside a 200 response, timeouts and network errors are retried. A case that
  still fails is skipped and re-run, not recorded as 0.

## Known coverage gaps

Implemented and unit-tested, but not exercised by any of the 569 cases: grandfathering (every
purchase is after 2018), debentures, NSC, SCSS, Sukanya Samriddhi, voluntary and employer EPF,
multi-year 80D premiums, the super-senior slab, 80G qualifying-limit donations, short-term
loss expiry, and holding periods near the 12-month threshold.

## Release cleanup

Unreported runs, raw logs and development tooling were removed. `evaluate_llm.py` was trimmed
to the six evaluated models, and its comments were condensed with the code unchanged.
`rescore.py --dry-run` reports 0 differences on all 19 runs. A README and `requirements.txt`
were added.
