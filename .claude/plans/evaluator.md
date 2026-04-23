# Plan: Benchmark Evaluator

## Context
Once the synthetic data generator produces test cases (input JSON + ground-truth expected output), we need tooling to:
1. Run the calculator on generated inputs and verify ground-truth consistency
2. Feed inputs to an LLM, collect its output, and score it section-by-section against ground truth

### Thesis evaluation goal
We are looking for either or both of the following insights:
1. **All models perform badly** — anything less than 75% accuracy across the board
2. **Significant variation** — some models >90%, some <60–70%

Model selection is designed to maximise the chance of observing this variation.

---

## Files

| File | Action |
|------|--------|
| `tests/run_generated_tests.py` | Create — runs calculator on each generated case, verifies `_expected` fields match |
| `tests/tune_prompt.py` | Create — interactive prompt tuning tool; runs sample cases, shows failures, lets user iterate on the prompt |
| `tests/evaluate_llm.py` | Create — feeds inputs to LLM via 3 methods, compares output to `_expected`, produces per-field scoring |

---

## `run_generated_tests.py` — ground-truth verification

Validates that the generator and calculator agree (regression suite).

```
for each JSON in tests/generated/:
    load → extract _expected, _description
    input_only = strip meta fields (_description, _expected)
    result = tax_calculator.calculate(input_only)
    compare result to _expected field by field (recursive, tolerance 0.01)
    record pass/fail + first divergence

print summary: N passed / M failed
on failure: print case description + expected vs actual diff
```

### Verification
```bash
# Generate cases (pairwise by default)
python3 tests/generate_test_cases.py

# Count generated cases
ls tests/generated/*.json | wc -l

# Run verification (100% pass expected — ground truth from same calculator)
python3 tests/run_generated_tests.py
```

---

## `evaluate_llm.py` — LLM benchmark scoring

---

### Constants (top of script)

```python
MAX_TOOL_ROUNDS = 20          # tool-call method: max assistant→tool cycles per case
MAX_SCRIPT_RETRIES = 3        # script method: max error-fix cycles per case
SCRIPT_TIMEOUT = 20           # script method: seconds before killing subprocess
TOLERANCE = 0.01              # numeric comparison tolerance
DELAY_BETWEEN_CASES = 1.0     # seconds between API calls (rate-limit courtesy)
CHECKPOINT_DIR = "tests/evaluation_checkpoints"
RESULTS_DIR = "tests/evaluation_results"
```

All configurable via CLI flags (see CLI section) so that parameter sweeps (e.g., testing if more tool rounds improve accuracy) don't require code changes.

---

### Three evaluation methods

Executed in priority order: **zero-shot → script → tool-call**. Each method is run independently for all models before moving to the next.

#### Method 1: Zero-shot

Single turn. System prompt + input JSON → LLM responds → parse JSON from response.

```
Turn 1 (user):    System prompt + input JSON
Turn 2 (assistant): LLM responds with output JSON
→ Parse first valid JSON object from response
→ If no valid JSON found, score as 0 on all fields
```

No retries, no follow-up. If the model can't produce valid JSON in one shot, that's a data point.

#### Method 2: Script

LLM writes a Python script that reads the input JSON from a temp file, computes the tax output, and prints the result JSON to stdout. Multi-turn only if the script errors out.

```
Turn 1 (user):     System prompt + input JSON + instruction to write a Python script
                   "The input JSON is at: /tmp/tax_input.json"
                   "Write a Python script that reads it, computes the output, and prints ONLY the output JSON to stdout."
Turn 2 (assistant): LLM responds with Python code block
→ Extract code from response, write to temp.py file
→ Execute: subprocess.run(["python3", script_path], timeout=SCRIPT_TIMEOUT, capture_output=True)
→ If exit code 0: take stdout as the output JSON — done (no further LLM turn)
→ If error (non-zero exit, timeout, syntax error):
    Turn 3 (user):     Send stderr/error message back to LLM
    Turn 4 (assistant): LLM responds with fixed script
    → Re-extract, re-execute
    → Repeat up to MAX_SCRIPT_RETRIES error-fix cycles
→ If all retries exhausted: score as 0 on all fields
```

**Key details:**
- **Sandboxing**: Script runs in an isolated temp directory (`tempfile.mkdtemp()`) containing only the input JSON file. `subprocess.run()` uses `cwd=temp_dir`. The model has no access to project files (`tax_calculator.py`, test cases, expected outputs). This prevents the LLM from importing the calculator to produce a perfect score.
- Input passed via temp file in the sandbox directory (more reliable than stdin — avoids encoding issues and LLM not handling stdin correctly)
- Available libraries: Python standard library only
- The LLM's script must print the output JSON directly — no further LLM turn to restructure
- Only retry on errors (non-zero exit code). If the script runs successfully but produces malformed JSON, that's a data point (scored as 0)

#### Method 3: Tool-call

Multi-turn with the `calculate` tool. LLM calls the tool iteratively until it returns a final JSON response with no tool calls.

```
Turn 1 (user):    System prompt + input JSON
Turn 2 (assistant): LLM responds — may contain tool_calls or final JSON
Turn 3+ (tool):   If tool_calls present → execute all (parallel OK) → send results back
...repeat until assistant responds WITHOUT tool_calls or MAX_TOOL_ROUNDS hit...
Terminal:         Parse JSON from assistant's final response
```

- **Parallel tool calls**: When the LLM returns multiple tool calls in one response, execute all and return all results in a single tool-results message
- **Round counting**: Each assistant→tool→assistant cycle = 1 round. Multiple parallel tool calls in one response = 1 round
- **Cap hit**: If MAX_TOOL_ROUNDS reached and no final answer, score as 0 on all fields
- **Final answer parsing**: Extract first valid JSON object from terminal message

---

### Tool definition (tool-call method only)

Single tool exposed to the LLM:

```json
{
  "name": "calculate",
  "description": "Performs arithmetic. Supports: add, subtract, multiply, divide (floating-point). Operands list can have 2+ values. Operations are left-associative: subtract(10, 3, 2) = (10 - 3) - 2 = 5. divide(100, 4, 5) = (100 / 4) / 5 = 5.0. You may request multiple calculate calls in parallel within a single response.",
  "parameters": {
    "type": "object",
    "properties": {
      "operation": {
        "type": "string",
        "enum": ["add", "subtract", "multiply", "divide"]
      },
      "operands": {
        "type": "array",
        "items": { "type": "number" },
        "minItems": 2
      }
    },
    "required": ["operation", "operands"]
  }
}
```

Execution logic:
```python
def execute_calculate(operation, operands):
    result = operands[0]
    for x in operands[1:]:
        if operation == "add":
            result += x
        elif operation == "subtract":
            result -= x
        elif operation == "multiply":
            result *= x
        elif operation == "divide":
            result /= x       # float division always
    return round(result, 10)   # avoid floating-point display noise
```

---

### System prompt

#### Common across all methods
1. Role statement: "You are an Indian income tax calculator for FY 2025-26 (AY 2026-27)."
2. The exact output JSON schema (matching structure from Script_output.json - to be attached)
3. "Return ONLY a valid JSON object matching the schema. No explanation, no preamble, no markdown formatting around the JSON."
4. Input field interpretation guide (semantics only, not tax rules):
   - `FMV as of 31 Jan 2018` — Fair Market Value of the stock on 31-Jan-2018
   - `Pension Scheme Premium → Number of Years Paid` — Multi-year premium if number > 1
   - `Health Insurance → Number of Years Paid` — Multi-year premium if number > 1
   - `Education Loan Interest → Year of Repayment` — Nth year of the repayment schedule (e.g. 1 = first year, 5 = fifth year), not a calendar or fiscal year
   - `Held for duration in years` (Vehicle, Bonds, Debentures, G-Secs) — Integer years held
   - `Health Insurance → Paid By` — Who paid: "self" = individual pays; "group medical insurance" = employer-provided coverage
   - `Stock Sale Transactions → STT` — Securities Transaction Tax paid
   - `Long/Short Term Capital Loss → Financial Year` — The FY the loss was incurred, format "YYYY-YY" (e.g. "2020-21")
   - `Mutual Fund Transactions → Type` — One of: equity, debt, elss, gold-etf, gold-mf, international, hybrid-equity

#### Method-specific additions
- **Zero-shot**: No additional instructions. The LLM must compute everything from its training knowledge.
- **Script**: "Write a Python script that reads the input JSON from the file path provided, computes the tax output, and prints ONLY the output JSON to stdout. You have access to the Python standard library only."
- **Tool-call**: "Use the `calculate` tool for ALL arithmetic — never perform mental math. You may request multiple calculate calls in parallel when calculations are independent."

#### NOT included in the system prompt (LLM must figure these out)
All tax rules — the system prompt contains ONLY the role, output schema, and method-specific instructions. The LLM must rely on its training data for:
- 80C / 80CCE combined cap rules and proportional scaling
- Capital loss set-off rules and priority order
- New regime deduction restrictions
- HRA exemption 3-way min calculation
- 80D rules (cash exclusion, group insurance exclusion, beneficiary validation, senior limits)
- 80E 8-year window
- 80G donation rates (100% vs 50%) and cash >2k exclusion
- Vehicle always exempt
- Debt MF post-2023 slab-rate rule
- CII indexation and FY mapping
- Slab rates for both regimes
- Surcharge rates and marginal relief
- 87A rebate and marginal relief

#### Prompt tuning strategy (before benchmark execution)

The system prompt must be tuned for maximum JSON adherence before running the full benchmark:

1. **Pick the weakest model** (likely `nvidia/nemotron-nano-9b-v2:free` or `openai/gpt-oss-20b:free`)
2. Run 5–10 sample cases and observe failure modes:
   - Does it wrap JSON in markdown code fences? → Add "No ```json fences"
   - Does it add preamble text? → Strengthen "Return ONLY..."
   - Does it use wrong key names? → Provide schema more explicitly (JSON Schema format, not just example)
   - Does it omit sections? → List all required top-level keys
3. Iterate the prompt until the weakest model reliably produces parseable JSON (even if values are wrong)
4. **Freeze the prompt** and use it identically for all models — this is the "fair baseline"
5. If a model still fails to produce valid JSON after tuning, that failure is a legitimate benchmark data point

---

### Scoring approach

#### Scored fields (37 fields, 1 point each)

**Under Head Salaries (7 fields):**
| # | Field | Type |
|---|-------|------|
| 1 | Gross Salary | leaf |
| 2 | Section 10(13A) (HRA exemption) | leaf |
| 3 | Section 10(5) (LTA exemption) | leaf |
| 4 | Section 16(ia) (standard deduction) | leaf |
| 5 | Section 16(ii) (entertainment allowance) | leaf |
| 6 | Section 16(iii) (professional tax) | leaf |
| 7 | Net Salary | leaf |

**Capital Gains (2 combined fields):**
| # | Field | Type |
|---|-------|------|
| 8 | Combined STCG = STCG (Section 111A) + STCG (Other).Total | sum of leaves |
| 9 | Combined LTCG = LTCG (Section 112A) + LTCG (Non-Equity).Total + LTCG (Other) | sum of leaves |

**Income from Other Sources (3 fields):**
| # | Field | Type |
|---|-------|------|
| 10 | Savings Bank Interest | leaf |
| 11 | Deposit Interest | leaf |
| 12 | Other Interest → EPF Taxable Interest | leaf |

**Aggregates (2 fields):**
| # | Field | Type |
|---|-------|------|
| 13 | Gross Total Income | leaf |
| 14 | Total Taxable Income | leaf |

**Deductions (9 fields):**
| # | Field | Type |
|---|-------|------|
| 15 | 80C + 80CCC + 80CCD(1) combined | sum of 3 leaves |
| 16 | 80CCD(1B) | leaf |
| 17 | 80CCD(2) | leaf |
| 18 | 80D | leaf |
| 19 | 80E | leaf |
| 20 | 80G | leaf |
| 21 | 80TTA | leaf |
| 22 | 80TTB | leaf |
| 23 | Total Deductions | leaf |

**Tax Computation (14 fields):**
| # | Field | Type |
|---|-------|------|
| 24 | Tax at Slab Rates | leaf |
| 25 | Tax on STCG (Section 111A) | leaf |
| 26 | Tax on STCG (Other) | leaf |
| 27 | Tax on LTCG (Section 112A) | leaf |
| 28 | Tax on LTCG (Non-Equity) | leaf |
| 29 | Tax on LTCG (Other) | leaf |
| 30 | Total Tax Before Rebate | leaf |
| 31 | Less: Rebate under Section 87A | leaf |
| 32 | Tax After Rebate | leaf |
| 33 | Surcharge | leaf |
| 34 | Health and Education Cess | leaf |
| 35 | Total Tax Liability | leaf |
| 36 | Less: TDS | leaf |
| 37 | Net Tax Payable / Refund | leaf |

#### Scoring rules
- **Numeric tolerance**: `abs(expected - actual) <= 0.01` → correct (1 point), else 0
- **Combined fields**: Sum the relevant expected leaves, sum the relevant actual leaves, compare the sums with tolerance
- **Missing field in LLM output**: 0 points for that field
- **Per-case score**: sum of points / 37
- **Overall score**: average of per-case scores across all test cases

---

### Output reports

#### Per-model-method CSV (`tests/evaluation_results/<model_slug>_<method>_results.csv`)
One row per test case. Columns:
- `case_file`, `description`, `model`, `method`
- `rounds_used` (tool-call: tool rounds; script: retry count; zero-shot: always 1)
- `parsed` — 1 if valid JSON extracted, 0 if failed/cap-hit
- `latency_sec` — wall-clock time from first API call to final answer (seconds, 2 decimal places)
- `prompt_tokens` — total input tokens across all turns in this case
- `completion_tokens` — total output tokens across all turns in this case
- `total_tokens` — prompt_tokens + completion_tokens
- 37 scored-field columns (1/0 each)
- 37 `_pct_error` columns (one per scored field): `abs(expected - actual) / max(abs(expected), 1)` — supplementary error magnitude for richer thesis analysis. 0.0 when scored 1 (correct). Allows distinguishing "wrong surcharge bracket" (50% off) from "rounding error" (0.001% off) without changing the primary binary scoring.
- `total_score`, `total_pct`

**Token counting**: OpenRouter returns `usage.prompt_tokens` and `usage.completion_tokens` in every response. For multi-turn methods (tool-call, script), sum across all turns in a case.

#### Per-method summary CSV (`tests/evaluation_results/<method>_summary.csv`)
One row per model. Columns:
- `model`, `overall_accuracy`
- `salary_accuracy`, `capital_gains_accuracy`, `other_sources_accuracy`, `aggregates_accuracy`, `deductions_accuracy`, `tax_computation_accuracy`
- `mean_rounds`, `parse_fail_count`, `total_cases`
- `mean_latency_sec` — average wall-clock time per case
- `mean_prompt_tokens`, `mean_completion_tokens`, `mean_total_tokens` — average tokens per case
- `total_prompt_tokens`, `total_completion_tokens` — sum across all cases (total cost indicator)

Generated when all models complete for a given method. Can be generated independently (e.g., just `zero-shot_summary.csv` after the zero-shot run).

#### Cross-method pivot CSV (`tests/evaluation_results/cross_method_summary.csv`)
Models as rows, methods as columns. Three values per cell: accuracy / mean tokens / mean latency.

| model | zero-shot (acc / tok / sec) | script (acc / tok / sec) | tool-call (acc / tok / sec) |
|-------|-----------|--------|-----------|
| openai/gpt-oss-120b:free | 82.1% / 1.2k / 3.1s | 91.3% / 4.8k / 8.2s | 94.7% / 12.3k / 22.1s |
| nvidia/nemotron-nano-9b-v2:free | 31.4% / 0.9k / 2.4s | 55.2% / 3.1k / 6.8s | 48.9% / 8.7k / 18.3s |
| ... | ... | ... | ... |

This shows the accuracy-vs-cost tradeoff at a glance: does the improvement from zero-shot → tool-call justify the extra tokens/latency?

Generated only when results exist for all three methods.

#### Console summary (printed to stdout)
```
=== Evaluation Report: openai/gpt-oss-120b:free [tool-call] ===
Overall accuracy:    82.1% (569 cases)
Failed to parse:     12 cases (scored as 0)
Mean tool rounds:    8.3 per case

Per-section accuracy:
  Salary (7 fields):            92.1%
  Capital Gains (2 fields):     61.2%
  Other Sources (3 fields):     98.7%
  Aggregates (2 fields):        74.0%
  Deductions (9 fields):        73.5%
  Tax Computation (14 fields):  68.1%

Cost / efficiency:
  Mean latency:          22.1 sec/case
  Mean tokens:           12,340 total (2,180 prompt + 10,160 completion)
  Total tokens (all cases): 7,017,460
```

---

### CLI interface

```bash
# Defaults: method=zero-shot, all models, default constants
python3 tests/evaluate_llm.py

# Run a specific method for all models
python3 tests/evaluate_llm.py --method zero-shot
python3 tests/evaluate_llm.py --method script
python3 tests/evaluate_llm.py --method tool-call

# Run a specific model only
python3 tests/evaluate_llm.py --method tool-call --model "openai/gpt-oss-120b:free"

# Override constants for parameter sweeps
python3 tests/evaluate_llm.py --method tool-call --max-rounds 30
python3 tests/evaluate_llm.py --method script --max-script-retries 5 --script-timeout 30
```

| Flag | Default | Description |
|------|---------|-------------|
| `--method` | `zero-shot` | One of: `zero-shot`, `script`, `tool-call` |
| `--model` | (all models) | OpenRouter model ID; if omitted, runs all models |
| `--max-rounds` | 20 | Tool-call method: max tool-call rounds per case |
| `--max-script-retries` | 3 | Script method: max error-fix cycles per case |
| `--script-timeout` | 20 | Script method: seconds before killing subprocess |
| `--delay` | 1.0 | Seconds between API calls |

---

### Script structure

```python
MODELS = [
    # Tier 1: High accuracy candidates (>90% expected)
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    # Tier 2: Variable / mid-tier
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    # Tier 3: Likely low accuracy (<70% expected)
    "nvidia/nemotron-nano-9b-v2:free",
    "openai/gpt-oss-20b:free",
]

# Method dispatch
def run_zero_shot(model, input_json) -> dict | None
def run_script(model, input_json) -> tuple[dict | None, int]
def run_tool_call(model, input_json) -> tuple[dict | None, int]

# System prompts
def build_system_prompt(method: str) -> str
    """Common base (role + schema) + method-specific instructions."""

# Tool execution (tool-call method only)
def execute_calculate(operation: str, operands: list[float]) -> float

# Script execution (script method only)
def extract_code(response_text: str) -> str
def execute_script(code: str, input_path: str) -> tuple[str, str, int]
    """Returns (stdout, stderr, exit_code). Kills after SCRIPT_TIMEOUT."""

# LLM interaction
def send_to_llm(model: str, messages: list[dict], tools: list[dict] | None) -> Response

# Checkpointing — per (model, method) pair
def checkpoint_key(model: str, method: str) -> str
    """e.g. 'openai_gpt-oss-120b_free__zero-shot.jsonl'"""
def load_checkpoint(model: str, method: str) -> set[str]
def save_checkpoint(model: str, method: str, case_file: str, result: CaseResult)

# Scoring
def extract_scored_fields(output: dict) -> dict[str, float]
def score_case(expected: dict, actual: dict | None) -> dict[str, int]

# Reporting
def report_per_model_method_csv(model, method, results)
def report_method_summary_csv(method, all_model_results)
def report_cross_method_pivot(all_results)

if __name__ == "__main__":
    args = parse_cli()
    method = args.method                           # "zero-shot" | "script" | "tool-call"
    models = [args.model] if args.model else MODELS
    cases = load_cases("tests/generated/")

    for model in models:
        completed = load_checkpoint(model, method)
        results = [load from checkpoint for already-completed cases]
        for case in cases:
            if case["file"] in completed:
                continue
            try:
                result = evaluate_case(model, method, case)
                save_checkpoint(model, method, case["file"], result)
                results.append(result)
            except (RateLimitError, APIError, KeyboardInterrupt):
                print(f"Stopped at {case['file']} for {model} [{method}]. "
                      f"Checkpoint saved. Re-run to resume.")
                break
        report_per_model_method_csv(model, method, results)

    # Generate method-level summary if all models complete
    report_method_summary_csv(method, all_model_results)
```

---

## Implementation details

### Models

All models accessed via **OpenRouter** (OpenAI-compatible API) using free-tier endpoints.

| Tier | Model (OpenRouter ID) | Size | Expected accuracy | Rationale |
|------|----------------------|------|-------------------|-----------|
| 1 — High | `openai/gpt-oss-120b:free` | 117B | >90% | Large model optimised for high-reasoning tasks |
| 1 — High | `meta-llama/llama-3.3-70b-instruct:free` | 70B | >90% | Gold standard for open-weight instruction following |
| 2 — Mid | `google/gemma-4-31b-it:free` | 31B dense | 70–90% | Newer dense model; may struggle with Indian tax edge cases |
| 2 — Mid | `nvidia/nemotron-3-super-120b-a12b:free` | 120B MoE (12B active) | 70–90% | 120B total but only 12B active parameters; effective capacity between Tier 1 and Tier 3 |
| 3 — Low | `nvidia/nemotron-nano-9b-v2:free` | 9B | <70% | Too small for multi-step tax reasoning |
| 3 — Low | `openai/gpt-oss-20b:free` | 20B | <70% | Much smaller/weaker than 120B sibling |

**API settings**: `temperature=0` for all models (deterministic output for reproducibility).

### API provider

OpenRouter with openai SDK:
```python
from openai import OpenAI
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
```
- Single endpoint, unified tool-calling format for all models
- `OPENROUTER_API_KEY` read from environment variable
- Rate limits vary per model; `DELAY_BETWEEN_CASES` provides courtesy spacing

### Tool-calling compatibility

| Model | Native tool-call support | Risk |
|-------|-------------------------|------|
| openai/gpt-oss-120b:free | Good | Low |
| meta-llama/llama-3.3-70b-instruct:free | Good | Low |
| google/gemma-4-31b-it:free | Supported | Medium — newer model |
| nvidia/nemotron-3-super-120b-a12b:free | Supported | Medium — MoE with 12B active |
| nvidia/nemotron-nano-9b-v2:free | Supported but small | High — may produce malformed calls |
| openai/gpt-oss-20b:free | Supported | Medium — smaller model |

No prompt-based fallback. If a model can't do tool calling, that's a valid benchmark finding for the tool-call method.

### Checkpointing

Directory: `tests/evaluation_checkpoints/`

One JSONL file per **(model, method)** pair. Filename: `<model_slug>__<method>.jsonl`
(model slug: OpenRouter ID with `/` and `:` replaced by `_`)

Example: `openai_gpt-oss-120b_free__tool-call.jsonl`

Each line is one completed case:
```json
{"case_file": "input_0001.json", "rounds_used": 7, "parsed": true, "llm_output": {...}, "scores": {"gross_salary": 1, "sec_10_13a": 0, ...}, "total_score": 29, "latency_sec": 18.42, "prompt_tokens": 2180, "completion_tokens": 10160, "total_tokens": 12340, "messages": null}
```

Behaviour:
1. On start: load checkpoint → build set of completed case filenames → skip those
2. Each completed case appended immediately to JSONL
3. On any stoppage (rate limit, API error, Ctrl+C): already-saved cases are safe, next run resumes from the next unprocessed case
4. **Failed case transcripts**: For cases where `parsed=false` or `total_score < 19` (below 50%), the `messages` field stores the full conversation transcript (all API messages). For passing cases, `messages` is null to save space.

### Prompt tuning (pre-benchmark) — `tests/tune_prompt.py`

Separate interactive script. Human stays in the loop throughout — automated tuning risks accidentally adding tax-logic hints.

#### How the script works

```bash
# Each run tests all 3 tiers (weak + mid + strong) together
# Default: 5 cases, zero-shot method
python3 tests/tune_prompt.py

# Override cases or method
python3 tests/tune_prompt.py --method script --cases 5
python3 tests/tune_prompt.py --method tool-call --cases 5
```

The script always runs 3 models in a single invocation — one from each tier:
- Weak: `nvidia/nemotron-nano-9b-v2:free`
- Mid: `google/gemma-4-31b-it:free`
- Strong: `meta-llama/llama-3.3-70b-instruct:free`

This costs only 5 cases × 3 models = 15 API calls per iteration and catches tier-specific issues in one go (e.g., fixing something for weak that breaks strong).

**Flow per run:**
1. Load the current system prompt from `tests/prompts/system_prompt.txt`
2. Pick 5 random cases from `tests/generated/` (same 5 used for all 3 models)
3. For each model × case:
   - Send to the model using the current prompt and selected method
   - Attempt to parse the JSON from the response
   - Display:
     - **Parse status**: OK / FAIL (with the raw response text on failure)
     - **Key-name check**: list any keys in the response that don't match the schema
     - **Score** (if parseable): field-by-field comparison against `_expected`
4. Print a per-model summary:
   - Parse success rate: X/5
   - Common failure patterns (e.g., "2/5 had markdown fences")
   - Mean score on successfully parsed cases

**The user then:**
- Edits `tests/prompts/system_prompt.txt` manually
- Re-runs the script to see if the change helped across all 3 tiers
- Repeats until satisfied, then freezes the prompt

#### Prompt file and version tracking

Directory: `tests/prompts/`

```
tests/prompts/
├── system_prompt.txt      # single prompt file — used by all methods and models
└── tuning_log.jsonl       # append-only log of each tuning run
```

One prompt file for all methods. Method-specific instructions (tool-call usage, script-writing instructions) are appended programmatically by `evaluate_llm.py` and `tune_prompt.py` — they are not part of the tunable prompt.

`tuning_log.jsonl` — one line per tuning run, capturing prompt progression:
```json
{
  "timestamp": "2026-04-23T14:30:00",
  "method": "zero-shot",
  "prompt_hash": "a1b2c3d4",
  "cases_tested": 5,
  "results": {
    "nvidia/nemotron-nano-9b-v2:free": {"parse_rate": 0.6, "mean_score": 0.32, "failures": ["markdown_fences: 2"]},
    "google/gemma-4-31b-it:free": {"parse_rate": 0.8, "mean_score": 0.51, "failures": ["preamble_text: 1"]},
    "meta-llama/llama-3.3-70b-instruct:free": {"parse_rate": 1.0, "mean_score": 0.74, "failures": []}
  },
  "change_description": "Added explicit 'No markdown code fences' instruction"
}
```

This log gives a clear progression for the paper: each iteration shows parse-failure rate across all 3 tiers, with the exact change made.

#### Tuning process

Each iteration:
1. Edit `tests/prompts/system_prompt.txt`
2. Run `python3 tests/tune_prompt.py` (tests weak + mid + strong on same 5 cases)
3. Review results — common failures to address:
   - Markdown code fences around JSON → add "No code fences"
   - Preamble text before JSON → strengthen "Return ONLY a valid JSON object"
   - Wrong key names → use JSON Schema format in prompt, not just an example
   - Missing sections → explicitly list all required top-level keys
4. Repeat until all 3 tiers reliably produce parseable JSON (even if values are wrong)
5. **Freeze the prompt** → used identically for all models, all methods
6. Remaining parse failures after tuning are legitimate benchmark data points

#### Paper justification
The prompt tuning process and its results should be documented in the paper (Methodology section):
- The prompt was optimised for **format adherence only**, not for tax-logic accuracy
- Any remaining parse failures are genuine model limitations, not prompt engineering failures
- The same prompt was used for all models → fair comparison
- Include the progression from `tuning_log.jsonl`: parse-failure rate improving at each iteration across weak/mid/strong tiers, as evidence the prompt is not the bottleneck

### Future parameter sweeps

The script's constants are all exposed as CLI flags, enabling sweeps like:
- Does increasing `--max-rounds` from 20 to 40 improve tool-call accuracy?
- Does increasing `--max-script-retries` from 3 to 5 help script method?
- Does a longer `--script-timeout` (30s vs 20s) help complex cases?

These sweeps can be run per-model to identify model-specific optimal settings, though the primary benchmark should use fixed constants for fair comparison.

### Rate limiting and error handling

**Rate limiting**: OpenRouter free-tier models have per-minute and per-day limits that vary by model.

Strategy (layered):
1. **Baseline delay**: `DELAY_BETWEEN_CASES` (default 1.0s) between every API call — provides courtesy spacing
2. **429 detection**: On HTTP 429 (rate limit), read the `Retry-After` header if present. If absent, use exponential backoff: 5s → 15s → 45s → 120s
3. **Automatic slowdown**: If 3 consecutive 429s occur for the same model, double `DELAY_BETWEEN_CASES` for that model for the rest of the run
4. **Daily limit hit**: Some free models have daily caps. If a 429 response body contains "daily limit" or similar, stop that model and move to the next. The checkpoint ensures it can be resumed the next day.

**Transient API errors** (500, 502, 503, timeout):
1. Retry up to 3 times with exponential backoff: 2s → 8s → 32s
2. If all 3 retries fail, **skip the case** (don't write to checkpoint) so it's retried on the next run
3. Log the error with case file and model name for debugging
4. After 5 consecutive skipped cases for the same model, pause and ask the user (print a warning and continue to next model)

**KeyboardInterrupt (Ctrl+C)**:
- Caught at the case loop level. The last *completed* case is already checkpointed. Print which case was in progress and exit cleanly.

---

## Decisions during Implementation

Findings from testing all 6 models with a minimal prompt ("Return only this JSON: {\"x\": 42}"):

### 1. Cost model confirmed free
All `:free` endpoints returned `"cost": 0` in the response. However, the credits endpoint showed a small usage delta (~$0.015 across 8 calls) — this appears to be noise/rounding from prior sessions, not actual charges from free models. **Decision**: Removed per-API-call cost checking. Instead, the cost guard captures the initial usage balance at script start and checks the credits endpoint every 5 completed cases. If >$0.01 has been spent since start, it halts with an error.

### 2. Response field handling
Models return JSON in different fields:
- **gpt-oss-120b, gpt-oss-20b**: `content` has the JSON, `reasoning` has short chain-of-thought
- **gemma-4-31b**: `content` only, no reasoning
- **nemotron-nano-9b**: `content` may be None with all output in `reasoning` when max_tokens is too low. With sufficient tokens, `content` has JSON and `reasoning` has long chain-of-thought
- **nemotron-3-super**: `content` has JSON, `reasoning` has chain-of-thought. May contain control characters in response body

**Decision**: `get_response_text()` prefers `content`, falls back to `reasoning` if content is empty/None. `extract_json()` already handles fences, preamble, and brace-matching so it strips reasoning preamble naturally.

### 3. What we store in checkpoint per case
```json
{
  "case_file": "input_0001.json",
  "rounds_used": 7,
  "parsed": true,
  "llm_output": {full parsed JSON dict or null},
  "scores": {field_name: 0_or_1 for all 37 fields},
  "pct_errors": {field_name: float for all 37 fields},
  "total_score": 29,
  "latency_sec": 18.42,
  "prompt_tokens": 2180,
  "completion_tokens": 10160,
  "total_tokens": 12340,
  "messages": [truncated conversation transcript or null]
}
```
- `llm_output`: Full parsed output JSON for debugging incorrect fields. Null if parse failed.
- `messages`: Full conversation transcript (assistant content truncated to 500 chars) stored ONLY for failed/low-score cases (parse_fail or score < 19/37). Null for passing cases to save space.
- `pct_errors`: Per-field `abs(expected - actual) / max(abs(expected), 1)` for richer analysis.

### 4. Llama 3.3 70B availability
`meta-llama/llama-3.3-70b-instruct:free` returned persistent 429 upstream rate-limit errors from the Venice provider during testing. This is a free-tier upstream throttle, not our rate limit. The retry/backoff logic handles this, but the model may be unreliable during high-traffic periods. Will proceed with it in the model list since the retry logic accommodates intermittent 429s.

---

## To be done 

### Tool-call method

These items are deferred until zero-shot and script methods are implemented and running:

- **MAX_TOOL_ROUNDS sufficiency**: Log cases where the round cap is hit so we can determine if 20 rounds is enough or if it's truncating complex cases (surcharge marginal relief, multi-bucket loss netting). Adjust cap based on data.
- **Rate limiting for tool-call**: Tool-call generates 10+ API calls per case. The current rate-limit handling (429 backoff, auto-slowdown) works for zero-shot/script but may need per-model delay overrides for tool-call to avoid constant throttling on free-tier limits.
- **Runtime estimate for tool-call**: 500 cases × 6 models × ~8–10 rounds avg = ~27,000 API calls. At free-tier limits (~10–20 req/min), ~1.4 hours per model, ~8.5 hours total. Consider running models in parallel (separate terminal sessions with `--model X --method tool-call`).

### To be considered

- **Runtime estimate for zero-shot + script**: Zero-shot = 500 × 6 = 3,000 API calls (~1 call/case). Script = 500 × 6 × ~2 avg = ~6,000 calls. At 1s delay + rate limits, estimate ~1.5–3 hours for zero-shot, ~3–6 hours for script. Plan for ~5–9 hours total for both methods across all models.
- **Additional models**: The following free models were deferred from the initial 6-model comparison and can be added later to expand coverage:
  - `qwen/qwen3-coder:free` — coding-specialist model; likely strong on script method, variable on zero-shot
  - `minimax/minimax-m2.5:free` — strong in planning; financial math performance unknown
  - `inclusionai/ling-2.6-flash:free` — lower intelligence index (26.2/100); expected Tier 3
