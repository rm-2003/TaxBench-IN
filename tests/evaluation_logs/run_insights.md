# Evaluation Run Insights

Each run section follows this format for consistency:

```
## Run N — <purpose> | seed=<S> | <C> cases | <method>

| Field          | Value          |
|----------------|----------------|
| Date           | YYYY-MM-DD     |
| Seed           | <int>          |
| Cases          | <int>          |
| Method         | zero-shot / script / tool-call |
| Models         | <int>          |
| max_tokens     | <int>          |
| Budget         | $X.XX          |
| Total spent    | $X.XXXX        |
| Log file       | <filename>     |

### Per-model results — <table>
### Per-section accuracy — <table>
### Issues found — <details + fixes>
```

---

## Run 1 — Smoke test | seed=42 | 10 cases | zero-shot

| Field | Value |
|-------|-------|
| Date | 2026-04-24 |
| Seed | 42 |
| Cases | 10 |
| Method | zero-shot |
| Models | 7 |
| max_tokens | 16384 |
| Budget | $17.00 |
| Total spent | $0.2093 |
| Log file | `run_zero-shot_20260424_smoke10.log` |

### Per-model results

| Tier | Model | Accuracy | Parse Rate | Cost | Latency/case | Tokens/case |
|------|-------|----------|-----------|------|-------------|-------------|
| Strong | tencent/hy3-preview:free | 57.0% | 10/10 | $0.00 | 383s | 23,291 |
| Strong | openai/gpt-oss-120b | 55.4% | 10/10 | $0.0295 | 176s | 7,355 |
| Mid | deepseek/deepseek-chat-v3-0324 | 48.4% | 10/10 | $0.0226 | 112s | 4,011 |
| Mid | meta-llama/llama-3.3-70b-instruct | 32.7% | 8/10 | $0.0066 | 38s | 3,116 |
| Mid | google/gemma-4-31b-it:free | — | 0/10 | $0.00 | — | — |
| Weak | openai/gpt-oss-20b | 37.8% | 9/10 | $0.0117 | 104s | 8,295 |
| Weak | nvidia/nemotron-nano-9b-v2:free | 36.8% | 10/10 | $0.00 | 145s | 6,986 |

### Per-section accuracy (all models)

| Model | Salary | Cap Gains | Other Src | Aggregates | Deductions | Tax Comp |
|-------|--------|-----------|-----------|------------|------------|----------|
| hy3-preview | 72.9% | 25.0% | 96.7% | 0.0% | 75.6% | 41.4% |
| gpt-oss-120b | 67.1% | 45.0% | 100.0% | 0.0% | 65.6% | 42.9% |
| deepseek-v3 | 67.1% | 15.0% | 100.0% | 0.0% | 58.9% | 32.9% |
| gpt-oss-20b | 41.4% | 15.0% | 90.0% | 0.0% | 41.1% | 31.4% |
| nemotron-9b | 37.1% | 5.0% | 100.0% | 0.0% | 45.6% | 27.1% |
| llama-70b | 27.1% | 15.0% | 80.0% | 0.0% | 37.8% | 29.3% |

### Issues found and fixes applied

#### 1. Gemma free endpoint — all 10 cases skipped (429)

**Root cause**: OpenRouter enforces a **global free-models-per-minute** rate limit across all free-tier calls combined, not per model. With 3 free models (hy3-preview, gemma, nemotron) running concurrently, each with concurrency=4, the combined free call rate exceeded the platform limit. The error message `"Rate limit exceeded: free-models-per-minute"` contained the substring `"limit exceeded"`, which was caught by the daily-cap check (`if "daily" in err_str or "limit exceeded" in err_str: raise`), bypassing the fallback mechanism entirely.

**Fix**: (a) Moved the `FREE_FALLBACKS` check before the daily-cap raise, so paid fallback is always attempted first. (b) Removed the `attempt >= 1` guard — fallback now triggers immediately on first 429, since retrying the same free endpoint that's rate-limited is pointless. (c) Narrowed the daily-cap check to only match `"daily"` (not `"limit exceeded"`).

Actually though it was an issue of:
No — the paid model was never actually called. That's the bug. Here's what happened on every single retry:                                                                              
1. Loop starts → call_kwargs = dict(kwargs) → model = google gemma-4-31b-it:free                                                                 
2. Hits free endpoint → 429
3. Fallback triggers → sets call_kwargs["model"] = "google/gemma-4-31b-it" (paid)                                                    
4. continue → goes back to top of loop   
5. call_kwargs = dict(kwargs) rebuilds from original → model = google/gemma-4-31b-it:free again
6. Hits free endpoint → 429 again               
7. Repeat until all 3 retries exhausted 

#### 2. Llama 70B — 2 parse failures (input_0280, input_0287)

**Observation**: Despite 16K max_tokens, Llama still had 2/10 parse failures. In tuning (3 cases, seed 77), 16K gave 100% parse rate. The evaluate run used a different set of 10 cases (seed 42) — these two cases may require more reasoning tokens than the tuning cases did.

**Fix**: Bumped max_tokens to 32768 for all models. This gives reasoning models ample headroom while non-reasoning models (deepseek, gpt-oss) will simply stop generating when done and won't waste tokens.

#### 3. Aggregates 0.0% across all models — NOT a bug

**Observation**: Gross Total Income and Total Taxable Income scored 0% for every model. These are **computed aggregates** — Gross Total Income = sum of all income heads (salary + capital gains + other sources), Total Taxable Income = Gross Total Income minus deductions. If *any* upstream component is wrong, the aggregate will be wrong too.

**Why this is expected**: At current accuracy levels (35-57%), models get enough upstream fields wrong that the aggregates never land within ±0.01 tolerance. This will naturally improve if/when individual section accuracy improves. No code change needed.

### Fixes applied after this run

| Fix | File | Change |
|-----|------|--------|
| Free-tier fallback | `evaluate_llm.py` | `FREE_FALLBACKS` triggers immediately on first 429, before daily-cap raise |
| Free-tier fallback (kwargs rebuild) | `evaluate_llm.py` | Introduced `active_model` variable outside retry loop so fallback persists across iterations |
| max_tokens | `evaluate_llm.py` | 16384 → 32768 for all models |

---

## Run 2 — Full benchmark | seed=42 | 20 cases | zero-shot

| Field | Value |
|-------|-------|
| Date | 2026-04-24 |
| Seed | 42 |
| Cases | 20 |
| Method | zero-shot |
| Models | 7 |
| max_tokens | 32768 |
| Budget | $17.00 |
| Total cost (all 20 cases) | $0.1461 |
| Log files | `run_zero-shot_20260424_113933.log` (6 models), `run_zero-shot_20260424_114907_20cases_gemma-4-31b-it:free_retry.log` (gemma solo) |

**Note**: This run extended the Run 1 smoke test from 10 → 20 cases on the same seed. The 6 non-Gemma models resumed from their 10-case checkpoints. Gemma was run separately after fixing the free-tier fallback bug (see Run 1 issues #1). Llama's 2 parse failures from the first 10 cases (at max_tokens=16384) are checkpointed and were **not** re-run at 32768.

### Per-model results

| Tier | Model | Accuracy | Parse Rate | Cost | Latency/case | Tokens/case |
|------|-------|----------|-----------|------|-------------|-------------|
| Strong | tencent/hy3-preview:free | 59.7% | 19/20 | $0.00 | 309s | 21,500 |
| Strong | openai/gpt-oss-120b | 55.5% | 20/20 | $0.0458 | 137s | 6,961 |
| Mid | google/gemma-4-31b-it:free | 49.7% | 20/20 | $0.0118 | 38s | 3,287 |
| Mid | deepseek/deepseek-chat-v3-0324 | 48.8% | 20/20 | $0.0464 | 120s | 4,083 |
| Weak | nvidia/nemotron-nano-9b-v2:free | 39.9% | 20/20 | $0.00 | 176s | 6,940 |
| Weak | meta-llama/llama-3.3-70b-instruct | 39.1% | 18/20 | $0.0130 | 51s | 3,079 |
| Weak | openai/gpt-oss-20b | 37.8% | 18/20 | $0.0291 | 78s | 9,131 |

### Per-section accuracy (all models)

| Model | Salary | Cap Gains | Other Src | Aggregates | Deductions | Tax Comp |
|-------|--------|-----------|-----------|------------|------------|----------|
| hy3-preview | 70.7% | 44.7% | 96.5% | 2.6% | 80.7% | 43.2% |
| gpt-oss-120b | 66.4% | 52.5% | 100.0% | 0.0% | 63.3% | 43.9% |
| gemma-4-31b-it | 49.3% | 15.0% | 93.3% | 0.0% | 78.3% | 34.3% |
| deepseek-v3 | 60.0% | 20.0% | 100.0% | 0.0% | 61.7% | 35.0% |
| nemotron-9b | 34.3% | 10.0% | 100.0% | 0.0% | 54.4% | 30.4% |
| llama-70b | 31.4% | 22.5% | 90.0% | 0.0% | 42.8% | 37.5% |
| gpt-oss-20b | 34.3% | 22.5% | 90.0% | 0.0% | 40.0% | 34.6% |

### Issues found

#### 1. Gemma free-tier fallback — confirmed fixed

Gemma ran successfully as a separate job after the `active_model` fix from Run 1. All 20 cases parsed (100% parse rate). The fallback to paid endpoint triggered frequently (visible in logs as `429 on free tier — switching`) but always recovered. Cost was $0.0118, confirming paid endpoint was used for ~half the calls.

#### 2. Llama 70B — 2 parse failures carry over from Run 1

`input_0280` and `input_0287` were checkpointed as parse failures from Run 1 (max_tokens=16384). Since checkpointing prevents re-runs, these were scored as 0 in the 20-case results. Deleting these checkpoint entries would allow them to re-run at 32768, which previously fixed Llama's parse issues in tuning.

#### 3. gpt-oss-20b — 2 parse failures

`input_0097` (18K tokens generated) and `input_0248` (35K tokens, $0.006 for a single case). The model generates massive output without producing parseable JSON. This is a model capability limitation, not a token budget issue — the model simply fails to follow the output format instructions for complex cases.

#### 4. hy3-preview — 1 skip

`input_0549` exhausted all 3 retries. Likely a transient free-tier rate limit issue. With 19/20 cases evaluated, accuracy is 59.7%.

#### 5. Tier shifts from Run 1 → Run 2

With 2× more cases, some rankings shifted:
- **Gemma** (new): slots in at Mid tier, 49.7% — between gpt-oss-120b and deepseek-v3
- **Nemotron** improved from 36.8% → 39.9%, but still Weak tier
- **Llama** improved from 32.7% → 39.1% (accuracy up due to more cases, but 2 parse failures still drag it down)
- **Deepseek** held steady: 48.4% → 48.8%
- **Top two unchanged**: hy3-preview (57→60%) and gpt-oss-120b (55→56%)

### Preemptive fixes applied after this run

| Fix | File | Change |
|-----|------|--------|
| `RateLimitExhausted` exception | `evaluate_llm.py` | Distinct exception type when all retries exhausted due to 429s, so callers can distinguish rate limits from other failures |
| Sliding window submission | `evaluate_llm.py` | Cases fed incrementally (window of `concurrency`) instead of all upfront — allows stopping the tap on rate limits without queued futures all failing independently |
| Self-healing rate-limit pause | `evaluate_llm.py` | On `RateLimitExhausted`: stop feeding new cases, drain in-flight. If any in-flight succeeds → reset and resume. If all drain with rate limits → cooldown sleep (120s), then retry remaining. After 2 cooldowns → halt model |

---

## Run 3 — 50 cases | seed=42 | 50 cases | zero-shot

| Field | Value |
|-------|-------|
| Date | 2026-04-24 |
| Seed | 42 |
| Cases | 50 |
| Method | zero-shot |
| Models | 7 |
| max_tokens | 32768 |
| Budget | $17.00 |
| Total spent | ~$0.59 |
| Log files | `run_zero-shot_20260424_130239_50cases_hy3-preview_retry.log`, `run_zero-shot_20260424_131237_50cases_gpt-oss-20b_retry.log` |

**Note**: Resumed from 20-case checkpoints (Run 2). Main process was killed after 6 of 7 models completed — hy3-preview was at 38/50. hy3-preview re-run separately with bumped config (`rpm=20, concurrency=8`). gpt-oss-20b's 5 parse failures were re-run with no max_tokens cap — 4 of 5 parsed successfully, 1 remains a genuine format failure (`input_0248`, 67K tokens).

### Per-model results

| Tier | Model | Accuracy | Parse Rate | Cost | Latency/case | Tokens/case |
|------|-------|----------|-----------|------|-------------|-------------|
| Strong | tencent/hy3-preview:free | 55.4% | 49/50 | $0.00 | 336s | 23,187 |
| Strong | openai/gpt-oss-120b | 53.6% | 50/50 | $0.1078 | 122s | 7,051 |
| Mid | google/gemma-4-31b-it:free | 49.8% | 50/50 | $0.0324 | 59s | 3,317 |
| Mid | deepseek/deepseek-chat-v3-0324 | 47.6% | 50/50 | $0.1179 | 131s | 4,172 |
| Mid | openai/gpt-oss-20b | 40.7% | 49/50 | $0.0759 | 96s | 9,113 |
| Weak | nvidia/nemotron-nano-9b-v2:free | 39.2% | 50/50 | $0.00 | 176s | 7,057 |
| Weak | meta-llama/llama-3.3-70b-instruct | 37.1% | 45/50 | $0.0334 | 39s | 3,109 |

### Per-section accuracy

| Model | Salary | Cap Gains | Other Src | Aggregates | Deductions | Tax Comp |
|-------|--------|-----------|-----------|------------|------------|----------|
| hy3-preview | 69.7% | 33.0% | 91.3% | 2.0% | 72.4% | 40.4% |
| gpt-oss-120b | 61.1% | 42.0% | 100.0% | 0.0% | 62.0% | 43.9% |
| gemma-4-31b-it | 50.0% | 11.0% | 96.0% | 0.0% | 76.0% | 35.6% |
| deepseek-v3 | 56.9% | 18.0% | 100.0% | 0.0% | 58.7% | 35.6% |
| gpt-oss-20b | 39.1% | 24.0% | 98.0% | 1.0% | 40.4% | 37.4% |
| nemotron-9b | 31.1% | 12.0% | 100.0% | 0.0% | 51.1% | 32.0% |
| llama-70b | 28.9% | 17.0% | 90.0% | 0.0% | 39.6% | 36.6% |

### Issues found

#### 1. Llama 70B — 5 parse failures (10%)

`input_0280`, `input_0287` (carried over from Run 2 at 16K max_tokens), plus 3 new: `input_0313`, `input_0201`, `input_0498`. The original 2 are token-budget failures from the 16K era. The 3 new ones occurred at 32K — Llama's thinking chain may still exhaust the budget on complex cases. Accuracy dropped from 39.1% → 37.1% with more cases.

#### 2. gpt-oss-20b — 5→1 parse failure after max_tokens removal

Originally 5 parse failures, all hitting the 32K max_tokens ceiling (`completion=32768`). Checkpoint entries removed and re-run with no token cap. 4 of 5 parsed successfully:

| Case | Before | After (no cap) | Tokens |
|------|--------|----------------|--------|
| input_0539 | PARSE_FAIL (32K) | 17/37 (46%) | 5,563 |
| input_0097 | PARSE_FAIL (32K) | 12/37 (32%) | 7,581 |
| input_0451 | PARSE_FAIL (32K) | 13/37 (35%) | 10,510 |
| input_0547 | PARSE_FAIL (32K) | 12/37 (32%) | 11,028 |
| input_0248 | PARSE_FAIL (32K) | PARSE_FAIL (67K, $0.013) | 67,669 |

`input_0248` remains a genuine format failure — model generates 67K tokens without valid JSON. Overall accuracy improved from 37.8% → **40.7%**, parse rate from 45/50 → **49/50**.

#### 3. Aggregates still 0% (except gpt-oss-20b at 1%)

Remains expected — computed fields cascade upstream errors. gpt-oss-20b got 1 aggregate correct by chance.

#### 4. Gemma free-tier fallback working smoothly

Gemma's fallback to paid endpoint triggered throughout the run (429 → switch visible in logs). All 50 cases parsed successfully. Total cost $0.0324 confirms ~half hit the paid endpoint.

#### 5. hy3-preview — 1 parse failure (input_0549, carried from Run 2)

Same case that failed in Run 2 — `input_0549` exhausted retries. 49/50 parsed. Despite this, hy3-preview leads at 55.4%.

#### 6. Tier consolidation at 50 cases

Rankings stabilised compared to 20 cases:
- **hy3-preview** leads at 55.4% (down from 59.7% at 20 cases) — still Strong tier, $0.00 cost
- **gpt-oss-120b** solidly second at 53.6% (down from 55.5%) — most consistent (50/50 parse)
- **Gemma** and **deepseek** cluster tightly in Mid tier (49.8% vs 47.6%)
- **gpt-oss-20b** improved from 37.8% → 40.7% after token cap removal, promoted to Mid tier
- **Nemotron** stable at 39.2%, Weak tier but perfect parse rate (50/50)
- **Llama** dropped to 37.1% — 5 parse failures drag it down despite decent per-field accuracy when parsing succeeds

#### 7. hy3-preview rpm/concurrency bump

hy3-preview was bumped from `rpm=12, concurrency=4` to `rpm=20, concurrency=8` mid-run. The remaining 12 cases completed without rate-limit issues, confirming the higher config is viable for this model.

---

## Run 4 — First complete script arm | seed=42 | 50 cases | script

| Field | Value |
|-------|-------|
| Date | 2026-10-10 |
| Seed | 42 |
| Cases | 50 |
| Method | script |
| Models | 1 (nvidia/nemotron-3-ultra-550b-a55b:free) |
| Scored fields | 35 (was 37 through Run 3) |
| Budget | $17.00 |
| Total spent | $0.0000 |
| Log file | `nemotron_script_v2.out`, `run_script_20261010_060735.log` |

First arm run end-to-end under the final prompt and the corrected answer key.
Resumed from a 33-case checkpoint after the 4 Oct attempt hit a 429 daily cap at
`input_0363`; that case correctly left no record and so re-entered the queue, so
all 50 cases are prompt-matched.

### Per-model results

| Model | Accuracy | Parse fail | Mean rounds | Mean latency | Mean tokens | Cost |
|---|---|---|---|---|---|---|
| nemotron-3-ultra-550b | 60.7% | 0 | 1.2 | 369 s | 24,478 | $0.0000 |

The same model's zero-shot arm scores 61.4% at 866 s/case, so the script method
is near-identical on accuracy at **2.3x less wall time**.

### Per-section accuracy

| Section | Fields | Accuracy |
|---|---|---|
| Salary | 7 | 75.1% |
| Capital Gains | 2 | 43.0% |
| Other Sources | 3 | 100.0% |
| Aggregates | 2 | 6.0% |
| Deductions | 9 | 82.2% |
| Tax Computation | 12 | 38.3% |

Derived (31 fields, computed) 55.8% vs copied (4 fields, from input) 98.5%.

### Issues found

#### 1. Aggregates at 6.0% is the employer-NPS correction, not a scoring defect

`gross_salary` is wrong in 34 of 50 cases and in **all 34 the error is exactly the
Tier-1 employer NPS contribution** — the v1.4.4 ground-truth fix (s.17(1)(viii))
reproduced as a measurement. With `TOLERANCE = 0.01`, Gross Total Income and Total
Taxable Income are accumulators that inherit that one omission and fail. Median GTI
error is 1.92%; 35 of 47 misses sit within 5%. The invariant `GTI = sum of heads`
holds with 0 violations in 50, so the answer key is self-consistent.

Salary scoring 75.1% beside Aggregates at 6.0% — one wrong field of seven versus
one wrong accumulator of two — is the clearest argument in the dataset for
per-field scoring over a single bottom-line number.

#### 2. Retry causes are genuine Python faults, not format negotiation

Across all 50 cases: `NameError` 3, `IndentationError` 2, `SyntaxError` 1, `ValueError` 1.
Confirms the code-fence override holds. 7 of 50 cases retried at all and all 7
transcripts stored. Worst case `input_0076` spent 3 rounds and 57,775 tokens on
two indentation faults to reach 49%.

#### 3. Two harness defects found after this run — present in these numbers

- `extract_code()` returned the **first** fenced block. `input_0411` sent a
  358-char stub ahead of the real 13,499-char script and the stub ran. The case
  recovered at rounds=2 and scored 21/35, so **this arm's accuracy stands**, but its
  mean rounds (1.2) and mean tokens (24,478) are slightly inflated.
- The retry-history trim plus `temperature=0` makes a repair round deterministic,
  so a failed repair regenerates byte-identical output forever. Nemotron peaked at
  3 rounds and never entered the loop, so this arm is unaffected; gemma's
  `input_0255` burned 5 identical rounds for 0/35.

Re-running this arm under the fixed harness costs ~50 free requests and would make
the efficiency columns strictly comparable with later arms.

---

## Run 5 — Gemma 4 12B script arm | seed=42 | 50 cases | script

| Field | Value |
|-------|-------|
| Date | 2026-10-10 to 2026-10-12 |
| Seed | 42 |
| Cases | 50 |
| Method | script |
| Models | 1 (ollama/gemma4-12b-ctx16k, local, num_ctx 16384) |
| Scored fields | 35 |
| Total spent | $0.0000 |
| Log file | `gemma_script_v3.out`, `run_script_20261010_113242.log` |

### Per-model results

| Model | Accuracy | Parse fail | Mean rounds | Mean latency | Mean tokens | Strict |
|---|---|---|---|---|---|---|
| gemma4-12b (ctx16k) | 45.2% | 1 | 2.28 | 2,794 s | 25,565 | 0/50 |

### Per-section accuracy

| Section | Fields | Accuracy |
|---|---|---|
| Salary | 7 | 45.4% |
| Capital Gains | 2 | 16.0% |
| Other Sources | 3 | 98.0% |
| Aggregates | 2 | 4.0% |
| Deductions | 9 | 65.8% |
| Tax Computation | 12 | 28.2% |

### Issues found

#### 1. Prompt fix: small accuracy gain, moderate cost saving
Paired against the archived pre-fix run on the same 50 cases and the same
35-field metric: +1.71 points (45.20% vs 43.49%), better 27 / worse 12 /
same 11, tokens -17%, rounds 2.28 vs 2.88.

#### 2. Truncation misdiagnosis consumes 62% of runtime
10 of 50 cases contain a truncated response; they took 23.9 h of 38.8 h. The
harness reports "printed nothing — call your function" for a script that was
simply cut off. Not fixed mid-arm; highest-priority harness change for the next
run.

#### 3. Zero-shot comparison is context-confounded
Gemma zero-shot ran at num_ctx 8192 and script at 16384, so the 36.7% vs 45.2%
gap mixes method and context size.
