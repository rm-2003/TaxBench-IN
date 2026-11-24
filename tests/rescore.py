#!/usr/bin/env python3
"""Rescore checkpointed model outputs against the CURRENT ground truth.

Usage:
    python3 tests/rescore.py --dry-run          # report drift, write nothing
    python3 tests/rescore.py                    # rebuild the derived CSVs
    python3 tests/rescore.py --update-checkpoints  # also refresh stored scores
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_llm as E

METHODS = ["zero-shot", "script", "tool-call"]


def resolve_model_id(slug, method):
    """Recover the real model ID for a checkpoint slug."""
    csv_path = E.RESULTS_DIR / f"{slug}__{method}_results.csv"
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("model"):
                    return row["model"]
    known = set(E.MODELS) | set(E.MODEL_CONFIG)
    for m in known:
        if E.model_slug(m) == slug:
            return m
    return None


def rescore_method(method, cases_by_file, dry_run, update_checkpoints):
    all_model_results = {}
    report = []

    for ckpt in sorted(E.CHECKPOINT_DIR.glob(f"*__{method}.jsonl")):
        slug = ckpt.name[: -len(f"__{method}.jsonl")]
        model = resolve_model_id(slug, method)
        if model is None:
            print(f"  ! {slug}: cannot resolve model ID — skipped")
            continue

        entries = [json.loads(l) for l in ckpt.read_text().splitlines() if l.strip()]
        results, refreshed = [], []
        old_score = new_score = fields = changed = 0

        for entry in entries:
            case = cases_by_file.get(entry["case_file"])
            if case is None:
                print(f"  ! {slug}: {entry['case_file']} not in dataset — skipped")
                continue

            scores, pct_errors = E.score_case(case["expected"], entry.get("llm_output"))
            total = sum(scores.values())

            old_score += entry["total_score"]
            new_score += total
            fields += len(scores)
            if total != entry["total_score"]:
                changed += 1

            fresh = dict(entry, scores=scores, pct_errors=pct_errors, total_score=total)
            refreshed.append(fresh)
            results.append(E.result_from_checkpoint_entry(fresh, model, method, cases_by_file))

        if not results:
            continue

        all_model_results[model] = results
        report.append((model, len(results), old_score / fields, new_score / fields, changed))

        if not dry_run:
            E.write_per_model_method_csv(model, method, results)
            if update_checkpoints:
                shutil.copy2(ckpt, ckpt.with_suffix(".jsonl.bak"))
                with open(ckpt, "w") as f:
                    for fresh in refreshed:
                        f.write(json.dumps(fresh) + "\n")

    if all_model_results and not dry_run:
        E.write_method_summary_csv(method, all_model_results)

    return report


def main():
    ap = argparse.ArgumentParser(description="Rescore checkpoints against current ground truth")
    ap.add_argument("--method", choices=METHODS, help="default: every method with checkpoints")
    ap.add_argument("--dry-run", action="store_true", help="report drift without writing")
    ap.add_argument("--update-checkpoints", action="store_true",
                    help="also rewrite stored scores in the checkpoints (keeps llm_output; "
                         "writes a .bak). Without this, a later resumed run mixes stale "
                         "stored scores with freshly scored cases.")
    args = ap.parse_args()

    cases_by_file = {c["file"]: c for c in E.load_cases()}
    methods = [args.method] if args.method else METHODS

    any_report = False
    for method in methods:
        report = rescore_method(method, cases_by_file, args.dry_run, args.update_checkpoints)
        if not report:
            continue
        any_report = True
        print(f"\n=== {method} ===")
        print(f"{'model':44} {'n':>4} {'stored':>8} {'rescored':>9} {'delta':>8} {'cases≠':>7}")
        print("-" * 85)
        for model, n, old, new, changed in sorted(report):
            print(f"{model[:44]:44} {n:4d} {old:8.4f} {new:9.4f} {new - old:+8.4f} {changed:7d}")

    if not any_report:
        print("No checkpoints found to rescore.")
        return

    if args.dry_run:
        print("\nDry run — nothing written.")
    else:
        pivot = E.write_cross_method_pivot()
        print(f"\nRebuilt per-model CSVs, method summaries, and pivot: {pivot}")


if __name__ == "__main__":
    main()
