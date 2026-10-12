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

#### Archetype ID now carried through the dataset and evaluation results

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/generate_test_cases.py` | Generated cases now embed `_profile` (full archetype name, e.g. `P01_mid_salary_private_new_metro`) and `_archetype` (short ID, e.g. `P01`) fields | Previously the archetype was only recoverable from the filename, and only under a naming scheme (`{slug}_{idx:04d}.json`) that didn't match what `evaluate_llm.py` actually globs for (`input_*.json`) — the two had drifted apart. Filename generation fixed back to `input_{idx:04d}.json` so the generator output matches the harness's expectations; regenerated all 569 cases (569/569 pass ground-truth re-verification). |
| `tests/evaluate_llm.py` — `CaseResult` | New `archetype` field | Populated from the case's `_archetype` on a fresh run, and recovered via a `case_file → case` lookup on checkpoint resume (previously `description` was also silently dropped to `""` on resume; now restored the same way) |
| `tests/evaluate_llm.py` — results CSV | New `archetype` column | Per-model-method results CSV (`write_per_model_method_csv`) now carries the P01–P10 archetype per row, enabling per-archetype accuracy analysis without re-deriving it from parameter combinations |

#### Debt mutual fund indexation removed (Budget 2024 correctness fix)

| Area | Change | Rule / Notes |
|---|---|---|
| `tax_calculator.py` — `classify_mf_transaction()` | Debt-MF LTCG (units bought before 1 Apr 2023, held >24 months) now taxed on flat gain (`sale − cost`), not CII-indexed cost | Budget 2024 (23 Jul 2024) retroactively withdrew indexation for **all** debt-fund LTCG, including units bought before 1 Apr 2023, for any sale on/after that date. Every case in this benchmark's FY 2025-26 scope has a sale date after the cutoff, so indexation never legally applies here — the prior code was giving these cases an incorrect (indexed, lower) taxable gain. Verified against Budget 2024 Section 50AA analysis (see sources in conversation). |
| `tax_calculator.py` | Removed `CII_TABLE` and `fy_start()` | Dead code once indexation was removed — nothing else in the calculator used them |
| `calculator_tests/test18_mf_debt_pre2023.json` + `run_tests.py` | Updated to an in-scope FY 2025-26 sale date (2025-06-01, was 2024-01-01) and the correct flat-gain expected value (₹50,000, was the indexed ₹34,385.38) | The old test's sale date preceded the Budget 2024 cutoff, so its old expected value was still technically correct for that date — but out of scope for a calculator that only targets FY 2025-26 |
| `tests/generated/*.json` | Regenerated all 569 cases | 158 of 569 cases (the `non_equity_mf=debt_pre2023_*` factor levels, present across all 10 profiles) had their `LTCG (Non-Equity)` ground truth change from an indexed to a flat gain. Ground-truth re-verification: 569/569 pass. Calculator unit tests: 26/26 pass. |

#### Section 16(iii) professional tax cap corrected to ₹5,000 (primary-source verification against CBDT ITR-2 Validation Rules, AY 2026-27)

| Area | Change | Rule / Notes |
|---|---|---|
| `tax_calculator.py` | Section 16(iii) professional tax deduction cap raised from ₹2,500 to ₹5,000 | Confirmed directly from the official **CBDT e-Filing ITR-2 Validation Rules for AY 2026-27, V1.0 (26 May 2026)**, Rule 37: *"In Schedule Salary, Professional tax u/s 16(iii) will be allowed only to the extent of Rs.5000/-"*. The ₹2,500 figure (Article 276(2) of the Constitution) was the long-standing historical cap and is what every other source, including this project's own `Reference.md`, had documented — but the AY 2026-27 official validation rules supersede it for this benchmark's scope. |
| `Reference.md` | Updated Section 16(iii) limit to ₹5,000, with source citation | — |
| Dataset impact | None | The generator never feeds a `Professional Tax` value above ₹2,500 (max used: ₹2,500 across all profiles), so `min(2500, x) == min(5000, x)` for every one of the 569 cases — no case's ground truth actually changes from this fix, but it's now correct for any future case with a higher value. Verified: 569/569 ground-truth pass, 26/26 unit tests pass. |
| Cross-check method | User supplied primary sources: CBDT ITR-2 Validation Rules PDF (AY 2026-27) and the ITR-2 JSON Schema, both downloaded from incometax.gov.in | Cross-referenced against `tax_calculator.py`'s HRA (50%/40% split), entertainment allowance (₹5,000/20%-of-basic/govt-only), standard deduction (₹50,000 old / ₹75,000 new), 80D limits (₹25k/₹50k self, ₹25k/₹50k parents, ₹5k preventive checkup, ₹1L overall), 80G cash >₹2,000 rule, 80CCD(2) 10%/14% split, 80TTA/80TTB age-gating, 87A thresholds (₹12L new / ₹5L old), and STCG 111A (20%) / LTCG 112A (12.5%) rates — all confirmed correct, no further discrepancies found |

#### Explicit API request timeout (evaluation harness robustness fix)

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `get_client()` | New `API_TIMEOUT_SECS = 600` constant, passed as `timeout=` to the `OpenAI()` client | Previously no timeout was configured, so a provider that accepts a request but never responds blocks that case's concurrency slot forever — observed directly with `nvidia/nemotron-3-ultra-550b-a55b:free`, which opened a connection and then sat with zero response for 20+ minutes on a full (system prompt + taxpayer JSON) request, despite answering a trivial test prompt in ~2s via direct `curl`. 600s gives ~2x headroom over the slowest model's observed average latency (hy3-preview, 336s/case) so legitimately slow reasoning isn't cut off, while still failing well before a genuine hang. A timeout now surfaces as a normal exception, which `api_call_with_retry`'s existing `"timeout" in err_str` branch already retries/skips correctly — no other logic changes needed. |

#### Method summary CSV no longer clobbered by single-model runs

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `write_method_summary_csv()` | Reads any existing `{method}_summary.csv` into a dict keyed by model, updates only the models present in the current run, then rewrites all rows sorted by model | The function opened the file with mode `"w"` and wrote rows only for `all_model_results`, which for a `--model X` invocation contains exactly one model. Every single-model run therefore silently deleted every other model's summary row. Observed in the working tree: the file held only `nvidia/nemotron-3-ultra-550b-a55b:free` after its run, having dropped the `tencent/hy3-preview:free` row written earlier. The per-model `*_results.csv` files were never affected, so nothing was permanently lost, but the aggregate table was wrong after any single-model run. Verified with an isolated temp-dir test: a one-model write against a 9-row summary now leaves all 9 rows intact. |

#### `tests/rescore.py` — offline re-grading of checkpointed outputs against current ground truth

| Area | Change | Rule / Notes |
|---|---|---|
| New file `tests/rescore.py` | Re-scores every checkpointed case's stored `llm_output` against the current `_expected`, then rebuilds the per-model results CSVs, the per-method summary, and the cross-method pivot. Flags: `--dry-run` (report drift, write nothing), `--method`, `--update-checkpoints` | Needed because ground truth is regenerated whenever `tax_calculator.py` is corrected, while already-collected model results keep whatever score they were given at collection time. Since `save_checkpoint()` persists `llm_output` per case, re-grading needs no API calls. Reuses `score_case()`, `result_from_checkpoint_entry()`, `write_per_model_method_csv()` and `write_method_summary_csv()` rather than reimplementing scoring. Model IDs are recovered from the `model` column of the matching results CSV because `model_slug()` flattens `/` and `:` to `_` and is not reversible. |
| Cross-model comparability defect this surfaced | Seven models were scored against the pre-fix answer key and have been re-graded | Commit `f90c423` (2026-09-15) regenerated all 569 case files: 443 changed only in metadata (the `_archetype` addition), but **126 had real `_expected` value changes**, all traceable to the debt MF indexation fix (e.g. `input_0002`: `Total Taxable Income` 2,822,276.03 → 2,859,500.0, `Tax on LTCG (Non-Equity)` 0.0 → 4,375.0). The seven models whose results were committed 2026-04-24 predate that regeneration, so their accuracies were computed against superseded ground truth and were not comparable with `nvidia/nemotron-3-ultra-550b-a55b:free`, evaluated 2026-09-19 onward. Re-graded deltas: `deepseek-chat-v3-0324` 0.4757 → 0.4741 (3 cases), `gemma-4-31b-it:free` 0.4978 → 0.4941 (6), `llama-3.3-70b-instruct` 0.3714 → 0.3676 (6), `nemotron-nano-9b-v2:free` 0.3919 → 0.3886 (6), `gpt-oss-120b` 0.5362 → 0.5335 (7), `gpt-oss-20b` 0.4070 → 0.4038 (5), `hy3-preview:free` 0.5541 → 0.5530 (7). Unchanged: `nemotron-3-ultra` (already on the current key, confirming the split) and `gpt-oss-120b:free` (none of its 10 cases fall among the 126). All deltas are negative and small (0.11–0.38 pp) because each 50-case sample contains only 3–7 affected cases and only ~4 of 37 fields move within them. |
| `--update-checkpoints` rationale | Rewrites the stored `scores`/`pct_errors`/`total_score` in place, preserving `llm_output`, after copying the file to `.jsonl.bak` | Without it the stale scores resurface: `run_model()` rebuilds `prior_results` from the checkpoint's stored scores, so a later resumed run would mix pre-fix and post-fix grading within one model's results. Non-lossy because `llm_output` is retained and any score is re-derivable from it. |
| `.gitignore` | Added `.env` and `*.jsonl.bak` | `.env` holds `OPENROUTER_API_KEY` / `GEMINI_API_KEY` and must never be committed; the file previously listed only `.DS_Store`. |
| Post-fix state | Both `zero-shot_summary.csv` and `cross_method_summary.csv` now carry all 9 evaluated models on one answer key | Rebuilding from every checkpoint at once also restored the summary rows that the `"w"`-mode bug above had dropped. |

#### Local Ollama provider path (`ollama/*` model IDs)

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `get_client()` | Third provider branch: an `ollama/` prefix routes to `http://localhost:11434/v1` with a placeholder API key | Motivated by the OpenRouter free tier's `free_model_daily_requests` cap of **50/day, counted per account across all `:free` models** — not per model, so switching free models buys no extra throughput. The method comparison (zero-shot vs script vs tool-call over 569 cases) needs ~1,700 requests, which the cap makes impossible and a local model makes free. |
| New `is_local_model()` / `api_model_name()` helpers | `api_model_name()` strips the `ollama/` routing prefix so the request carries the provider's own ID (`gemma4:12b`) | Applied once, in `api_call_with_retry()`, where `active_model` is derived — the three method runners need no changes. The prefixed form stays the canonical ID everywhere else (checkpoints, results CSVs, summaries) so local and hosted runs of the same base model never collide; `model_slug()` flattens it to `ollama_gemma4_12b`. |
| `LOCAL_TIMEOUT_SECS = 1800` | Local client uses a 1800s timeout instead of `API_TIMEOUT_SECS = 600` | 600s exists to catch a hosted provider accepting a request and never responding. Locally there is no such failure mode, and a 12B on consumer hardware can legitimately exceed 600s on one case, so the tighter ceiling would abort valid work. |
| `MODEL_CONFIG["ollama/gemma4:12b"]` | `{"rpm": 600, "concurrency": 1}` | `concurrency: 1` is deliberate: local generation is memory-bandwidth-bound, so parallel requests split one bandwidth budget rather than adding throughput — unlike the hosted runs, which genuinely benefit from `concurrency: 4`. `rpm: 600` effectively disables the rate limiter. |
| `main()` — cost guard | Skipped when every model in the run is local | `CostGuard` polls OpenRouter's credits endpoint every `COST_CHECK_INTERVAL` cases. A local model cannot cost anything, so this avoided pointless network calls reporting $0. (It already degraded safely to a no-op without `OPENROUTER_API_KEY`, but the key is normally present.) |

#### `tests/check_invariants.py` — oracle-free validation of the ground truth

| Area | Change | Rule / Notes |
|---|---|---|
| New file `tests/check_invariants.py` | Asserts properties that must hold whatever the correct tax is: net-salary identity, capital-gains subtotals, GTI as the sum of its heads, deductions total, the full tax build-up chain (before-rebate → after-rebate → cess → liability → net payable), cess = 4%, 87A bounds, non-negativity, and monotonicity of tax in salary | Written because `run_generated_tests.py` is **circular** — it only checks that the stored `_expected` matches what the calculator currently outputs, so if a rule is wrong all 569 ground truths encode that error and the check still reports 569/569. These invariants need no independent implementation and immediately found two real defects (below) plus confirmed monotonicity holds across 40 cases (no slab/surcharge/marginal-relief inversions). Passing does not prove correctness; it rules out internal contradiction. |

#### Section 80A(2) fix — Chapter VI-A deductions capped at gross total income

| Area | Change | Rule / Notes |
|---|---|---|
| `tax_calculator.py` | `total_deductions = min(total_deductions, gross_total)` | Section 80A(2): the aggregate of Chapter VI-A deductions "shall not, in any case, exceed the gross total income of the assessee." Without the cap, 11 of the 569 cases produced a **negative Total Taxable Income** (worst: `input_0305`, GTI ₹73,000 against ₹275,000 of deductions → −₹202,000). A model correctly answering ₹0 was scored wrong, so the ground truth was penalising correct behaviour. All 11 were old-regime. |
| Dataset | Regenerated: 11 of 569 `_expected` blocks changed, **0 `input` blocks changed** | Verified by diffing every case against `HEAD` before accepting the regeneration. The generator has no RNG (pairwise covering arrays over fixed parameter dicts), so inputs reproduce byte-identically and all previously collected model results remain comparable. |
| All collected results | Re-graded via `tests/rescore.py --update-checkpoints`, no API calls | Deltas are small and uniformly **positive**, consistent with removing cases where models were marked wrong for answering 0: `nemotron-3-ultra` 0.6400 → 0.6404 (4 cases), `gpt-oss-120b` 0.5335 → 0.5341, `hy3-preview` 0.5530 → 0.5535, `nemotron-nano-9b` 0.3886 → 0.3892, `gpt-oss-20b` 0.4038 → 0.4043. |
| `calculator_tests/test27_80a2_deduction_cap.json` + `run_tests.py` | New regression test: GTI ₹68,000 with ₹75,000 claimed → deductions allowed ₹68,000, taxable income ₹0, tax ₹0 | Suite now 27 passed, 0 failed. Ground truth back in sync (569/569) and the invariant suite reports 0 negative-taxable-income violations (was 11). |

#### Two further ground-truth defects identified, pending external adjudication

| Area | Finding | Rule / Notes |
|---|---|---|
| GTI schema shadowing (336 of 569 cases) | The output key `"Other Interest"` is reused as a **container** for `EPF Taxable Interest`, shadowing the input's scalar `Other Interest` income. The calculator correctly includes that amount in GTI, but the schema gives a model nowhere to report it, so GTI exceeds the sum of its own displayed components | Accounts for 8.6% of `nemotron-3-ultra`'s GTI failures (21 of 245 cases where the model was low by *exactly* the unreportable amount). **Not fixed**: correcting the schema changes the task the models were given and would invalidate all 331 collected cases. Recommended for a v2 dataset; quantified here as a known limitation. |
| s.87A marginal relief (56 of 58 rebate cases) | The eligibility gate uses `total_taxable`, but the marginal-relief branch measures the excess with `normal_income - rebate_threshold`. When capital gains push total income above ₹12L while normal income stays below it, the excess computes as 0 and the full slab tax is rebated (e.g. `input_0199`: total taxable ₹17,69,500, rebate ₹59,000 granted) | In the `nemotron-3-ultra` run, **31 of 31** affected cases had the model answer rebate = 0 and be scored wrong every time. The rebate cascades into Tax After Rebate → Cess → Total Tax Liability → Net Tax Payable, so ~5 of the 14 Tax Computation fields are affected per case — plausibly several points of the 45.6% section score. **Not fixed**: the treatment of special-rate income under the new-regime 87A rebate is contested, and `calculator_tests/test14_87a_marginal_relief.json` explicitly encodes the current interpretation ("income above 12L from normal sources"), so neither the code nor the test suite is independent evidence. Requires adjudication against the ITD estimator or a practitioner. Note also that test14's description computes the rebate as 42750 while `run_tests.py` asserts 38750 — one is stale. |

#### `extract_code()` leaked the markdown fence when a response was truncated

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `extract_code()` | New branch matching an *unterminated* fence (opening ` ```python ` with no closing fence), returning the body without the fence line | The function only matched a complete fenced block. When it failed, the fallback returned `text.strip()` verbatim — fence line included — so the generated `solve.py` began with ` ```python ` and died with `SyntaxError: invalid syntax` on line 1. That masked the real cause (a truncated response) behind a syntax error, and the model was then asked to "fix the script" for a problem it had not made. Found on the first ever `script`-method case: 4 rounds, 30,096 tokens, 25.6 min, `PARSE_FAIL`, where 3 of 4 rounds failed on this bug rather than on model error (round 1 was a genuine model `TypeError`). Verified against 6 response shapes: complete fence, unterminated fence, bare code, prose-only, fence without a language tag, and preamble-plus-fence. |

#### `run_script()` appended each assistant turn twice, one copy truncated to 500 characters

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `run_script()` | The per-round append now stores `raw` in full, exactly once. The duplicate `{"role": "assistant", "content": raw}` appends in the script-error and timeout branches are removed | Each retry round added **two** assistant messages: a `raw[:500]` stub appended immediately after the response, then the full text appended again by the error branch. The stub was a fragment of the model's own script cut off mid-expression, placed directly beside a `SyntaxError: '{' was never closed` message asking it to fix that script — the stub was itself an instance of the error being reported. The duplication also charged every retry round twice for the script in prompt tokens. All three cases of the first `ctx8k` script trial failed under this bug; that run has been archived rather than reported, and `script_summary.csv` reset, because it measured the harness rather than the model. |

#### Local model rebuilt at `num_ctx 16384` for the script method

| Area | Change | Rule / Notes |
|---|---|---|
| `gemma4-12b-ctx16k` (new Ollama model), `MODEL_CONFIG` entry `ollama/gemma4-12b-ctx16k` | Same `gemma4:12b` weights at `num_ctx 16384`, `reasoning_effort: "none"`, `concurrency 1` | The script method's context needs are far higher than zero-shot's or tool-call's: a generated tax script runs 6,000–10,000 characters (~2,500 tokens), and a retry round must additionally carry the previous script in full plus the interpreter traceback. 8,192 does not fit — `input_0255` recorded 2,472 prompt + 5,720 completion = **exactly 8,192** and was truncated mid-script on its first attempt, yielding a `'{' was never closed` SyntaxError that was an artifact of the context wall rather than a model mistake. This corrects an earlier note that context never binds for this benchmark: that held for zero-shot and tool-call (peak per-round prompt ~4,500 of 8,192), not for `script`. |

#### Schema shadowing also crashes generated scripts (new evidence on a known defect)

| Area | Finding | Rule / Notes |
|---|---|---|
| `"Other Interest"` output-key reuse (see "Two further ground-truth defects" above) | Two of the three first-round script failures died on the identical line `data["Other Interest"]["EPF Taxable Interest"]` → `TypeError: 'int' object is not subscriptable` (`input_0289`, `input_0199`) | The model read the **output** schema, where `"Other Interest"` is a container holding `EPF Taxable Interest`, and inferred the **input** had the same shape. The input instead has `"Other Interest"` as a scalar with `"EPF Taxable Interest"` as a sibling key. So the defect is not confined to unreportable GTI components in zero-shot: it causes hard crashes in the script method. Still **not fixed** — a schema change invalidates the 331 collected cases — but the cost is now two failure modes across two methods, which strengthens the case for correcting it in the same pass as any s.87A fix so the models are re-run only once. |
| Underlying constraint this exposed (no code change) | The `script` method's retry loop outgrows an 8,192-token context by round 3 | Each round appends the entire previous script (~2,400 tokens) plus its error to the conversation: ~1,800 prompt + 2,400 (r1) → ~7,100 (r2) → ~9,500 (r3), against `max_rounds=20`. So the method needs a large-context model; it is not viable on a local 12B at 8k, and raising the local context far enough would exceed available RAM on a 16 GB machine. Recorded here so the `script` arm is run on a hosted large-context model rather than re-attempted locally. |
#### Script method revalidated after the dedup and context fixes — it beats zero-shot

| Area | Finding | Rule / Notes |
|---|---|---|
| `script` vs `zero-shot`, `gemma4-12b` (3 cases, `seed=42`, identical cases in both arms) | **0 parse failures** (was 3 of 3). Paired totals: zero-shot **42/111 = 37.8%**, script **52/111 = 46.8%**. Script wins on every case: `input_0289` 13→14, `input_0255` 14→17, `input_0199` 15→21. Mean 1.7 rounds, mean latency 1,160 s/case | Reverses the earlier conclusion that the script method is unusable for a local 12B. The previous 0.0% measured the duplicate-append bug and the 8,192 context ceiling, not the model. `input_0255` is the clearest case: it had died at exactly 8,192 tokens, and now completes on the **first attempt with no retry** at 46%. Per-section: Other Sources 88.9%, Salary 66.7%, Deductions 55.6%, Tax Computation 33.3%, Capital Gains 16.7%, **Aggregates 0.0%**. |
| Aggregates failures are genuine, not schema artifacts | GTI errors are large and bidirectional (`input_0289` +42,500, `input_0255` +100,000, `input_0199` −125,500), so they are not the `"Other Interest"` shadowing defect | `input_0199` is off by exactly −125,500: the model deducted the ₹1,25,000 s.112A exemption from **Gross Total Income**, where it does not belong — the exemption applies when computing tax on LTCG, not when aggregating income heads. This is a composition error of the kind the benchmark exists to measure, consistent with the Capital Gains section scoring 16.7%. |
| Caveat | 3 cases only, and `input_0199`'s Tax Computation fields are graded against the disputed s.87A rebate | Not publishable until the full 50 have run and the 87A question is adjudicated. |
| Supersedes an earlier note in this version | An earlier row (under "Schema shadowing also crashes generated scripts") concluded that the `script` method "is not viable on a local 12B at 8k, and raising the local context far enough would exceed available RAM on a 16 GB machine", and that the arm should therefore be run on a hosted large-context model | That conclusion is withdrawn. `num_ctx 16384` on `gemma4:12b` Q4 runs comfortably on the 16 GB M3: all 3 cases completed, 0 parse failures, mean prompt 7,060 tokens against the 16,384 ceiling, so the context never bound. The earlier row is left in place unedited per the changelog rule against rewriting existing entries; this row is the correction. Its arithmetic was also pessimistic because it assumed the duplicate-append behaviour, which charged each retry round for the script twice. |

#### `test14_87a_marginal_relief.json` description corrected (test assertions unchanged)

| Area | Change | Rule / Notes |
|---|---|---|
| `calculator_tests/test14_87a_marginal_relief.json` — `_description` only | Rewritten to state the correct intermediate values and to label the interpretation as disputed. No input field and no assertion in `run_tests.py` changed; the suite still reports 27 passed, 0 failed | The old description read "Slab tax on 1225000 = 67750" and derived `rebate = 67750 - 25000 = 42750`, while `run_tests.py` asserts 38750. Both description figures were wrong: the slab tax is **63750** (20000 at 5% + 40000 at 10% + 3750 at 15%) and 67750 is the total *before* rebate, i.e. 63750 + 4000 of STCG tax. The error was **self-cancelling** — `67750 - 42750 + 4000` and `67750 - 38750` both yield 29000 — which is why a wrong derivation sat beside a correct assertion undetected. The new text also records explicitly that measuring the 12L threshold against normal rather than total income is the disputed reading, and that this test encodes the calculator's own interpretation and is therefore not independent evidence for it. |

#### `run_script()` gave up when a script exited cleanly but printed nothing

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `run_script()`, `returncode == 0` branch | When `extract_json(stdout)` returns `None`, the round now appends targeted feedback and consumes a retry instead of returning immediately. Two messages: one for empty stdout (naming the likely cause — the entrypoint was defined but never called) and one for stdout that is non-empty but unparseable (quoting up to 1,000 chars of it) | The success branch trusted the exit code alone. A script that defines `calculate_tax()` with a working `print(json.dumps(res))` inside it but never calls it — no `__main__` guard, no top-level call — runs the definitions, prints nothing, and exits 0. The harness scored that `PARSE_FAIL 0/37` at `rounds=1` with **all three retries unused**, despite being recoverable by saying "your script printed nothing". Hit `input_0287` in the 50-case run: 1,802 s and a spurious zero. Forgetting the entrypoint call is a common small-model slip, so this was set to recur across the run. Verified by replaying `input_0287`'s stored response through `run_script`: rounds 1 → 2, and a corrected script parsed. The spurious `input_0287` entry was deleted from the ctx16k checkpoint so the case re-runs; the three earlier passing cases were kept, since the fix only alters the failure path. |

#### `script` arm complete at 50 cases — the `rounds=4` collapse is a harness artifact

| Area | Finding | Rule / Notes |
|---|---|---|
| `ollama/gemma4-12b-ctx16k` `script`, 50 cases, `seed=42` | **31.0% overall**, **47.0% among the 33 that completed**, 17 parse failures (34%), mean 2.5 rounds, mean latency 2,283 s/case, 1,451,936 tokens | Beats the same model's `zero-shot` 38.4% on completed cases by ~9 points, and loses to it on the raw figure because a third of the cases score 0. Both numbers must be reported: the raw 31.0% is what an unattended pipeline delivers, the 47.0% is what the method achieves when it produces an answer at all. |
| Every failure is at `rounds=4`; rounds 1–3 never fail | `rounds=1` n=15, 0 failures, 45.0%; `rounds=2` n=13, 0 failures, 48.4%; `rounds=3` n=4, 0 failures, 49.3%; `rounds=4` n=18, **17 failures**, sole survivor 48.6% | Answer quality is flat across rounds — a case that survives to round 4 scores in line with every other bucket — so the 17 zeros are not hard cases failing on merit. Retrying does not degrade the answer; something about the fourth round prevents an answer from being produced. |
| Cause: `run_script()` never trims the retry history | `messages` grows by two entries per round and is never pruned, so round 4 re-sends three superseded scripts (~3,500 tokens each) plus three tracebacks ahead of the input. Summed prompt tokens across the 18 `rounds=4` cases fall in two clusters, ~36,300 (n=12) and ~49,600 (n=5), implying a round-4 prompt of 14,000–19,000 against `num_ctx` 16,384 | In the larger cluster the round-4 prompt exceeds the context window outright, leaving no room to emit the fix it was asked for. This is the same accumulation described in the superseded row above, now measured rather than estimated. |
| Accumulated prompt size separates the outcomes perfectly | Sole survivor `input_0156` at **28,690** summed prompt tokens; all 17 failures at **36,180 or above**. A 7,490-token gap with no case in it | 18 cases, one survivor, and the survivor is the one with the most room left. Accumulated prompt size predicts the outcome with no overlap, which is the evidence that the collapse is a harness artifact and not a property of the model or the cases. |
| Completed-only per-section, comparable across arms | Other Sources 87.9%, Deductions 64.6%, Salary 50.2%, Tax Computation 36.6%, Capital Gains 15.2%, **Aggregates 0.0%** | **Zero of 66.** Across 33 cases that ran a Python program to completion and printed valid JSON, not one got Gross Total Income or Total Taxable Income right, while getting Other Sources right 87.9% of the time. A model that wrote working code to compute the components could not make them add up. The harness report's per-section figures (Salary 33.1%, Aggregates 0.0%) include the 17 zeros and are therefore **not** comparable to the `zero-shot` arm, whose failure rate is 1.9%; use the completed-only figures above for any cross-arm claim. |

#### `nemotron-3-ultra-550b` `zero-shot` at 422 of 569 cases

| Area | Finding | Rule / Notes |
|---|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free`, 422 cases, `seed=42` | **63.1% overall**, 8 parse failures (1.9%), mean 1.0 rounds, mean latency 828 s/case, 7,314,806 tokens, $0.00 | Per-section: Other Sources 89.8%, Salary 85.9%, Deductions 79.7%, Capital Gains 48.9%, Tax Computation 45.1%, **Aggregates 8.8%**. 147 cases remain; the OpenRouter free tier is 50 requests/day account-wide, so ~3 further days. |
| The composition finding now holds across model scale and across arms | A 550B model scores 85.9% on the seven Salary fields and 8.8% on the two Aggregates fields that sum them. The 12B `script` arm scores 50.2% and 0.0% on the same two sections | The failure is not arithmetic and not tax law — it is composition. Previously established from the other direction: only 9.3% of wrong GTI answers are off by exactly the unreportable `"Other Interest"` amount, so ~90% are genuine, and the `tool-call` arm showed exact arithmetic barely changed the answers. |
| Graceful quota-exhaustion path confirmed working | On hitting `free-models-per-day`, the run logged one `SKIP (RateLimitError: 429 …)`, wrote its report, and exited | Rules out quota exhaustion as the cause of the 28 Sep 00:00:09 hang, in which the process held 0 TCP connections at 0% CPU with no `SKIP` logged for ~2 hours. That remains undiagnosed; socket count, not CPU, is the signal that distinguishes the two. |

#### Empty provider responses were being scored as model failures

| Area | Change | Rule / Notes |
|---|---|---|
| `tests/evaluate_llm.py` — `EMPTY_COMPLETION_RETRIES` | Raised 2 → 4 (3 attempts → 5) | On 30 Sep the OpenRouter provider went through a bad patch: **26 empty completions (200 OK, 0 tokens) across 56 cases**, and 8 of those cases exhausted all three attempts and were recorded as `PARSE_FAIL 0/37` with `completion_tokens = 0`. Raising the limit is nearly free because an empty response is **not billed against the 50/day free-model quota** — the 56 cases cost 55 requests despite the 26 empties — so the only cost of further attempts is wall-clock time. |
| Diagnosis: the apparent accuracy drop was entirely infrastructure | Completed-only accuracy by batch: ≤422 **64.6%**, 423–472 **64.4%**, 473–528 **65.5%**. Raw accuracy for the same three: 63.1%, 63.1%, **56.1%** | The 30 Sep batch looked 7 points worse and was in fact marginally the best. All 8 of its zeros had 0 completion tokens. Distinguishing the two required splitting on `completion_tokens`: across all 528 cases, **12 of 19 zeros had zero tokens** (infrastructure) and 7 had 248–7,131 tokens (genuine truncated or malformed model output). |
| 12 zero-token cases dropped from the checkpoint to re-run | `input_0017`, `input_0029`, `input_0109`, `input_0118`, `input_0150`, `input_0206`, `input_0299`, `input_0351`, `input_0399`, `input_0413`, `input_0432`, `input_0504`. The dropped entries are preserved outside the repo rather than deleted outright | Restated figures after the drop: **516 cases, 63.8% overall, 64.7% completed-only, 7 genuine zeros (1.4%)** — replacing the contaminated "528 cases, 62.4%, 17 parse failures" in the report above. 53 cases now remain (41 never run + 12 re-runs), so two more days at 50/day. |

#### s.87A normal-income reading validated against the ITD estimator — ground truth stands

| Area | Finding | Rule / Notes |
|---|---|---|
| The disputed s.87A threshold reading (see `test14` NOTE 2, and "Two further ground-truth defects" above) | Checked against the Income Tax Department's own estimator on four generated cases. **The estimator agreed with the stored ground truth on all four.** The ₹12 lakh threshold is measured against **normal income**, not total income | Resolves the open question that gated **56 of 569 cases** (all new-regime). No re-run of collected model outputs is required: every arm's Tax Computation scores stand as recorded. This was the single largest correctness risk in the benchmark. |
| The four cases and what each isolates | `input_0170` — no capital gains at all, so the marginal-relief formula alone (total income ₹12,40,000, rebate ₹26,000, tax ₹41,600). `input_0176` — s.111A STCG, normal income ₹11,90,000 below the threshold, full ₹59,000 rebate, tax ₹10,296. `input_0186` — s.112A and non-equity LTCG only, no STCG, tax ₹1,885. `input_0172` — normal income ₹12,40,000 **above** the threshold with ₹3,29,000 of gains, relief computed as though the gains did not exist, tax ₹68,120 | The 56 affected cases fall into three shapes: 9 with no capital gains (pure marginal relief), 7 with normal income at or below ₹12 lakh where gains push the total over, and **40 with normal income already above the threshold and gains present**. The earlier three-scenario check covered only the first two groups; `input_0172` is the first test of the 40-case group, which is the largest. |
| `calculator_tests/test14_87a_marginal_relief.json` — `_description` only | NOTE 3 appended recording the resolution and superseding the DISPUTED status in NOTE 2. No input field and no assertion changed; suite still reports **27 passed, 0 failed** | NOTE 2 is left in place unedited, matching how NOTE 1 preserves the earlier wrong derivation rather than overwriting it. |
| Standing caveat on the strength of this evidence | The estimator is the department's own tool, so agreement with it is the right standard for a benchmark of Indian income tax — but it is **administrative practice, not the statute**, and this issue was contested for AY 2025-26 when the filing utility was changed mid-season to block the rebate against s.111A gains | The write-up should therefore say "validated against the ITD estimator" rather than "proven correct". The check was performed manually by a third party and is **not yet archived**: the estimator's line-by-line output for each of the four cases should be committed so the validation is auditable rather than merely reported. |

#### Correction: only 2 of the 4 estimator checks reproduce the ground truth

| Area | Correction | Rule / Notes |
|---|---|---|
| **Supersedes the row above** claiming "the estimator agreed with the stored ground truth on all four" | That was written from a second-hand report before the estimator's output was read. On inspection of the four saved PDFs, **`input_0170` and `input_0172` match every line; `input_0176` and `input_0186` do not** (estimator 51,896 vs 10,296, and 53,884 vs 1,885). The earlier row is left unedited per the changelog rule; this row is the correction | The PDFs are now archived at `docs/ground_truth_validation/` with a README working through each case line by line, so the claim is auditable rather than reported. |
| The s.87A conclusion is unaffected and still holds | `input_0172` carries **no deductions**, so nothing confounds it: normal income 12,40,000, total income 15,69,000, and the estimator granted the **26,000 rebate** — every line identical to the ground truth through to 68,120 of total tax. `input_0170` independently confirms the marginal-relief formula (66,000 slab tax, 26,000 rebate, 41,600 total) | The two cases that matched are precisely the two that test the disputed reading without deductions in the way. The 12 lakh ceiling is measured against income excluding special-rate income, and relief is computed as though the gains were absent — the shape covering 40 of the 56 affected cases. **56 answer keys stand; no re-run of collected model outputs is required.** |
| **New and unresolved: whether 80CCD(2) survives in the new regime** | `input_0176`'s income entries are correct — special-rate tax 9,900 is exactly 49,500 × 20%, and the estimator's Taxable Income of 12,89,500 equals the stored GTI to the rupee. The only divergence is that it **displays** `Deductions 50000` and then does not subtract it. That 50,000 is employer NPS under **80CCD(2)**, which s.115BAC preserves in the new regime unlike 80C and 80CCD(1B) | Most likely a data-entry mistake — the amount went into a field the new regime correctly disallows — but it is **not yet demonstrated**. Exposure is larger than the s.87A question was: **140 of the 247 new-regime cases carry a non-zero 80CCD(2), a quarter of the benchmark.** To close it, re-run `input_0176` alone with the 50,000 in the "Deductions u/s 80CCD(2) — Employers contribution towards NPS" field; expected Taxable Income 12,39,500 and total tax 10,296. |
| `input_0186` is a mis-entry and carries no information | Estimator Taxable Income 14,59,500 against a stored GTI of 13,79,500, and 11,812 of special-rate tax implies 2,19,500 of LTCG against the 1,39,500 in the input — the same 80,000 discrepancy in both | Should be redone after `input_0176` resolves, since it carries the 80CCD(2) question as well. |
| Harmless presentation difference, recorded so it is not mistaken for an error later | The estimator reported all 3,29,000 of `input_0172`'s gains under "LTCG covered u/s 112A" where `tax_calculator.py` splits 1,99,000 of s.112A from 1,30,000 of non-equity | The tax is identical either way (25,500): the shared 1,25,000 exemption is applied once and both buckets are charged at 12.5%, so 74,000 + 1,30,000 and 2,04,000 give the same result. |

#### Employer NPS contribution was deducted without ever being added to salary

| Area | Change | Rule / Notes |
|---|---|---|
| `tax_calculator.py` — `calculate()` | The employer's NPS contribution is now added to `gross_salary`, and the 80CCD(2) rate and the government imputation are computed ahead of it so an imputed contribution is taxed as well as deducted. `basic_da` stays Basic + DA only, since it is the base for the HRA exemption and the 80CCD caps, none of which count the employer's contribution | `gross_salary` summed ten named salary components and the employer's contribution is not one of them, yet 80CCD(2) then deducted it: **the same rupees were excluded from income and subtracted from it**. Under s.17(1)(viii) an employer's NPS contribution *is* salary, and 80CCD(2) relieves it — net neutral up to the cap, but it has to enter income before it can be taken out. Only the capped amount is deductible while the whole contribution is taxable, so a contribution above the cap is now correctly left partly taxed. |
| Found by the ITD estimator disagreeing on `input_0176` | Estimator Taxable Income **12,89,500** against the stored **12,39,500**. After the fix the calculator returns 12,89,500 and a Total Tax of **51,896**, the estimator's figure to the rupee. `input_0186` reconciles too: 43,485 against the estimator's 53,884, the gap being exactly the 80,000 of LTCG over-entered (80,000 × 12.5% = 10,000, plus 4% cess = 10,400) | This **supersedes the row above** which recorded the divergence as a probable data-entry mistake — page 7 of the PDF shows the 50,000 correctly on the `80CCD(2)` line with every other deduction line at 0. The hypothesis was wrong; the calculator was. |
| Ground truth regenerated and all models re-graded offline | **378 of 569 cases changed** — 367 with the full cascade through to Total Tax Liability, 163 crossing a surcharge threshold, and 11 low-salary cases where the 75,000 standard deduction had been capped by a gross salary below it. `_expected` was recomputed in place from each case's own stored `input` rather than by re-running `generate_test_cases.py`, so the inputs the models were evaluated on are byte-identical | **No inference was re-run.** `tests/rescore.py --update-checkpoints` re-graded every stored `llm_output`. Accuracy fell for every model: nemotron-3-ultra 63.81% → **60.63%** (339 cases changed), gemma4-12b `script` 46.31% → **44.35%**, gemma4-12b `zero-shot` 38.38% → **37.84%**, gpt-oss-120b 53.41% → 51.03%, tencent/hy3 55.35% → 52.43%, deepseek-v3 47.46% → 45.57%. The buggy key had been crediting models for sharing its error. Ordering is preserved and the `script` arm still beats its own `zero-shot` by 6.5 points. |
| The composition finding is strengthened, not weakened | Nemotron per-section, completed-only, before → after: Salary **85.7% → 72.0%**, Aggregates **8.5% → 4.7%**, Other Sources 89.8% → 91.7%, Deductions 79.5% → 80.9%, Capital Gains 50.4% → 52.3%, Tax Computation 44.8% → 46.6% | Salary fell 14 points because the models do not add the employer's contribution to salary either and were previously credited for sharing the error. The gap the benchmark exists to measure **widened**: 72.0% on the seven salary fields against 4.7% on the two that sum them. Checked separately that the bug was not itself producing the Aggregates result — of 329 affected completed cases only **5 (2%)** had a model answer differing from the key by exactly the 80CCD(2) amount, so the models are wrong in their own varied ways rather than systematically offset. |
| `calculator_tests/test28_80ccd2_employer_nps_in_salary.json` (new) + `run_tests.py` | Asserts Gross Salary 13,50,000, Net Salary 12,75,000, GTI 12,90,000, 80CCD(2) 50,000 and Total Taxable Income 12,40,000 — the last being the figure the taxpayer reaches with no NPS arrangement at all, which is the point of the deduction. Suite now **28 passed, 0 failed** | The bug survived all 27 earlier tests because only `test7_s16ii_govt` involved a government employer and it asserted nothing beyond `Section 16(ii)`. The error lived in the interaction between salary construction and a deduction, which no single test spanned — an instance of the oracle problem this benchmark exists to study. A property test ("taxable income must not fall when an employer contribution is added") would have caught it immediately. |
| Invariant checks re-run against the regenerated ground truth | 336 of 569 cases violate "Gross Total Income = sum of all heads", and **all 336 are explained exactly by the unreportable input `Other Interest`** — 0 unexplained. Monotonicity: 0 violations over 40 cases | Confirms the regeneration introduced nothing: the remaining violations are entirely the pre-existing `"Other Interest"` schema-shadowing defect recorded above, which is still unfixed. |

#### Benchmark validity: two defects that made the ground truth undeliverable from the input

Both were found by asking why `gross_total_income` was wrong in **every single
one** of nemotron's 36 `script` cases. Neither is a tax error — the statute was
applied correctly in both — and that is what made them survive 28 tests and four
ITD-estimator checks. They are defects in what the benchmark *asks*.

| Change | Detail | Consequence |
|---|---|---|
| **Removed the 14% employer-NPS imputation for government employees** (`tax_calculator.py`) | The contribution was raised to `max(declared, 0.14 × (Basic+DA))`. Government employers really do contribute 14% compulsorily, so the arithmetic was right — but the amount appears nowhere in the input JSON and the rule nowhere in `system_prompt.txt`, so the answer key depended on a figure no model could derive. It applied to **all 212 government cases**: median 90,000 of salary invented from nothing, maximum 272,000, and **48 cases declared exactly 0** | The declared figure is now taken at face value. A benchmark may only ask what its inputs support. |
| Why it hid for 212 cases | The imputation **cancelled out of Total Taxable Income** — the 80CCD(2) deduction equalled the imputed amount exactly in all 212 cases — so the entire tax chain stayed correct while Gross Salary, Net Salary, Gross Total Income, Total Deductions and 80CCD(2) were all wrong. Every test that checked a *tax* figure passed | Found only via the fingerprint: `input_0355` and `input_0381` both had **correct Total Taxable Income with GTI wrong by exactly −70,000**. A right answer sitting on top of a wrong one. |
| **`Other Interest` is now a reportable amount, `EPF Taxable Interest` its sibling** (`tax_calculator.py`, `tests/prompts/system_prompt.txt`) | The output schema nested `EPF Taxable Interest` inside a container called `Other Interest`, while the input used `Other Interest` as a separate flat number. The same key meant a container on the way out and an amount on the way in. The input's amount entered GTI (correctly — it is income) with **nowhere to be reported** | The invariant "GTI = sum of the reported heads" now holds: **0 violations in 569 cases, previously 336.** `input_0160`'s ₹3,000 is finally visible in the output it belongs to. |
| The collision was costing real accuracy, but only where code is executed | Models writing Python inferred the input's shape from the output schema — the only template the prompt offered — and read `data["Other Interest"]["EPF Taxable Interest"]`, raising `TypeError` on an int. **Both** retry transcripts in the project do exactly this. Measured on the field itself: gemma `script` **63.3%** against **100.0%** for the same model in `zero-shot`, a 37-point collapse from switching to code generation, with 6 of 49 cases provably conflating the two meanings | Verified harmless in `zero-shot` across all nine arms: **0 conflations, 0 shape errors**, nemotron 508/508. The defect is a hazard of making a model infer input structure, not of the output schema as a specification. |
| **Added an explicit input schema to the prompt**, which never had one | The prompt documented *field semantics* but never the input's *structure*, so a script-writing model had to guess it. The new section states the shape of all 33 top-level keys and says in terms that `Other Interest` is not a container, plus: "Use the values exactly as given. Do not substitute a statutory default for a declared figure, even when the declared figure is 0" | Removes the guesswork that caused the crash class, and forecloses the imputation misreading at the same time. |
| **Zero-shot runs were preserved rather than discarded** (`LEGACY_FIELD_PATHS` in `tests/evaluate_llm.py`) | Flattening the schema moved `epf_taxable_interest`'s path, which would have made all **816** stored zero-shot answers unscorable on that field and forced a re-run of roughly two weeks of free quota. The scorer now reads a field at its former location when the current path is absent **in the answer only**; `expected` is regenerated and always uses the current path, so this never changes what counts as correct | Verified by re-grading: nemotron zero-shot `epf_taxable_interest` **508/511 (99.4%)**, gemma `script` **63.3%** — identical to the figures measured before the change. `Other Interest` is reportable but deliberately **unscored**, keeping the count at 37 so no old answer is marked wrong for a field it was never asked to produce. |
| Ground truth regenerated and all models re-graded offline | All 569 cases changed shape; the five NPS fields moved on exactly 212. `_expected` recomputed in place from each case's own stored `input`, so the inputs are byte-identical and **no inference was re-run** | Every model gained and none lost, ordering unchanged: nemotron zero-shot **60.63% → 62.52%** (190 cases changed), hy3 52.43% → **54.38%**, gpt-oss-120b 51.03% → **52.54%**, gemma-4-31b 49.19% → **50.70%**, deepseek 45.57% → **47.19%**, gpt-oss-20b 38.22% → **39.57%**, gemma4-12b zero-shot 37.84% → **38.81%**, llama-3.3-70b 36.49% → **37.68%**, nemotron-nano 36.86% → **37.30%**. The defect had been understating every model by 1–2 points. |
| What the NPS fix did **not** fix | Field-level recovery was far narrower than the case count suggests: `80ccd_2` flipped on all 190 affected nemotron cases, but `gross_salary` on only 42 and `gross_total_income` on **9** — on the rest a second, independent error sits underneath | So Aggregates is **not** rescued (5.6% → unchanged in substance) and remains genuinely hard rather than mis-specified. An earlier note in this session estimated the defect at ~5% of every model's score; the measured cost was 1–2 points. |
| `test29_other_interest_reportable.json`, `test30_no_govt_nps_imputation.json` (new) + `run_tests.py` | Test 29 asserts the flat shape and, as a lambda, the invariant itself — that the Other Sources leaves sum to GTI. Test 30 asserts Gross Salary 6,00,000 and 80CCD(2) 0 for a government employee declaring 0, where the old code would have added 84,000 and deducted it again. Suite now **30 passed, 0 failed** | Test 30 is the property test whose absence let the imputation survive: no earlier test asserted a *salary* figure for a government employee. |
| Script-arm checkpoints archived, not deleted | `tests/evaluation_checkpoints/v1_preschemafix/` holds gemma `script` (50 cases, 45.73%) and nemotron `script` (36 cases, 61.19%) with a README explaining why they are not comparable | The prompt changed, so the question changed. These two arms are being re-collected; the nine zero-shot arms are not, and that asymmetry is the whole point of the legacy reader. |

#### s.112A grandfathering: a provision applied to the wrong shares, and never actually tested

Found by solving `input_0141` and then `input_0549` by hand against the statute
rather than against the engine — the only way to break the circularity of
validating a ground truth with the code that produced it.

| Change | Detail | Consequence |
|---|---|---|
| **Grandfathering now requires acquisition before 1 Feb 2018** (`tax_calculator.py`) | `effective_cost_per_share = max(cost_price, fmv)` ran for **every** long-term holding, with no date test. s.55(2)(ac) restricts the step-up to equity shares acquired before the cutoff. Shares bought in 2024 were therefore given a cost basis lifted to their "FMV as of 31 Jan 2018" — a figure with no meaning for a share that did not exist in the holder's hands in 2018 | **166 transactions across 166 cases (29% of the benchmark)** had an inflated cost basis, understating LTCG by **₹1,32,80,000** in total. `input_0549`: a share bought 2024-04-01 stepped from ₹100 to ₹180 per share. |
| **The step-up is now capped at the sale consideration** | The rule is cost = HIGHER of actual cost and the LOWER of FMV and sale consideration. The inner `min()` was missing, so an FMV above the sale price would manufacture a loss from a break-even sale | Latent, not observed: **0 of 777** transactions have FMV above sale price. Fixed because the generator may eventually produce one. `test3d` now guards it. |
| Why 28 calculator tests and four ITD-estimator checks all passed over it | **The one test covering grandfathering asserted the bug.** `test3b_ltcg_grandfathering.json` used a purchase date of 2020-01-01 — six years inside the cutoff — and its own `_description` stated the wrong rule as if it were the law: "effective_cost = max(100, 200)=200" | The test did not merely fail to catch the defect; it documented it as correct. Repaired to 2017-06-01, which makes it genuinely eligible and leaves the expected 950 unchanged. |
| Two complementary errors that cancelled into a plausible result | The generator's `ltcg_fmv_benefit` variant sets `"FMV as of 31 Jan 2018": 180` with `"Purchase Date": "2024-04-01"`, so it was never eligible. The calculator's missing date test is the only reason the variant appeared to do anything at all — FMV 180 *did* change the answer, the variant *did* differ from its siblings, and nothing failed | A textbook instance of the oracle problem this benchmark exists to study, found in its own harness: a scenario that looked like it validated a rule while validating nothing. |
| `test3c_ltcg_no_grandfathering_post_2018.json`, `test3d_ltcg_grandfather_clamped_at_sale.json` (new), `test3b` repaired | 3c asserts 1,950 for an identical trade bought in 2020 (actual cost used, FMV ignored); before the fix it returned 950. 3d asserts 0 where FMV 500 exceeds a 300 sale price. Suite now **32 passed, 0 failed** | Grandfathering now has eligible, ineligible and clamped coverage, which it has never had. |
| Ground truth regenerated and all models re-graded offline | **143 of 569 cases moved**: LTCG (112A), GTI and Total Taxable Income on all 143, the tax chain on 140, surcharge on 41. `_expected` recomputed from each case's own stored `input`, so **no inference was re-run** | Score effect is near zero and not uniformly positive: nemotron zero-shot 62.52% → **62.77%**, nemotron `script` 63.14% → **63.47%**, gemma-4-31b and hy3 unchanged, while deepseek 47.19% → 47.08%, llama-3.3-70b 37.68% → 37.51%, nemotron-nano 37.30% → 37.19%, gpt-oss-120b 52.54% → 52.49%, gpt-oss-20b 39.57% → 39.51%, gemma4-12b 38.81% → 38.76%. |
| An earlier reading of this, corrected | It was initially framed as "our key was wrong, so models were being marked wrong for being right". The re-grade refutes that: **four of seven arms score slightly lower** after the correction. The models were not getting these cases right either — correcting the key moved the target, and they were missing it in their own ways | LTCG (112A) is wrong in **305 of 351** nemotron zero-shot cases where it is non-zero (87%), and the stale ₹1,00,000 exemption explains only 55 of those. The remaining failures are genuine model difficulty, not a ground-truth artifact. |
| Invariant re-checked after regeneration | "GTI = sum of the reported heads": **0 violations in 569** | Unchanged by this fix, as expected — it touches the value of LTCG, not where income is reported. |

#### Deferred to v2 (input-level changes — each invalidates every collected model output)

Recorded here so the reasoning is not lost. Both require re-running the arms
they affect, because they change what the model is shown rather than what the
answer key says. Collected runs stand at **1,015** across 11 model/method
combinations, so neither is worth doing piecemeal; they should land together.

| Item | Why | Cost |
|---|---|---|
| **Give s.112A grandfathering real coverage** — set some `ltcg_fmv_benefit` purchase dates to e.g. `2017-06-01` in `generate_test_cases.py` | After the fix above, **no stock transaction in the dataset is eligible**: the earliest purchase date anywhere is 2024-04-01, so the FMV field is now **dead** — carried in all 777 transactions, documented in the system prompt, and never load-bearing. The provision the field exists for is untested by the benchmark, and `CHANGELOG.md` v1.0 claims "LTCG grandfathering (FMV 31 Jan 2018)" as implemented, which overstates it on both counts. **This note supersedes that claim**; per the project rule the earlier entry is left unedited | Changes inputs → re-run every arm |
| **Rename the input's `Other Interest`** so it no longer collides with the output key | The output nesting was fixed this version and the input schema documented, which stops models crashing on `data["Other Interest"][...]`. The underlying name collision remains: one key still means a flat amount in the input and a reported leaf in the output | Changes inputs → re-run every arm |
| Known limitation to state in the write-up either way | Grandfathering is implemented and unit-tested but **not exercised by any of the 569 cases**. Claiming the benchmark covers it would be false | — |

#### Statutory audit: six further defects in the tax engine

The grandfathering bug prompted a rule-by-rule audit of `tax_calculator.py`
against the Act rather than against its own tests. Six more defects, all in the
answer key only — `_expected` regenerated from each case's stored `input`, all
1,015 collected runs re-graded by `tests/rescore.py`, **no inference re-run**.

| # | Defect | Exposure | Fix |
|---|---|---|---|
| **A** | **The 1,25,000 s.112A relief was spilled onto non-equity LTCG.** s.112A(2) attaches it to "such long-term capital gains" — the s.112A(1) ones, equity with STT paid. Bonds, debentures, G-Secs and debt funds fall under s.112, which has no equivalent allowance | **94 of 569 cases** undertaxed; **44** paid nothing at all on non-equity LTCG. ₹5,36,625 of tax before cess | The remainder no longer carries over; non-equity LTCG is charged at a flat 12.5% |
| **B** | **The old regime's basic exemption was 2,50,000 at every age.** It is age-dependent: 3,00,000 at 60-79, 5,00,000 at 80+, and the 5% band disappears entirely for a super senior | **48 cases** (all exactly age 72) overtaxed by ₹2,500 each. No 80+ case exists, so that path had no coverage at all | `old_regime_slabs_for_age()` selects one of three tables |
| **C** | **No 15% surcharge ceiling on special-rate income.** Surcharge on s.111A/112A/112 income is capped at 15% however high total income goes; the headline 25%/37% rate was applied to the whole liability | **48 cases** above ₹2 crore holding capital gains | `_surcharge_amount()` charges the normal and special components at different rates |
| **D** | **Chapter VI-A deductions were set against special-rate gains.** s.112A(6) and s.111A(2) allow them from GTI "as reduced by" those gains; the cap was against unreduced `gross_total` | **25 cases**, ₹16,16,500 sheltered. Tax barely moves — the gains are charged from their own gross amounts and slab income was already clamped at zero — but **reported Total Deductions and Total Taxable Income were both wrong, and both are scored fields** | Ceiling is now `gross_total - special_gains` |
| **E** | **Surcharge marginal relief compared against pure-slab tax at the boundary.** `compute_slab_tax(boundary)` treats every rupee of the threshold as slab income, which overstates the comparator whenever capital gains are present (slab reaches 30% against 12.5% on LTCG) and so understates relief | **129 of the 163 surcharge cases** | The comparator now holds income COMPOSITION fixed: special-rate income stays at its actual amount and only the slab part is reduced to land on the boundary, with the lower band's rate applied at the boundary itself |
| **F** | **No s.80G(4) qualifying limit.** The "with qualifying limit" categories are deductible only up to 10% of adjusted GTI | **0 cases** — latent. The generator emits only PM Cares Fund (353, 100% without limit) and the PM's Drought Relief Fund (216, 50% without limit) | Implemented with both limited-category sets empty, so adding such a scheme cannot silently over-deduct |

| Follow-on | Detail |
|---|---|
| `test22` corrected | It expected **21,875** — (2,00,000 − 25,000) at 12.5% — and was titled *"G-Secs LTCG + shared 1.25L exemption"*, so both the assertion and the name presented defect A as the rule. Now expects **25,000** and is retitled to state that the relief is s.112A-only. |
| **Third instance of the same meta-failure** | `test3b` asserted the grandfathering bug and spelled the wrong formula in its description; `test22` asserted the spill and named it a feature; `test7` was the only government-employer test and asserted nothing beyond `Section 16(ii)`, which is how the employer-NPS defect survived. The tests were written by reading the implementation, so they verified self-consistency rather than correctness — the oracle problem this benchmark studies, in its own harness. Hand-computing four cases against the statute found seven defects that 32 passing tests had not. |
| `test31`, `test32` (new) | Senior (age 65, slab tax 20,000 against the old 22,500) and super senior (age 82, slab tax 10,000). Suite now **34 passed, 0 failed**. |
| Ground truth regenerated | **208 of 569 cases moved.** Net tax payable, cess and total liability on 183; tax before/after rebate on 135; tax on non-equity LTCG on 94; surcharge on 82; slab tax on 48; Total Taxable Income and Total Deductions on 30. |
| Score effect — **mostly downward, which is the expected direction** | nemotron zero-shot 62.77% → **62.64%**, gemma-4-31b 50.70% → **50.49%**, llama-3.3-70b 37.51% → **37.24%**, gpt-oss-120b 52.49% → **52.27%**, gemma4-12b zero-shot 38.76% → **38.54%**, hy3 54.22% → **54.22%**, gpt-oss-20b 39.51% → **39.35%**, nemotron-nano 37.08% → **37.08%**, deepseek 47.08% → **47.14%**, nemotron `script` 63.47% → **63.72%**. Four of the six defects *undertaxed*, so the corrected key demands larger numbers and the models were sharing the engine's leniency. |
| Invariant re-checked | "GTI = sum of the reported heads": **0 violations in 569** |
| Verified correct, no change needed | New and old slab rates; 87A thresholds and the new-regime marginal relief (validated against the ITD estimator); standard deductions; LTCG 12.5%, STCG 111A 20%, cess 4%; surcharge bands including the new-regime 25% cap; MF classification (equity 12-month, debt s.50AA, ELSS lock-in); loss set-off asymmetry and the 8-year window (`current_ay_start` is mislabelled as an AY but the arithmetic yields FY ≥ 2017, which `test20` confirms); HRA three-condition minimum; LTA; s.16(ia)/(ii)/(iii); 80CCE ₹1.5L with proportional scaling; 80CCD(1)/(1B); 80TTA savings-only and 80TTB; the new regime disallowing everything but 80CCD(2); s.80A(2). |

#### Metric validity: two degenerate scored fields removed, and the score decomposed

| Change | Detail | Consequence |
|---|---|---|
| **`tax_stcg_other` and `tax_ltcg_other` dropped from scoring (37 → 35 fields)** | Both were **0 in all 569 cases**, so neither could discriminate between models: emitting a constant 0 scored 100% while reasoning about them was punished. STCG on non-equity assets is charged at slab rates and folded into "Tax at Slab Rates" — a convention `system_prompt.txt` never stated — so **26% to 86% of each model's answers were marked wrong for reporting the attributable tax instead**, defensibly the more informative answer (gemma-4-31b 86%, gpt-oss-20b 79%, hy3 75%, nemotron 26%) | Documenting the convention would only have converted a trap into free marks, since a field constant across the dataset carries no signal either way. Both remain in the required output schema; they are simply not scored. |
| Hardcoded `/ 37` denominators replaced | `total_pct` and the per-case log line now derive the count from `len(scores)` | A future field change cannot silently mis-scale every reported accuracy. |
| **All scores fall by roughly 4 points**, which is the inflation those two fields were supplying | 35-field figures: nemotron `script` **62.34%**, nemotron zero-shot **61.37%**, hy3 **53.26%**, gpt-oss-120b **49.94%**, gemma-4-31b **49.94%**, deepseek **45.77%**, gpt-oss-20b **37.37%**, gemma4-12b zero-shot **36.69%**, llama-3.3-70b **35.43%**, nemotron-nano **35.14%** | Models were being credited for two fields that required no tax reasoning at all. |
| **Report now decomposes the score into derived and copied fields** | Four scored fields are the input value verbatim in all 569 cases (`savings_bank_interest`, `deposit_interest`, `epf_taxable_interest`, `tds`) — transcription, not tax computation. Reported separately rather than dropped: losing them is a real mistake, just not a tax mistake | The gap is large and uniform, and the derived figure discriminates better (spread 27.2–57.7 against 35.1–62.3 overall): nemotron `script` 62.3% → **57.7% derived** / 98.5% copied; nemotron zero-shot 61.4% → **57.4%** / 92.5%; hy3 53.3% → **48.6%** / 89.5%; gpt-oss-120b 49.9% → **43.9%** / 97.0%; gemma-4-31b 49.9% → **44.3%** / 93.5%; deepseek 45.8% → **39.5%** / 94.0%; gpt-oss-20b 37.4% → **30.1%** / 94.0%; gemma4-12b 36.7% → **28.6%** / 99.5%; llama 35.4% → **29.4%** / 82.5%; nemotron-nano 35.1% → **27.2%** / 97.0%. gemma4-12b is the extreme: **99.5% copying against 28.6% computing**. |

#### Coverage audit: rules the engine implements, unit-tests, and the dataset never exercises

Twelve input fields never vary across the 569 cases. The s.112A grandfathering
gap was not an isolated oversight but one instance of this, so the whole input
space was swept. **None of these is a bug in the engine** — each rule is
implemented and has a passing unit test. They are gaps in what the benchmark
*asks*, and claiming coverage of them would be false.

| Rule / dimension | Cases exercising it | Note |
|---|---|---|
| s.112A grandfathering (FMV 31-Jan-2018) | **0** | No stock acquired before the cutoff; earliest purchase date anywhere is 2024-04-01 |
| Debentures | **0** | `Sale`, `Purchase` and holding all constant 0, yet `STCG (Other).Debentures` and `LTCG (Non-Equity).Debentures` are reported output fields. Covered by `test24` only |
| NSC | **0** | Three of the 80C instruments are never used; only PPF (516), ELSS (516) and EPF-deducted (152) appear |
| SCSS | **0** | |
| Sukanya Samriddhi Yojana | **0** | |
| Voluntary EPF (VPF) | **0** | `EPF/Employee Contribution/Voluntary` constant 0 |
| EPF employer contribution | **0** | constant 0 |
| s.80D(4A) multi-year premium spreading | **0** | `Health Insurance[].Number of Years Paid` is always 1, so the division by years never changes anything. `test13` covers it |
| Super senior (80+) basic exemption | **0** | Every old-regime senior case is exactly age 72. `test32` now covers it |
| s.80G(4) qualifying-limit categories | **0** | Only PM Cares (353) and PM's Drought Relief (216), both "without limit" |
| STCL 8-year expiry | **0** | `Short Term Capital Loss[].Financial Year` is always `2023-24`. LTCL expiry **is** exercised — 102 cases carry `2015-16`, which is out of window |
| Stock sale date variation | **0** | `Sale Date` constant `2025-10-15`; only the purchase date moves |

| Latent defect found, never triggered | Detail |
|---|---|
| `compute_80d` credits every preventive-health-checkup to the **self** bucket regardless of beneficiary | s.80D counts a parents' checkup against the parents' limit. All 62 checkup entries in the dataset are `self`, so the misallocation never changes an answer. Left unfixed and recorded; fixing it blind with no case to verify against risks introducing an error rather than removing one. |

| Verified correct in this sweep, no change | `compute_80d` limits (25k/50k, senior detection, cash exclusion, group-policy exclusion, ₹5,000 checkup cap applied within the overall limit); MF classification across all six fund types (equity 12-month, ELSS lock-in, debt s.50AA, gold-ETF 12-month, gold-MF and international 24-month); EPF employee contribution feeding 80C; bonds/debentures/G-Secs 12-month threshold (correct for **listed** securities — the input never says listed or unlisted, so that assumption is forced and should be stated in the prompt). |

**Everything in the coverage table is a `generate_test_cases.py` change**, so it
alters the inputs and invalidates all collected runs. It belongs with the two
items already deferred to v2 and should land in one pass.

#### Nemotron script arm complete at 50/50 under the final prompt and answer key

The arm resumed from the 33-case checkpoint (the Oct 4 run stopped on a 429
daily-quota exhaustion at `input_0363`, which correctly left no checkpoint
record and so re-entered the queue). `system_prompt.txt` was last modified
2026-10-02, before that run began, so all 50 cases are prompt-matched; the
scoring and ground-truth changes since are retroactive and were applied by
re-grade.

| | |
|---|---|
| Overall accuracy | **60.7%** (50 cases, 35 fields) |
| Failed to parse | 0 |
| Mean rounds | 1.2 |
| Retried at all | 7 of 50 |
| Mean latency | 369.0 s/case |
| Mean tokens | 24,478 (4,601 prompt + 19,877 completion) |
| Total tokens | 1,223,918 |
| Cost | $0.00 (free tier) |

Per-section, and the derived/copied split:

| Section | Accuracy |
|---|---|
| Other Sources (3 fields) | 100.0% |
| Deductions (9 fields) | 82.2% |
| Salary (7 fields) | 75.1% |
| Capital Gains (2 fields) | 43.0% |
| Tax Computation (12 fields) | 38.3% |
| Aggregates (2 fields) | **6.0%** |
| Derived (31 fields, computed) | 55.8% |
| Copied (4 fields, from input) | 98.5% |

**The 6.0% on Aggregates is real, not a scoring defect.** Diagnosed after the
run: `gross_salary` is wrong in 34 of 50 cases and in **all 34 the error is
exactly the Tier-1 employer NPS contribution** — the v1.4.4 ground-truth
correction (employer NPS is taxable salary, s.17(1)(viii)) reproduced on this
arm. `TOLERANCE = 0.01`, so Gross Total Income and Total Taxable Income are
accumulators that inherit that single omission and fail. Median GTI error is
only 1.92% and 35 of 47 wrong values sit within 5%. The ground-truth invariant
`GTI = sum of heads` holds in **0 violations of 50**, confirming the answer key
is self-consistent.

Salary scoring 75.1% while Aggregates scores 6.0% — one wrong field out of
seven versus one wrong accumulator out of two — is the dataset's clearest
argument for per-field scoring over a single bottom-line number.

Retry causes across all 50 are genuine Python faults, never format
negotiation, confirming the code-fence fix holds: `NameError` 3,
`IndentationError` 2, `SyntaxError` 1, `ValueError` 1. All 7 transcripts
stored, confirming the two-gate fix. The worst case, `input_0076`, spent 3
rounds and 57,775 tokens on two indentation faults to reach 49%.

Accuracy by archetype (n is small per cell; reported for shape, not as a
result): P06 94.3% (n=1), P01 74.3% (n=2), P03 74.3% (n=3), P07 70.0% (n=4),
P04 63.3% (n=7), P09 62.9% (n=2), P08 56.2% (n=3), P05 54.8% (n=6), P10 54.8%
(n=6), P02 51.4% (n=5). By regime: new 63.3% (n=14), old 60.5% (n=25) over the
first 39 cases. **The draft's P06 archetype claim rests on a single case and
must either be dropped or restated as anecdote.**

Deferred to v2: the 0.01 tolerance makes every accumulator all-or-nothing. A
tolerance-sensitivity check (exact / ₹1 / 0.5% / 1%) would show how much of the
Aggregates and Tax Computation collapse is near-miss arithmetic rather than
misapplied statute. That is a rescore, not a re-run, so it is free.

#### Two script-harness defects found while running the gemma script arm

Both were found by reading the stored transcript of a case that scored 0, and
both are artefacts of the harness rather than anything the model got wrong.

**1. The retry loop is a fixed point at temperature 0.** The retry-history trim
sends only `[system, user, last script, last error]`, which makes a repair
round a deterministic function of its input. So once a repair fails, the next
round receives byte-identical input and returns a byte-identical script,
forever. gemma's `input_0255` regenerated the same 7,843-char script five times
(rounds 3-7, identical sha256), spending ~45,000 tokens and ~75 minutes on
rounds that could not possibly have succeeded.

The trim is not the mistake -- it lifted the nemotron script arm 31.0% ->
46.3% and stays. The fix hashes every script tried and, on a repeat, injects
one escalated message that quotes the error and forbids a verbatim repeat.
That breaks the determinism through the *context* rather than by raising
temperature, so temperature stays 0 and the arm remains reproducible. A second
repeat means the model is genuinely stuck and the remaining retries are
forfeit. A set of hashes rather than just the previous script, so a two-round
cycle is caught as well as a stuck repeat.

Measured on `input_0255`, same model, same case:

| | before | after |
|---|---|---|
| rounds | 7 | **4** |
| latency | 6,553 s | **2,146 s** |
| tokens | 64,047 | **37,300** |
| score | 0/35 | 0/35 |

The score is unchanged by design: an identical script reproduces an identical
error, so no round this removes could ever have succeeded. gemma repeated
itself even after the escalation, so 0/35 is the honest outcome -- it now costs
36 minutes to establish instead of 109.

**2. `extract_code` took the first fenced block, not the longest.** A model
that opens with a short illustrative snippet before the real script had the
snippet executed. nemotron's `input_0411` emitted a 358-char stub followed by
the real 13,499-char script, and the stub was what ran. That case recovered at
rounds=2 and scored 21/35, so the completed arm's **accuracy is unaffected**,
but one round was spent on an extraction artefact and its rounds/token figures
are correspondingly inflated. Now takes `max(blocks, key=len)`.

Checked and deliberately not changed: `run_tool_call` sends full history with
no trim, so it cannot form a fixed point; and `extract_code`'s prose fallback
(7 unfenced assistant messages across the stored transcripts) is recoverable
with no case showing it mis-fires, so it is recorded rather than fixed blind --
the same reasoning as the `compute_80d` checkup bucket.

Worth stating in the paper as a finding, not just a bug: **in a script-repair
loop, trimming the context for room and fixing temperature for reproducibility
combine to make the loop deterministic, so a model that fails a repair cannot
escape it.** Any agentic benchmark with a bounded retry budget and a trimmed
transcript has this failure mode.

#### Audit of rescore.py and generate_test_cases.py (the two unaudited files)

**`rescore.py` is sound, and a dry run gives the strongest whole-dataset
consistency check available:** 13 model/method arms, 986 stored entries,
`delta +0.0000` on every arm and `0` cases differing. Every stored score in
every checkpoint reproduces exactly from the current ground truth, so the
regenerate-and-rescore pass over 569 cases left nothing stale and no arm is
graded against an old answer key. Stored field counts are uniform at `{35: 986}`,
which also makes `rescore.py`'s pooled `score/fields` figure arithmetically
identical to the per-case mean the harness reports -- the two can never
disagree.

Two latent notes, neither worth changing now. `CHECKPOINT_DIR.glob` rather than
`rglob` is the only thing keeping `v1_preschemafix/` out of the leaderboard,
which is load-bearing and undocumented. And `all_model_results[model]` is keyed
by resolved model ID, so two slugs resolving to one ID would silently overwrite
each other -- unreachable today, but `resolve_model_id`'s fallback makes it
possible.

**`generate_test_cases.py`: the coverage gap is in the factor *definitions*,
not in the profile wiring.** Every one of the 19 parameters is varied by at
least one of the 10 profiles and every factor value is reachable -- 0 unreachable
factors, 0 pinned parameters. So the uncovered rules cannot be fixed by adding
parameters to a profile's `vary` list; they need new factor values that set the
relevant leaf to something other than its default.

Measured directly from the 569 generated cases, the genuinely constant scalar
input leaves are:

| Input leaf | Constant value | Consequence |
|---|---|---|
| `Debentures/{duration,purchase,sale}` | 0 | provision never exercised |
| `EPF/Employer Contribution` | 0 | |
| `EPF/Employee Contribution/Voluntary` | 0 | VPF never exercised |
| `NSC`, `SCSS`, `Sukanya Samriddhi Yojana` | 0 | 3 of the 80C instruments |
| `Health Insurance[]/Number of Years Paid` | 1 | s.80D(4A) spreading never fires |
| `Short Term Capital Loss[]/Financial Year` | `2023-24` | STCL 8-year expiry untestable |
| `Stock Sale Transactions[]/Quantity` | 1000 | |
| `Stock Sale Transactions[]/Sale Date` | `2025-10-15` | see holding period below |

**s.55(2)(ac) grandfathering is confirmed unexercised.** Purchase dates take
exactly two values across all 569 cases -- `2024-04-01` (394 transactions) and
`2025-04-01` (383) -- so 0 transactions fall before 01-Feb-2018, and the
grandfathering branch is unreachable on this dataset. It cannot have altered
any stored answer.

CORRECTION to an earlier statement in this entry: the FMV field is **not**
unpopulated. The key is `FMV as of 31 Jan 2018` and it is present in all 777
transactions; the `ltcg_fmv_benefit` factor sets it to 180. An earlier audit
here searched for the wrong spelling (`FMV as on 31-Jan-2018`), found nothing,
and wrongly concluded the field was never written. The field is populated and
carried everywhere -- it is the post-2018 purchase date that makes it dead, not
its absence. Consequently the `ltcg_fmv_benefit` factor, which Table 1 of the
paper lists as a tested scenario, exercises no grandfathering at all: it is a
large-gain LTCG case carrying an unreachable FMV. Either relabel it or footnote
it until the v2 pre-2018 dates land.

**New gap found by this audit: the holding-period threshold is never tested near
its boundary.** Two purchase dates against a constant sale date gives every
transaction a holding period of either ~18.5 months or ~6.5 months. The
12-month equity threshold is only ever probed at those two distant points, so an
off-by-one in the comparison would pass all 569 cases. The same shape as the
pinned STCL financial year.

v2 input worklist, to land in one pass: pre-2018 purchase dates with a populated
FMV; holding periods at 11 and 13 months; non-zero Debentures, VPF, EPF employer
contribution, NSC, SCSS and Sukanya Samriddhi; `Number of Years Paid` > 1; an
STCL financial year outside the 8-year window; and the `Other Interest` input
rename.

#### Gemma 4 12B script arm complete at 50/50 under the final prompt and fixed harness

Run with `ollama/gemma4-12b-ctx16k` (num_ctx 16384), 10-12 Oct, including the
fixed-point and `extract_code` fixes. Cases 1-2 were run during validation of
those fixes; `input_0255` was re-run under the fixed harness, so all 50 cases are
harness-matched.

| | |
|---|---|
| Overall accuracy | **45.2%** (50 cases, 35 fields) |
| Parse failures | 1 (`input_0255`, identical-script abandonment) |
| Strict accuracy | 0/50 |
| Mean rounds | 2.28 (distribution 1:24, 2:11, 3:3, 4:3, 5:7, 6:2) |
| Mean tokens | 25,565 |
| Mean latency | 2,794 s/case; 38.8 h total |

Per-section: Salary 45.4%, Capital Gains 16.0%, Other Sources 98.0%,
Aggregates 4.0%, Deductions 65.8%, Tax Computation 28.2%. Derived 38.5%,
copied 97.5%.

**Against the archived pre-fix run, re-scored on the identical 35-field metric
(n=50, same cases):** new prompt 45.20% vs old 43.49% (**+1.71 points**), better
27, worse 12, same 11; tokens -17%, mean rounds 2.28 vs 2.88, total time 38.8 h
vs 43.1 h. Earlier interim figures of -5 to -6 points (reported at n=9-10) were
an artefact of comparing 35-field against 37-field percentages and are
withdrawn.

**Truncation misdiagnosis dominates the cost.** 10 of 50 cases contain at least
one truncated response (an over-long script cut off at the context limit, which
then exits 0 having printed nothing and is told to "call your function"). Those
10 cases consumed **23.9 h of the 38.8 h total (62%)** and scored 43.4% on
average. Fixing the feedback for truncated responses is the highest-value
harness change outstanding; it was deliberately not applied mid-arm, to keep the
arm internally consistent.
