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

---

## v1.4

### v1.4.1

| Area | Change | Rule / Notes |
|---|---|---|
| LLM benchmark evaluator | Plan finalised (`tests/evaluate_llm.py`) | Feeds each generated test case to an LLM via API, scores output against `_expected` |
| Three evaluation methods | Zero-shot, Script, Tool-call | Run in priority order; each method run for all models before moving to next; CLI `--method` flag selects which to run |
| Zero-shot method | Single turn: system prompt + input → LLM responds with JSON | No retries, no tools; parse failure = 0 score; purest test of model knowledge |
| Script method | LLM writes Python script, executed in subprocess | Input via temp file; stdout = output JSON; up to `MAX_SCRIPT_RETRIES` (3) error-fix cycles; `SCRIPT_TIMEOUT` (20s); numpy/pandas available |
| Tool-call method | Multi-turn with `calculate` tool | Single tool (add/subtract/multiply/divide, N operands, left-associative); parallel calls encouraged; `MAX_TOOL_ROUNDS` (20) cap |
| System prompt | Output JSON schema only + method-specific instructions | No tax rules included — LLM must rely on training data for all tax logic (80CCE, loss set-off, new regime, HRA, 80D, etc.) |
| Prompt tuning | 3-phase: tune on weakest model → validate on mid+strong → freeze | Format adherence only (not tax-logic hints); document before/after parse-failure rates for paper methodology section |
| Scoring | 37 fields, 1 point each, ±0.01 tolerance | Combined: 80C+80CCC+80CCD(1) as one; STCG sum as one; LTCG sum as one; tax lines scored individually |
| Models (8 total) | Tier 1: qwen3-coder, gpt-oss-120b, llama-3.3-70b; Tier 2: gemma-4-31b, minimax-m2.5; Tier 3: ling-2.6-flash, nemotron-nano-9b, gpt-oss-20b | All free-tier via OpenRouter; tiered selection designed to maximise performance variation |
| Latency & token tracking | Per-case: wall-clock latency (sec), prompt/completion/total tokens | Summed across all turns for multi-turn methods; enables accuracy-vs-cost analysis across methods |
| Checkpointing | JSONL per (model, method) pair | `<model_slug>__<method>.jsonl`; each case appended immediately; re-run resumes from next unprocessed case |
| Rate limiting | Layered: baseline delay + 429 backoff + auto-slowdown + daily-limit detection | 3 retries with exponential backoff on transient errors; skipped cases retried on next run |
| Output reports | Per-model-method CSV, per-method summary CSV, cross-method pivot CSV, console summary | Pivot shows accuracy / tokens / latency per model × method; per-method summary generated independently |
| CLI interface | `--method`, `--model`, `--max-rounds`, `--max-script-retries`, `--script-timeout`, `--delay` | All optional with sensible defaults; `--method` defaults to `zero-shot` |

### v1.4.2

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/prompts/system_prompt.txt` | Implemented | Role statement (FY 2025-26), input field interpretation guide (FMV, multi-year premiums, repayment year, MF types, etc.), exact output JSON schema with all 37+ fields. No tax rules. Method-specific instructions appended programmatically. |
| `tests/tune_prompt.py` | Implemented | Interactive prompt tuning: runs 5 sample cases on 3 models (weak/mid/strong) per iteration; reports parse rate, key mismatches, failure patterns, field-by-field scores; logs each run to `tuning_log.jsonl` with prompt hash and per-tier results |
| `tests/evaluate_llm.py` | Implemented | Main benchmark script: 3 methods (zero-shot, script, tool-call), 6 models, JSONL checkpointing per (model, method), rate-limit handling, CSV reports, console summary |
| `tests/run_generated_tests.py` | Implemented | Ground-truth verification: runs calculator on all 569 generated cases, compares to `_expected` field-by-field with ±0.01 tolerance. **569/569 passed.** |
| Model list refined | 6 models (down from 8) | Tier 1: gpt-oss-120b, llama-3.3-70b; Tier 2: gemma-4-31b, nemotron-3-super-120b; Tier 3: nemotron-nano-9b, gpt-oss-20b. Deferred: qwen3-coder, minimax-m2.5, ling-2.6-flash |
| Script method sandboxing | Isolated temp directory | `tempfile.mkdtemp()` with only `input.json`; no access to project files (`tax_calculator.py`, test cases); Python standard library only |
| Cost guard | Balance-check approach | Captures initial usage at start; checks OpenRouter credits endpoint every 5 cases; halts if >$0.01 spent. Confirmed all `:free` models cost $0 per call. |
| Reasoning model handling | `get_response_text()` fallback | Prefers `content` field; falls back to `reasoning` field if content is None (Nemotron, GPT-OSS reasoning models). `extract_json()` handles fences, preamble, brace-matching. |
| Checkpoint storage | Per-case JSONL with full output | Stores: parsed JSON output, 37 field scores, 37 pct_error values, latency, tokens, conversation transcript (truncated, only for failed/low-score cases) |
| Per-field pct_error | Added to scoring and CSV | `abs(expected - actual) / max(abs(expected), 1)` per field — distinguishes rounding errors from wrong-bracket errors in analysis |
| Llama 3.3 70B | Upstream 429s from Venice provider | Retry/backoff logic handles it; model kept in list but may be unreliable during high-traffic periods |

### Placeholders (not yet implemented)
- Prompt tuning execution (phases 1–3)
- Full benchmark runs (zero-shot → script → tool-call)
- Tool-call method runtime validation (MAX_TOOL_ROUNDS sufficiency)

### v1.4.3

| Concurrency & RPM | Thread-pool concurrency + rate limiter | **RPM** (requests per minute): enforces minimum gap between API calls (e.g., RPM=18 → one call every 3.3s). **Concurrency**: max threads in flight simultaneously (e.g., 9 threads). RPM is the bottleneck — despite 9 threads ready, calls dispatch one-at-a-time through the rate limiter. Concurrency helps because while one thread waits for a slow API response (20–100s), others can fire in the next RPM slot. Example: 6 models × 3 cases = 18 tasks, RPM=18, concurrency=9 → all 18 dispatched in ~60s, responses return over the next 20–100s. Same logic in both `tune_prompt.py` (default RPM=12, concurrency=6) and `evaluate_llm.py` (default RPM=15, concurrency=5). |

### v1.4.4

| Area | Change | Rule / Notes |
|---|---|---|
| `max_tokens` unified to 16384 | All models now use `max_tokens=16384` | Previously 4096 default; Llama 70B was exhausting tokens on `<think>` chain-of-thought at 4K and never reaching JSON output. 16K headroom fixes parse failures across all reasoning models without meaningful cost increase for non-reasoning models (they stop when done). |
| Llama 70B parse fix validated | 67–70% → 100% parse rate | `input_0341` (deterministic failure at 4K) now parses at 59.5%. Cost stayed flat (~$0.0007/call). Failure was purely token budget, not model capability. |
| Qwen 3.5 9B evaluated and dropped | 33% parse at 4K, 33% at 16K, **0% at no-cap** | Model ignores `<think>` tag instruction, reasons in plaintext, never transitions to JSON. More tokens = worse results + higher cost ($0.0009 → $0.0018 → $0.0068/call). Fundamental instruction-following failure — not fixable via token limits or prompt changes. |
| Gemma 4 31B evaluated | 100% parse, 57.7% mean score | Free endpoint 429s but paid fallback works. Correct key names, no structural issues. Added to model list as Mid tier. |
| Key normalization (`_normalize_keys`) | Fixes tokenizer-mangled key names | `_KEY_LOOKUP` maps space-stripped lowercase keys to correct schema keys (e.g. `"Under HeadSalaries"` → `"Under Head Salaries"`). Fixes Nemotron 9B's 4/10 key-name errors. Applied to all `extract_json` return paths in both scripts. |
| Model list updated to 8 | Strong: gpt-oss-120b, hy3-preview; Mid: deepseek-v3, llama-70b, gemma-4-31b; Weak: gpt-oss-20b, nemotron-nano-9b, qwen-3.5-9b | Qwen included for completeness but expected to fail. Per-model RPM/concurrency config added to `evaluate_llm.py`. |
| Per-model config in `evaluate_llm.py` | `MODEL_CONFIG` dict with RPM + concurrency per model | Free models: RPM=12, concurrency=4 (conservative). Paid models: RPM=25, concurrency=8. Budget raised to $17. |
| Parallel model execution | All models run simultaneously via top-level `ThreadPoolExecutor` | Each model gets its own `RateLimiter` instance and inner case-level thread pool. Wall-clock time bounded by slowest model. Global `_rate_limiter` removed; `rate_limiter` passed as parameter through `api_call_with_retry` → runners → `evaluate_case`. `_print_lock` added; all log lines prefixed with `[model-tag]`. |
| Free→paid fallback (`evaluate_llm.py`) | `FREE_FALLBACKS` dict (gemma-4-31b-it:free → paid) | On 2nd consecutive 429, switches model in API call and creates new `RateLimiter` with paid config (25 RPM). Stored in `model_delay_state` so all subsequent cases for that model use the upgraded rate limiter. |
| Free→paid fallback (`tune_prompt.py`) | `FREE_FALLBACKS` dict with same mapping | On 2nd 429, switches model in `_create_completion`. No rate limiter upgrade (unnecessary for small tuning runs). |
| Seed-based case selection | `--seed` CLI arg (default 42), `random.Random(seed).shuffle()` | Deterministic shuffle before slicing to `--max-cases`. Run `--max-cases 10` then `--max-cases 100` with same seed: first 10 are a prefix of the 100, checkpoints carry over. |
| Per-case cost tracking | `TokenTracker.cost` accumulates `usage.cost` from OpenRouter responses | Stored in `CaseResult.cost`, checkpointed in JSONL, included in per-model CSV (`cost` column), method summary CSV (`total_cost`, `mean_cost`), console summary, and per-case progress lines. |

#### Logging additions (`evaluate_llm.py`)

| Area | Detail |
|---|---|
| `LOGS_DIR` | New path constant: `tests/evaluation_logs/` |
| `_Tee` class | Duplicates writes to both console and log file via `sys.stdout`/`sys.stderr` replacement |
| Log file naming | `run_{method}_{UTC timestamp}.log` (e.g. `run_zero-shot_20260424_120000.log`) |
| Tee setup | At start of `main()`: creates `LOGS_DIR`, opens log file, wraps both stdout and stderr with `_Tee` |
| Tee teardown | At end of `main()`: prints log path, restores original stdout/stderr, closes file |
| What's captured | All console output — per-case progress lines (`[model-tag] [n/N] ...`), 429/retry messages, per-model summaries, cost guard alerts, final method summary, total spend |

#### Fixes from benchmark runs (`evaluate_llm.py`)

| Fix | Trigger | Change |
|---|---|---|
| Free-tier fallback ordering | Run 1: Gemma 0/10 — `"limit exceeded"` in 429 message matched daily-cap check, bypassing `FREE_FALLBACKS` entirely | Moved `FREE_FALLBACKS` lookup before daily-cap raise; narrowed daily-cap check to `"daily"` only (not `"limit exceeded"`) |
| Fallback `kwargs` rebuild bug | Run 1: Paid model was never actually called — `call_kwargs = dict(kwargs)` at top of retry loop reset model to free on every iteration | Introduced `active_model` variable outside retry loop; `call_kwargs["model"]` set from `active_model` so fallback persists across iterations |
| Immediate fallback on first 429 | Run 1: Retrying the same rate-limited free endpoint is pointless | Removed `attempt >= 1` guard — fallback triggers on first 429 instead of waiting for a second failure |
| `max_tokens` bump | Run 1: Llama 70B 2/10 parse failures at 16384 tokens | 16384 → 32768 for all models; non-reasoning models stop when done so no cost increase |
| `RateLimitExhausted` exception | Run 2: Needed to distinguish rate-limit exhaustion from other failures for self-healing logic | New exception type raised when all retries exhausted due to 429s |
| Sliding window case submission | Run 2: All cases submitted upfront → queued futures all fail independently on rate limits | Cases fed incrementally in a window of `concurrency` size; allows stopping the tap on rate limits without queued futures piling up |
| Self-healing rate-limit pause | Run 2: Transient platform-wide free-tier rate limits caused cascading failures | On `RateLimitExhausted`: stop feeding new cases, drain in-flight. If any in-flight succeeds → reset and resume. If all drain with rate limits → cooldown sleep (120s), then retry remaining. After 2 cooldowns → halt model |
| **`MAX_OUTPUT_TOKENS` removed** | Models were capped at 32768 even when they could benefit from unlimited output | `MAX_OUTPUT_TOKENS = None` — `max_tokens` param is no longer sent in API calls, letting each model use its provider default. Per-model overrides possible via `MODEL_CONFIG["max_tokens"]`. **Important:** removes the safety cap on token generation; runaway reasoning models may produce very large (and costly) responses. |
| Free-model rate limits raised | hy3-preview and nemotron were under-utilised at rpm=12, concurrency=4 | hy3-preview: 12→20 RPM, 4→8 concurrency. nemotron-nano-9b: 12→20 RPM, 4→8 concurrency. Gemma unchanged (still 429-prone, relies on paid fallback). |