# Handoff: remaining Gemma 4 12B runs

State as of 1 Nov 2026, branch `fix/v1.4.4-correctness-fixes` (= `main`).
Everything below runs locally through Ollama; no API key is needed.

## Do this (in order)

1. Set up the Ollama model exactly as in "Rules" item 2 below, and check the
   base model ID is `4eb23ef187e2`.
2. Create a branch: `git checkout -b gemma-zeroshot-569`.
3. Run the snippet under "How the harness knows which cases are done"; it must
   print `496 done; 73 left`. If it prints anything else, stop and ask Pranav.
4. Run the zero-shot command under "Commands". If it stops (sleep, crash), run
   the same command again; it resumes. Repeat until it reports 569 cases.
5. Commit as described under "When done" and push the branch
   (`git push -u origin gemma-zeroshot-569`). Do **not** push to `main`;
   Pranav is still committing other runs there and will merge this branch.
6. Report the final accuracy and any parse failures to Pranav.
7. **Stop there.** Do not start the script or tool-call runs: Pranav will
   choose a case subset for those first (all 519 remaining script cases would
   take about 17 days on a laptop).

## What is left

Case order is fixed: `tests/evaluate_llm.py` loads all 569 files in
`tests/generated/`, shuffles them with `random.Random(42)`, and takes the first
`--max-cases`. A run resumes from its checkpoint and only does missing cases.

| Arm | Checkpoint (`tests/evaluation_checkpoints/`) | Done | Left to 569 | Approx. time per case |
|---|---|---|---|---|
| Zero-shot, ctx16k | `ollama_gemma4-12b-ctx16k__zero-shot.jsonl` | 496 | 73 | ~3 min |
| Script, ctx16k | `ollama_gemma4-12b-ctx16k__script.jsonl` | 50 | 519 | ~45 min (multi-round, long scripts) |
| Tool-call | none for ctx16k | 0 | 569 | not measured |

### How the harness knows which cases are done

The checkpoint files are the record. Each line is one finished case and starts
with its file name, e.g. `{"case_file": "input_0289.json", ...}`. On start-up
the harness builds the seed-42 order, reads every `case_file` already in the
checkpoint for that model and method, and runs only the others; it prints
`Resuming: 496 done, 73 remaining`. So do not delete, rename or rewrite the
checkpoint files, and do not change the case folder (adding or removing files
changes the shuffle order). To list done and remaining cases:

```
python3 - <<'PY'
import json, random, sys
sys.path.insert(0, "tests")
import evaluate_llm as E
order = [c["file"] for c in E.load_cases()]
random.Random(42).shuffle(order)
ck = "tests/evaluation_checkpoints/ollama_gemma4-12b-ctx16k__zero-shot.jsonl"
done = {json.loads(l)["case_file"] for l in open(ck) if l.strip()}
left = [f for f in order if f not in done]
print(len(done), "done;", len(left), "left; next:", left[:5])
PY
```

Nemotron (OpenRouter / NVIDIA) arms are being run separately; do not touch
their checkpoints (`nvidia_*`, `nim_*`).

Priority: finish zero-shot first (73 cases, a few hours), then script. The
script arm at 569 is roughly 17 days of continuous local compute on a laptop, so
agree with Pranav on a subset (e.g. a fixed number per archetype) before
starting it. Tool-call for Gemma has only an old 3-case trial at 8k
(`ollama_gemma4-12b-ctx8k__tool-call.jsonl`); tool-call conversations grow every
round, so check context length before running it at 16k.

## Rules (keep results comparable)

1. Do not modify `tests/generated/` (inputs or `_expected`), `tax_calculator.py`,
   the prompts, or the scoring. Every existing number in the paper is scored
   against these exact files. In particular do not merge
   `origin/qwen-local-corrected-calculator`: it rewrites `_expected` in every case.
2. Use the same Ollama model as the existing runs: base `gemma4:12b`
   (ID `4eb23ef187e2`) with only the context window changed. Create it with
   this Modelfile:

   ```
   FROM gemma4:12b
   PARAMETER num_ctx 16384
   ```

   then `ollama create gemma4-12b-ctx16k -f Modelfile`. The harness sends
   `temperature=0` and `reasoning_effort="none"` itself (see `MODEL_CONFIG` in
   `tests/evaluate_llm.py`), and runs one case at a time (`concurrency=1`).
3. Append to the existing checkpoints above (just run the commands below; the
   harness resumes). Do not delete or rewrite existing rows.
4. Keep the machine plugged in and awake (lid open). A sleep mid-case inflates
   that case's `latency_sec` and can drop the request.

## Commands

From the repository root, with Ollama running:

```
# zero-shot: the remaining 73 cases
python3 tests/evaluate_llm.py --method zero-shot --model ollama/gemma4-12b-ctx16k --max-cases 569

# script: same settings as the existing 50 (max_script_retries=6, script_timeout=20s are the defaults)
python3 tests/evaluate_llm.py --method script --model ollama/gemma4-12b-ctx16k --max-cases 569
```

Use `--max-cases N` with N < 569 to stop at the first N cases of the fixed order.
Check progress with `wc -l` on the checkpoint file. The run prints a report
and rewrites `tests/evaluation_results/*` at the end; rerun
`python3 tests/rescore.py` if summaries need rebuilding.

## When done

Commit only the Gemma checkpoint(s), results CSVs, summaries and logs. Before
committing, check no secrets are staged:
`git diff --cached | grep -E "sk-or-v1-|nvapi-"` must print nothing.
Record the run (dates, cases, accuracy, anything unusual) as an addition to the
v1.4.4 section at the end of `CHANGELOG.md`; never edit earlier entries.
