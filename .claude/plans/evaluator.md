# Plan: Benchmark Evaluator

## Context
Once the synthetic data generator produces test cases (input JSON + ground-truth expected output), we need tooling to:
1. Run the calculator on generated inputs and verify ground-truth consistency
2. Feed inputs to an LLM, collect its output, and score it section-by-section against ground truth

---

## Files

| File | Action |
|------|--------|
| `tests/run_generated_tests.py` | Create — runs calculator on each generated case, verifies `_expected` fields match |
| `tests/evaluate_llm.py` | Create — feeds inputs to LLM, compares LLM output to `_expected`, produces per-field scoring |

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

Feeds each test case input to an LLM via API, collects the output JSON, and scores it against `_expected`.

---

### Constants (top of script)

```python
MAX_TOOL_ROUNDS = 20          # max multi-turn tool-call rounds per case
TOLERANCE = 0.01              # numeric comparison tolerance
```

---

### Tool definition

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

The system prompt sent to the LLM includes:
1. Role statement and FY 2025-26 context
2. Instruction to use the `calculate` tool for ALL arithmetic — never mental math
3. Instruction to return ONLY the output JSON when done — no explanation unless asked
4. Encouragement to use parallel tool calls where independent calculations can run simultaneously
5. The exact output JSON schema (matching `_expected` structure from Script_output.json)

### NOT included in the system prompt (LLM must figure these out)

#### 80C / 80CCE combined cap rules
- Section 80C eligible items: PPF, EPF (employee contribution), ELSS, NSC, Sukanya Samriddhi Yojana, SCSS
- Section 80CCC: Pension scheme premium (annual = Amount / Number of Years Paid)
- Section 80CCD(1): NPS Tier-1 self contribution, capped at 10% of (Basic Salary + DA)
- **Combined 80CCE pool**: 80C + 80CCC + 80CCD(1) together capped at ₹1,50,000
- If the uncapped sum exceeds 1,50,000, scale each component proportionally so the total = 1,50,000
- 80CCD(1B): additional NPS self contribution beyond CCD(1), up to ₹50,000 (outside 80CCE cap)
- 80CCD(2): employer NPS contribution — 14% of (Basic+DA) for government employees, 10% for private (outside 80CCE cap)

-> this may vary thus for verification we have just seen the total dudction availed for all 3 sections

#### Capital loss set-off rules
Priority order for netting carry-forward losses:

| Loss type | Offsets (in priority order) | Cannot offset |
|---|---|---|
| STCL (111A) | STCG 111A → STCG Other → LTCG 112A → LTCG Non-Equity | Salary, Other Sources |
| STCL (Other) | STCG Other → STCG 111A → LTCG 112A → LTCG Non-Equity | Salary, Other Sources |
| LTCL (112A) | LTCG 112A → LTCG Non-Equity | Any STCG; non-capital-gains heads |
| LTCL (Other) | LTCG Non-Equity → LTCG 112A | Any STCG; non-capital-gains heads |

- STCL can offset any capital gain (short or long term) — STCG first, then LTCG
- LTCL can only offset LTCG — never STCG
- Carry-forward: up to 8 assessment years
- LTCG 112A and LTCG Non-Equity share a combined ₹1,25,000 exemption (112A uses it first, remainder available for Non-Equity)

-> this may vary, thus final values (total after deductions) are seen for STCG and LTCG respectively

#### Miscellaneous points
- New regime deduction restrictions
- HRA exemption 3-way min calculation
- 80D rules (cash exclusion, group insurance exclusion, beneficiary validation, senior limits)
- 80E 8-year window
- 80G donation rates (100% vs 50%) and cash >2k exclusion
- Vehicle always exempt
- Debt MF post-2023 slab-rate rule
- CII indexation and FY mapping

---

### Multi-turn conversation flow

```
Turn 1 (user):    System prompt + "Here is the input:\n" + input JSON
Turn 2 (assistant): LLM responds — may contain tool_calls or final JSON
Turn 3+ (tool):   If tool_calls present → execute all (parallel OK) → send results back
...repeat until assistant responds WITHOUT tool_calls or MAX_TOOL_ROUNDS hit...
Terminal:         Parse JSON from assistant's final response
```

- **Parallel tool calls**: When the LLM returns multiple tool calls in one response, execute all of them and return all results in a single tool-results message. This is standard in OpenAI/Anthropic APIs.
- **Round counting**: Each assistant→tool→assistant cycle = 1 round. Multiple parallel tool calls in one response = 1 round.
- **Cap hit**: If MAX_TOOL_ROUNDS is reached and no final answer, score the case as 0 on all fields.
- **Final answer parsing**: Extract the first valid JSON object from the terminal message (no tool calls). If no valid JSON found, score as 0 on all fields.

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
| 9 | Combined LTCG = LTCG (Section 112A) + LTCG (Non-Equity @ 12.5%).Total + LTCG (Other @ 20%) | sum of leaves |

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
| 25 | Tax on STCG (Section 111A) at 20% | leaf |
| 26 | Tax on STCG (Other) | leaf |
| 27 | Tax on LTCG (Section 112A) at 12.5% | leaf |
| 28 | Tax on LTCG (Non-Equity) at 12.5% | leaf |
| 29 | Tax on LTCG (Other) at 20% | leaf |
| 30 | Total Tax Before Rebate | leaf |
| 31 | Less: Rebate under Section 87A | leaf |
| 32 | Tax After Rebate | leaf |
| 33 | Surcharge | leaf |
| 34 | Health and Education Cess (4%) | leaf |
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

### Output report

Three outputs produced per evaluation run:

#### 1. Console summary (printed to stdout)
```
=== Evaluation Report: qwen-3.5-8b ===
Overall accuracy:    78.4% (312 cases)
Failed to parse:     5 cases (scored as 0)
Mean tool rounds:    8.3 per case

Per-section accuracy:
  Salary (7 fields):          92.1%
  Capital Gains (2 fields):   61.2%
  Other Sources (3 fields):   98.7%
  Aggregates (2 fields):      74.0%
  Deductions (9 fields):      73.5%
  Tax Computation (14 fields): 68.1%
```

#### 2. Per-case CSV (`tests/evaluation_results/<model_name>_results.csv`)
One row per test case. Columns:
- `case_file` — filename (e.g., `input_0001.json`)
- `description` — the `_description` string
- `model` — model name
- `rounds_used` — how many tool-call rounds
- `parsed` — 1 if valid JSON extracted, 0 if failed/cap-hit
- One column per scored field (37 columns): `gross_salary`, `sec_10_13a`, ..., `net_tax_payable` — values are 1 (correct) or 0 (wrong/missing)
- `total_score` — sum of the 37 field columns
- `total_pct` — total_score / 37

This is the primary file for analysis in pandas/R.

#### 3. Cross-model summary CSV (`tests/evaluation_results/summary.csv`)
One row per model. Columns:
- `model`
- `overall_accuracy` — average total_pct across all cases
- `salary_accuracy`, `capital_gains_accuracy`, `other_sources_accuracy`, `aggregates_accuracy`, `deductions_accuracy`, `tax_computation_accuracy` — per-section averages
- `mean_rounds` — average tool-call rounds
- `parse_fail_count` — number of cases that failed to parse
- `total_cases`

---

### Script structure

```python
# Constants
MAX_TOOL_ROUNDS = 20
TOLERANCE = 0.01
CHECKPOINT_DIR = "tests/evaluation_checkpoints"
RESULTS_DIR = "tests/evaluation_results"

MODELS = [
    "qwen-3.5-8b",
    "gemma-4",
    "llama-70b",
    "deepseek-v2",
    "deepseek-r1",
    "qwen-250b",
]

# Tool execution
def execute_calculate(operation: str, operands: list[float]) -> float

# LLM interaction
def build_system_prompt() -> str
def send_to_llm(model: str, messages: list[dict], tools: list[dict]) -> Response
def run_case(model: str, input_json: dict) -> tuple[dict | None, int]
    """Multi-turn loop. Returns (parsed_output_or_None, rounds_used)."""

# Checkpointing
def load_checkpoint(model: str) -> set[str]
    """Returns set of case filenames already completed for this model."""
def save_checkpoint(model: str, case_file: str, result: CaseResult)
    """Appends one completed case to the checkpoint file."""

# Scoring
def extract_scored_fields(output: dict) -> dict[str, float]
    """Extracts the 37 scored values (applying sums for combined fields)."""
def score_case(expected: dict, actual: dict | None) -> dict[str, int]
    """Returns {field_name: 0_or_1} for each of the 37 fields."""

# Reporting
def generate_report(model: str, results: list[CaseResult]) -> Report
def report_to_csv(model: str, results: list[CaseResult])
def generate_cross_model_summary(all_results: dict[str, list[CaseResult]])

if __name__ == "__main__":
    cases = load_cases("tests/generated/")
    all_results = {}
    for model in MODELS:
        completed = load_checkpoint(model)
        results = [load from checkpoint for already-completed cases]
        for case in cases:
            if case["file"] in completed:
                continue
            try:
                result = evaluate_case(model, case)
                save_checkpoint(model, case["file"], result)
                results.append(result)
            except (RateLimitError, APIError, KeyboardInterrupt):
                print(f"Stopped at case {case['file']} for {model}. "
                      f"Checkpoint saved. Re-run to resume.")
                break
        report_to_csv(model, results)
        all_results[model] = results
    generate_cross_model_summary(all_results)
```

---

## Implementation details (to resolve before coding)

### Models

| Model | Size | Notes |
|-------|------|-------|
| Qwen 3.5 | 8B | Small — may struggle with complex multi-step tax logic |
| Gemma 4 | ~12B | Google, relatively new |
| Llama | 70B | Meta, strong general reasoning |
| DeepSeek v2 | ~236B MoE | Strong coding/reasoning |
| DeepSeek R1 | ~671B MoE | Reasoning model — uses chain-of-thought internally |
| Qwen | 250B | Large Qwen variant |

### API provider

All 6 models are available via **OpenRouter** (openai-compatible API), which gives a single endpoint and unified tool-calling format. This means:
- One API client (openai SDK with `base_url` pointed at OpenRouter)
- One tool-calling format for all models
- Rate limits and pricing vary per model on OpenRouter

Alternative: host smaller models locally (Qwen 8B, Gemma 4) via Ollama/vLLM and use OpenRouter for the large ones. Trade-off: cheaper but adds infrastructure complexity.

### Tool-calling compatibility

**Concern**: Not all models handle native function calling equally well.

| Model | Native tool-call support (OpenRouter) | Risk |
|-------|--------------------------------------|------|
| Qwen 3.5 8B | Supported but flaky on small models | May produce malformed tool calls |
| Gemma 4 | Supported | Relatively new, needs testing |
| Llama 70B | Good support | Low risk |
| DeepSeek v2 | Good support | Low risk |
| DeepSeek R1 | Supported but reasoning-mode quirks | May "think" extensively before tool call, using more rounds |
| Qwen 250B | Good support | Low risk |

**Mitigation strategy**: Try native tool calling first. If a model consistently fails to produce valid tool calls (>50% parse failures in first 10 cases), the script logs a warning. No prompt-based fallback — if a model can't do tool calling, that's a valid benchmark finding.

### Checkpointing

Directory: `tests/evaluation_checkpoints/`

One JSONL file per model (e.g., `qwen-3.5-8b.jsonl`). Each line is one completed case:
```json
{"case_file": "input_0001.json", "rounds_used": 7, "parsed": true, "llm_output": {...}, "scores": {"gross_salary": 1, "sec_10_13a": 0, ...}, "total_score": 29}
```

On script start for a model:
1. Load its checkpoint JSONL if it exists
2. Build set of already-completed case filenames
3. Skip those cases, process only remaining ones
4. On any stoppage (rate limit, API error, Ctrl+C), the last completed case is already saved — next run picks up from the next case

This means: if you run the script, it hits a rate limit at case 150, you can re-run and it resumes from case 151.

### Open questions

- **OpenRouter vs self-hosted**: Use OpenRouter for all, or host small models locally? (Cost vs simplicity)
- **Rate limiting**: OpenRouter has per-model rate limits. Should the script add a configurable delay between cases? (Suggest: yes, `DELAY_BETWEEN_CASES = 1.0` second as default constant)
- **Retry on transient API errors**: Suggest 3 retries with exponential backoff before marking a case as failed (not 0-scored — just skipped so it's retried on next run)
