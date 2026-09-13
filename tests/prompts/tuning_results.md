# Prompt Tuning Results

Prompt hash: `56a6dbd9` (frozen after these results)

## Final validation run (all 6 models × 3 cases, parallel)

Date: 2026-04-23
Method: zero-shot
Cases: `input_0259.json`, `input_0334.json`, `input_0203.json` (seed 77)
Cost: $0.28 for 18 API calls

### Per-model results

| Tier | Model | Parse Rate | Mean Score | Per-case scores |
|------|-------|-----------|------------|-----------------|
| 1 — High | tencent/hy3-preview:free | 3/3 (100%) | 71.2% | 0259: 51.4%, 0334: **94.6%**, 0203: 67.6% |
| 1 — High | openai/gpt-oss-120b:free | 3/3 (100%) | 57.7% | 0259: 37.8%, 0334: **83.8%**, 0203: 51.4% |
| 2 — Mid | deepseek/deepseek-chat-v3-0324 | 3/3 (100%) | 52.3% | 0259: 40.5%, 0334: 59.5%, 0203: 56.8% |
| 2 — Mid | meta-llama/llama-3.3-70b-instruct | 2/3 (67%) | 44.6% | 0259: 43.2%, 0334: **FAIL**, 0203: 45.9% |
| 3 — Low | openai/gpt-oss-20b:free | 2/3 (67%) | 60.8% | 0259: **FAIL**, 0334: 59.5%, 0203: 62.2% |
| 3 — Low | nvidia/nemotron-nano-9b-v2:free | 3/3 (100%) | 49.5% | 0259: 21.6%, 0334: **86.5%**, 0203: 40.5% |

### Parse failures — details and legitimacy

#### 1. meta-llama/llama-3.3-70b-instruct — `input_0334.json`

**What happened**: The model responded entirely inside `<think></think>` tags with reasoning text (e.g., "To calculate the tax, we first need to determine the income from various sources...") but never produced the final JSON output after the closing `</think>` tag. The response was truncated — likely hit the max output token limit mid-reasoning.

**Why this is a legitimate failure**: The system prompt instructs the model to reason inside `<think>` tags and then output JSON after them. The model correctly understood the reasoning instruction but failed to manage its token budget — it spent all available tokens on chain-of-thought and never reached the JSON output phase. This is a model capability limitation (token budget management under complex multi-step reasoning), not a prompt formatting issue.

**`extract_json` behaviour**: Found `{` characters inside the reasoning text (e.g., in references to JSON structure) but these were embedded in natural language, not valid JSON objects. Correctly returned `None`.

#### 2. openai/gpt-oss-20b:free — `input_0259.json`

**What happened**: The model returned `{ }` — a syntactically valid but empty JSON object. No keys, no values.

**Why this is a legitimate failure**: `input_0259.json` is a complex case (`salary_level=above_2Cr`, `hra_city=metro_pct_binding`, `lta=claim_exceeds_salary_lta`, multiple deductions). The 20B model appears to have recognized it should return JSON (it produced valid syntax) but could not compute any of the ~50 required fields. This represents a genuine model capability boundary — the model understood the format requirement but lacked the capacity to produce the content. The `response_format: json_object` flag was active, which may have forced valid JSON syntax but couldn't force meaningful content.

**`extract_json` behaviour**: Parsed `{ }` as a valid dict with no keys. Scoring correctly assigned 0 to all 37 fields.

### Key observations across models

#### Format adherence (key name accuracy)
- **nemotron-nano-9b**: Occasionally misplaces keys — e.g., puts `Section 16(ia)`, `Section 16(ii)`, `Section 16(iii)` under `Exemptions` instead of directly under `Under Head Salaries`. Also sometimes writes `"Under HeadSalaries"` (missing space). These are structural errors scored as missing fields.
- **All other models**: Exact key names when they produce output.

#### Case difficulty variation
- `input_0334.json` was the "easiest" case — 4 of 6 models scored >59%, with hy3-preview hitting 94.6% and nemotron-nano hitting 86.5%. Likely a simpler tax scenario (fewer edge cases).
- `input_0259.json` was the "hardest" — above-2Cr income with surcharge, multiple exemptions, LTA exceeding salary component. 3 of 6 models scored <43%, and gpt-oss-20b returned an empty object.

### Earlier tuning runs (chronological)

| Run | Date | Models tested | Cases | Key findings |
|-----|------|--------------|-------|-------------|
| 1 | 2026-04-23 13:47 | nemotron-nano, gemma-4 (429), llama-70b-free (429) | 5 (seed 42) | nemotron-nano: 100% parse, 41.6% score. Gemma/Llama free endpoints rate-limited. |
| 2 | 2026-04-23 14:43 | nemotron-super (empty), gpt-oss-120b | 2 (seed 42) | nemotron-super returns empty choices even without json_object. gpt-oss-120b: 100% parse, 55.4%. |
| 3 | 2026-04-23 14:53 | gpt-oss-20b | 2 (seed 42) | 50% parse — malformed JSON with embedded control chars. Led to adding `_clean_json_text()`. |
| 4 | 2026-04-23 15:36 | hy3-preview, gemma-4 (429) | 2 (seed 42) | hy3-preview: 100% parse, 47.3%. JSON mode not supported (400 error, fallback works). Gemma still 429. |
| 5 | 2026-04-23 17:26 | gpt-oss-20b (re-test) | 2 (seed 99) | After control-char fix: 100% parse, 39.2%. Fix validated. |
| 6 | 2026-04-23 21:48 | deepseek-v3, llama-70b (paid) | 2 (seed 42) | Both 100% parse. Budget guard updated from $0.01 hard stop to $1.00 budget. |
| 7 | 2026-04-23 22:46 | All 6 final models | 3 (seed 77) | Final validation — see table above. Prompt frozen. |

### Prompt improvements applied during tuning

1. **Guidelines 1-4** (applied to `system_prompt.txt`):
   - Tail reinforcement: "Begin your response with { and end with }. Nothing else."
   - Negative example for markdown fencing (WRONG/CORRECT)
   - Think-then-respond `<think></think>` tags for reasoning models
   - Explicit "do not say 'Here is the JSON'" prohibition

2. **Guideline 5** (applied to code):
   - `response_format: {"type": "json_object"}` auto-attempted on all non-tool-call requests
   - Fallback on 400/unsupported errors (hy3-preview, nemotron-super)
   - Fallback on empty choices (nemotron-super with json_object → empty response)

3. **Control character cleaning** (applied to `extract_json`):
   - `_clean_json_text()` strips `[\x00-\x09\x0b\x0c\x0e-\x1f]` before parsing
   - Fixes gpt-oss-20b embedded newline corruption

### Dropped models (with reasons)

| Model | Issue | When discovered |
|-------|-------|----------------|
| google/gemma-4-31b-it:free | Persistent 429 upstream (Google AI Studio) | Runs 1, 4 |
| nvidia/nemotron-3-super-120b-a12b:free | Returns empty choices (None) even without json_object | Runs 2, multiple retests |
| meta-llama/llama-3.3-70b-instruct:free | 429 upstream (Venice, 8 req/min cap) | Run 1 |
| qwen/qwen3-coder:free | 429 rate limited | Initial API test |

---

## Extended validation run (all 6 models × 10 cases, parallel)

Date: 2026-04-24
Method: zero-shot
Cases: seed 123, 10 cases: `input_0054`, `input_0275`, `input_0090`, `input_0418`, `input_0273`, `input_0111`, `input_0040`, `input_0389`, `input_0550`, `input_0341`
Settings: RPM=18, concurrency=6

### Per-model results

| Tier | Model | Parse Rate | Mean Score | Model Cost | Status |
|------|-------|-----------|------------|------------|--------|
| 1 — High | tencent/hy3-preview:free | 9/10 (90%) | 58.3% | $0.00 | 1 parse fail (input_0341) |
| 1 — High | openai/gpt-oss-120b (paid) | 10/10 (100%) | 53.6% | $0.032 | Free endpoint 503'd; all 10 done via paid |
| 2 — Mid | deepseek/deepseek-chat-v3-0324 | 10/10 (100%) | 47.8% | ~$0.08 | Most reliable |
| 2 — Mid | meta-llama/llama-3.3-70b-instruct | 9/10 (90%) | 41.6% | $0.011 | 1 consistent fail (input_0341) |
| 3 — Low | nvidia/nemotron-nano-9b-v2:free | 10/10 (100%) | 35.1% | $0.00 | Key name typos in 4/10 |
| 3 — Low | openai/gpt-oss-20b (paid) | 10/10 (100%) | 44.5% | $0.008 | Free endpoint 503'd; all 10 done via paid |

Note: gpt-oss-120b and gpt-oss-20b free endpoints were down (OpenInference 503 outage) during the initial run. All 10 cases completed via paid endpoints across retries. Llama had 3 initial failures; 2 recovered on retry, input_0341 consistently fails.

### Per-case breakdown (all models, all 10 cases complete)

| Case | hy3-preview | gpt-oss-120b | deepseek-v3 | llama-70b | nemotron-9b | gpt-oss-20b |
|------|-------------|-------------|-------------|-----------|-------------|-------------|
| input_0054 | 56.8% | 62.2% | 51.4% | 43.2% | 29.7% | 51.4% |
| input_0275 | 64.9% | 56.8% | 51.4% | 54.1% | 35.1% | 51.4% |
| input_0090 | 54.1% | 45.9% | 37.8% | 35.1% | 27.0% | 32.4% |
| input_0418 | 62.2% | 45.9% | 35.1% | 27.0% | 27.0% | 43.2% |
| input_0273 | 54.1% | 54.1% | 48.6% | 45.9% | 32.4% | 43.2% |
| input_0111 | 48.6% | 56.8% | 43.2% | 45.9% | 35.1% | 35.1% |
| input_0040 | 67.6% | 51.4% | 54.1% | 51.4% | 48.6% | 43.2% |
| input_0389 | 62.2% | 51.4% | 48.6% | 37.8% | 29.7% | 43.2% |
| input_0550 | 54.1% | 51.4% | 48.6% | 32.4% | 27.0% | 43.2% |
| input_0341 | **FAIL** | 62.2% | 59.5% | **FAIL** | 59.5% | 59.5% |

### Parse failures — details

#### 1. openai/gpt-oss-120b:free — initial 503, resolved via paid endpoint
All 10 cases initially returned `503 - "no healthy upstream"` from OpenInference provider. All 10 retried on paid `openai/gpt-oss-120b` — 10/10 parsed. Total model cost: $0.032.

#### 3. meta-llama/llama-3.3-70b-instruct — 3/10 failed (input_0418, input_0111, input_0341)

**Failure pattern**: All 3 failures are identical — the model begins with `<think>` tags and writes extended chain-of-thought reasoning ("To calculate the tax, we first need to...") but exhausts its output token budget before ever producing the JSON output after the closing `</think>` tag.

**Why this is systemic**: Llama 70B consistently fails on complex cases that require more reasoning steps (multi-exemption, capital gains, surcharge calculations). The model correctly follows the `<think>` tag instruction but cannot manage its token budget to reserve space for the ~1500-token output JSON. This is a 30% failure rate across runs — a real model limitation.

**Cases that failed initially** (input_0418, input_0111, input_0341) — retried after budget was hit. input_0418 (27.0%) and input_0111 (45.9%) succeeded on retry. input_0341 failed again — deterministically too complex for this model. Retry cost: $0.0054.

**Cases that succeeded** (7/10): input_0054 (43.2%), input_0275 (54.1%), input_0090 (35.1%), input_0040 (51.4%), input_0550 (32.4%), input_0389 (37.8%), input_0273 (45.9%)

#### 4. tencent/hy3-preview:free — 1/10 failed (input_0341)

**Failure pattern**: The model started explaining the `<think>` tag instruction itself ("tags, then the JSON. But the instruction: 'If you need to reason, do so inside tags before the JSON...'") rather than actually using the tags. It reflected on the prompt instructions instead of following them.

**Why this is a legitimate failure**: This is an instruction-following failure — the model interpreted the `<think>` tag instruction as content to discuss rather than a directive to follow. This occurred on `input_0341`, which was also one of the cases Llama failed on, suggesting it may be a particularly complex case that triggers unusual model behavior.

**Cases that succeeded** (9/10): input_0090 (54.1%), input_0111 (48.6%), input_0275 (64.9%), input_0054 (56.8%), input_0418 (62.2%), input_0040 (67.6%), input_0389 (62.2%), input_0550 (54.1%), input_0273 (54.1%)

#### 5. nvidia/nemotron-nano-9b-v2:free — 0 parse failures, but key name issues

All 10 cases parsed successfully but 4/10 had key name errors:
- `input_0054`: `"Under HeadSalaries"` (missing space) — 7 keys affected
- `input_0418`: `"UnderHead Salaries"` (space in wrong place) — 7 keys affected
- `input_0275`: `"Under HeadSalaries"` — 7 keys affected
- `input_0090`: `"UnderHead Salaries"` — 7 keys affected

These produce 0 scores on all salary-section fields since the key paths don't match. This is a tokenization issue — the 9B model's tokenizer splits "Under Head Salaries" inconsistently.

### Per-model cost and accuracy summary (10 cases each)

| Tier | Model | Parse Rate | Mean Score | Cost (10 cases) |
|------|-------|-----------|------------|-----------------|
| 1 — High | tencent/hy3-preview:free | 9/10 (90%) | 58.3% | $0.00 |
| 1 — High | openai/gpt-oss-120b (paid) | 10/10 (100%) | 53.6% | $0.032 |
| 2 — Mid | deepseek/deepseek-chat-v3-0324 | 10/10 (100%) | 47.8% | ~$0.08 |
| 2 — Mid | meta-llama/llama-3.3-70b-instruct | 9/10 (90%) | 41.6% | $0.011 |
| 3 — Low | nvidia/nemotron-nano-9b-v2:free | 10/10 (100%) | 35.1% | $0.00 |
| 3 — Low | openai/gpt-oss-20b (paid) | 10/10 (100%) | 44.5% | $0.008 |

### Conclusion (updated)

The prompt is frozen. Parse failures fall into three categories:
1. **Provider outages** (gpt-oss-120b, gpt-oss-20b): Infrastructure issue, not model or prompt problem — resolved via paid endpoints
2. **Token budget exhaustion** (Llama 70B, 10% of cases): Model starts reasoning but can't finish — systemic limitation
3. **Instruction reflection** (hy3-preview, 10% of cases): Model discusses prompt instructions instead of following them — rare

---

## New model evaluation — Gemma 4 31B & Qwen 3.5 9B (3 cases)

Date: 2026-04-24
Method: zero-shot
Cases: seed 77, 3 cases: `input_0259`, `input_0334`, `input_0203`
Settings: RPM=18, concurrency=9
Prompt hash: `56a6dbd9`

### google/gemma-4-31b-it (max_tokens=4096)

| Case | Score | Notes |
|------|-------|-------|
| input_0334 | 26/37 (70.3%) | |
| input_0203 | 25/37 (67.6%) | |
| input_0259 | 13/37 (35.1%) | Hardest case (above-2Cr, surcharge, multiple exemptions) |

- **Parse rate**: 3/3 (100%)
- **Mean score**: 57.7%
- **Cost**: $0.00 (free endpoint 429'd → fell back to paid, negligible cost)
- **Notes**: Free endpoint (`google/gemma-4-31b-it:free`) returned 429 on all 3 cases. All recovered via paid fallback (`google/gemma-4-31b-it`). 100% JSON adherence, correct key names, no structural issues.

### qwen/qwen3.5-9b — initial run (max_tokens=4096)

| Case | Score | Notes |
|------|-------|-------|
| input_0334 | **FAIL** | Plaintext reasoning, no JSON produced |
| input_0203 | **FAIL** | Plaintext reasoning, no JSON produced |
| input_0259 | 1/37 (2.7%) | Flat/wrong key nesting — keys at root instead of nested |

- **Parse rate**: 1/3 (33%)
- **Mean score**: 2.7%
- **Cost**: $0.0026
- **Failure pattern**: Qwen ignores `<think>` tag instruction, reasons in plaintext, exhausts token budget before producing JSON. The one case that parsed had structurally wrong nesting (e.g. `Section 10(13A)` at root instead of under `Under Head Salaries.Exemptions`).

### qwen/qwen3.5-9b — re-run with max_tokens=16384

| Case | Score | Notes |
|------|-------|-------|
| input_0334 | 3/37 (8.1%) | Parsed but wrong nesting — missing Capital Gains, flat structure |
| input_0259 | **FAIL** | Plaintext reasoning, no JSON produced |
| input_0203 | **FAIL** | Plaintext reasoning, no JSON produced |

- **Parse rate**: 1/3 (33%) — unchanged from 4096 run
- **Mean score**: 8.1%
- **Cost**: $0.0054 (doubled from 4096 run due to longer generation)
- **Conclusion**: Higher token limit did not fix parse failures — Qwen generates extended plaintext reasoning even with 16K tokens available and still never produces JSON. The one parsed case improved from 1/37 to 3/37 but structure remains fundamentally wrong (flat keys, missing entire sections like Capital Gains). This model cannot follow the prompt format.

### meta-llama/llama-3.3-70b-instruct — re-run with max_tokens=16384

Seed 77 cases (same 3 as above) + `input_0341` (previously deterministic failure):

| Case | Score | Notes |
|------|-------|-------|
| input_0334 | 23/37 (62.2%) | Previously failed at 4K tokens |
| input_0203 | 20/37 (54.1%) | |
| input_0259 | 16/37 (43.2%) | |
| input_0341 | 22/37 (59.5%) | **Previously deterministic failure** — now parses and scores |

- **Parse rate**: 4/4 (100%) — up from 67% (seed 77) and 70% (extended 10-case run)
- **Mean score**: 53.2% (seed 77 cases), 59.5% (input_0341)
- **Cost**: $0.0022 (3 cases) + $0.0005 (input_0341) = $0.0027
- **Conclusion**: The 16384 token limit fully resolves Llama 70B's parse failures. The model was exhausting tokens on `<think>` chain-of-thought at 4K and never reaching JSON output. With 16K headroom, all 4 cases parse — including `input_0341` which failed deterministically in all prior runs. This confirms the failure was purely a token budget issue, not a model capability gap.

### Qwen 3.5 9B — degraded performance with increased token limits

Three runs on the same seed 77 cases (`input_0259`, `input_0334`, `input_0203`) with progressively higher token limits:

| Run | max_tokens | Parse Rate | Total Cost | Cost/Call | Est. Output Tokens/Call |
|-----|-----------|-----------|-----------|----------|------------------------|
| Run 12 | 4,096 | 1/3 (33%) | $0.0026 | ~$0.0009 | ~3,000 |
| Run 13 | 16,384 | 1/3 (33%) | $0.0054 | ~$0.0018 | ~3,000 |
| Run 16 | no cap | **0/3 (0%)** | **$0.0204** | **~$0.0068** | **~10,300** |

**Key findings:**

1. **More tokens = worse results.** At 4K and 16K, `input_0334` parsed (scoring 2.7% and 8.1% respectively). With no cap, even that case failed — the model generated so much reasoning text that it drifted further from ever producing structured output.

2. **Cost scales inversely with quality.** The no-cap run cost 7.5x more than the 4K run ($0.0068 vs $0.0009 per call) while delivering 0% parse rate instead of 33%.

3. **Output token estimation** (from Qwen 3.5 9B pricing ~$0.20/M input + $0.60/M output): the no-cap run generated ~10,300 output tokens per call — all plaintext reasoning, no JSON. The model fills whatever budget it's given with chain-of-thought text.

4. **Contrast with Llama 70B:** Llama's parse failures were a token budget issue — more tokens fixed them (67% → 100% parse, cost stayed flat at ~$0.0007/call). Qwen's failures are an instruction-following issue — more tokens make it worse because the model doesn't know when to stop reasoning and start outputting.

**Conclusion:** Qwen 3.5 9B is not viable for this benchmark at any token limit. The model fundamentally cannot follow the prompt's output format instructions. It generates plaintext reasoning regardless of `<think>` tag guidance, never transitions to JSON output, and consumes more tokens (and cost) the more room it's given. Recommended to drop from the model list.
