# TaxBench-IN

A deterministic benchmark for evaluating whether large language models can compute a
complete Indian income tax return (FY 2025-26 / AY 2026-27, old and new regimes).

- **AY2026-Bench**: 569 synthetic taxpayer profiles across 10 archetypes, generated with
  pairwise covering arrays over 19 tax parameters.
- **Ground truth** from a rule-based Python tax engine, covered by 36 unit tests and
  spot-checked against the Income Tax Department's online calculator.
- **Field-level scoring**: 35 output fields, each correct only if within ₹0.01 of the answer key.
- **Three methods**: zero-shot (answer the JSON directly), script (write and run Python),
  and tool-call (use a calculator tool).

## Results

Field-level accuracy (%) on all 569 cases; in brackets, cases with all 35 fields correct.

| Model | Zero-shot | Script | Tool-call |
|---|---|---|---|
| Kimi K3.1 Pro | **77.8** (63) | **77.6** (69) | **78.0** (62) |
| Nemotron 3 Ultra 550B-A55B | 63.0 (2) | 64.9 (5) | 59.4 (3)² |
| Mistral Large 4 | 58.9 (3) | 61.7 (4)¹ | 59.4 (3) |
| GPT-OSS 120B | 52.1 (0) | 50.0 (0) | 44.1 (1) |
| MiniMax M3.1 Flash | 49.2 (4) | 49.2 (1) | 49.7 (1) |
| DeepSeek-R1-Distill-Llama-70B | 37.5 (0) | 38.4 (0) | 34.0 (0) |

¹ 568 cases: one request never returned a response.
² 244 cases via OpenRouter and 325 via NVIDIA NIM, same model and prompts; the CSVs list the
two routes as separate rows.

Errors concentrate at the end of the computation chain: a single upstream mistake, most
often leaving the employer's NPS contribution out of gross salary, breaks every total
computed from it. Writing code or calling a calculator tool raises no model's accuracy by
more than 3 points. Per-section results are in `tests/evaluation_results/`.

## Repository layout

```
tax_calculator.py              Ground-truth tax engine
calculator_tests/              Unit tests for the engine (one rule or edge case each)
tests/
  generate_test_cases.py       Dataset generator (archetypes + pairwise covering arrays)
  generated/                   AY2026-Bench: input_0001.json ... input_0569.json
  run_generated_tests.py       Checks every stored answer key against the engine
  check_invariants.py          Answer-key consistency checks that need no oracle
  prompts/system_prompt.txt    System prompt shared by all methods
  evaluate_llm.py              Evaluation harness (all three methods, scoring, checkpoints)
  rescore.py                   Re-scores stored model outputs against the current answer key
  evaluation_checkpoints/      Every model answer, one JSON line per case
  evaluation_results/          Per-model CSVs and method summaries
docs/ground_truth_validation/  The four cases checked on the Income Tax Department's calculator
CHANGELOG.md                   Every ground-truth correction and its effect on scores
```

## Setup

```bash
pip install -r requirements.txt
```

Python 3.10+. The tax engine, tests and rescoring use only the standard library.

## Reproducing the results

The stored checkpoints contain every model answer, so all reported numbers can be rebuilt
offline:

```bash
python3 calculator_tests/run_tests.py     # 36 engine unit tests
python3 tests/run_generated_tests.py      # 569 answer keys match the engine
python3 tests/check_invariants.py         # answer-key consistency checks
python3 tests/rescore.py                  # rebuild every CSV in tests/evaluation_results/
```

`python3 tests/rescore.py --dry-run` reports whether any stored score differs from a fresh
scoring of the same answer, without writing anything.

## Running a model

```bash
export NVIDIA_API_KEY=...          # models prefixed nim/
export OPENROUTER_API_KEY=...      # models without a prefix
export LLAMACPP_BASE_URL=http://localhost:8080/v1   # models prefixed llamacpp/

python3 tests/evaluate_llm.py --method zero-shot --model nim/moonshotai/kimi-k3.1-pro
python3 tests/evaluate_llm.py --method script    --model llamacpp/gpt-oss-120b
python3 tests/evaluate_llm.py --method tool-call --model nvidia/nemotron-3-ultra-550b-a55b:free
```

Runs resume from their checkpoint. `--shard k/n` runs every n-th case from offset k-1 into a
separate checkpoint, so several processes or API keys can share one run;
`python3 tests/evaluate_llm.py --help` lists all options. All models run at temperature 0.

## Using the tax engine directly

```bash
python3 tax_calculator.py tests/generated/input_0004.json output.json
```

The input can be a case file or a bare taxpayer object (a case's `input`); the output has the
same structure as the case's `_expected`. Slab rates, rebate thresholds and other constants
for the financial year are defined at the top of `tax_calculator.py`.

## Regenerating the dataset

```bash
python3 tests/generate_test_cases.py profiles
```

This rewrites `tests/generated/` with fresh inputs, which invalidates the stored model
answers. To change only the answer key after an engine fix, recompute `_expected` with
`tax_calculator.calculate` and run `tests/rescore.py`.

Regeneration reproduces every stored input except `TDS` in 320 cases. TDS is set from the
engine's liability at generation time, and the stored values were kept fixed when the engine
was later corrected (see `CHANGELOG.md`), so the inputs the models saw never changed.
