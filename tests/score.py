#!/usr/bin/env python3
"""Score saved LLM output files with the same rules as tests/evaluate_llm.py.

evaluate_llm.py calls a model and scores its reply straight away. This script does only the
scoring part, for outputs that were produced elsewhere (e.g. the local Qwen run) and saved as
output_NNNN.json. It runs no models and needs no API key.

Each output_NNNN.json in --outputs-dir is compared with the "_expected" section of
input_NNNN.json in --cases-dir. The scoring is copied unchanged from evaluate_llm.py:
  * 37 scored fields (SALARY / OTHER_SOURCES / AGGREGATE / DEDUCTION_LEAF / TAX fields, plus
    the combined fields: STCG = 111A + STCG Other Total, LTCG = 112A + Non-Equity Total + LTCG
    Other, and 80C + 80CCC + 80CCD(1));
  * a field scores 1 if it is within TOLERANCE (0.01) of the expected value, otherwise 0;
  * a missing or unreadable output file counts as a parse failure and scores 0 on every field;
  * pct_error = |expected - actual| / max(|expected|, 1), reported but not used in the score.

Results are written in evaluate_llm.py's CSV formats, to --results-dir (default
tests/evaluation_results, the folder evaluate_llm.py uses):
  <model>__<method>_results.csv   one row per case: 0/1 per field, pct errors, total_score
  <method>_summary.csv            one row per model: overall and per-section accuracy
Columns that only exist for live API runs (rounds, latency, tokens, cost) are left out.
An existing <method>_summary.csv is updated: the row for this model is replaced, others kept.

Usage:
    python tests/score.py
    python tests/score.py --model qwen3:4b --method local
    python tests/score.py --outputs-dir tests/llm_outputs --results-dir tests/evaluation_results
"""

import argparse
import csv
import glob
import json
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent        # tests
GENERATED_DIR = SCRIPT_DIR / "generated"            # input_NNNN.json with _expected
OUTPUTS_DIR = SCRIPT_DIR / "llm_outputs"            # output_NNNN.json from the model
RESULTS_DIR = SCRIPT_DIR / "evaluation_results"     # same folder evaluate_llm.py writes to

# ---------------------------------------------------------------------------
# Scoring rules - copied from evaluate_llm.py
# ---------------------------------------------------------------------------
TOLERANCE = 0.01

SALARY_FIELDS = [
    ("gross_salary", ("Under Head Salaries", "Gross Salary")),
    ("sec_10_13a", ("Under Head Salaries", "Exemptions", "Section 10(13A)")),
    ("sec_10_5", ("Under Head Salaries", "Exemptions", "Section 10(5)")),
    ("sec_16_ia", ("Under Head Salaries", "Section 16(ia)")),
    ("sec_16_ii", ("Under Head Salaries", "Section 16(ii)")),
    ("sec_16_iii", ("Under Head Salaries", "Section 16(iii)")),
    ("net_salary", ("Under Head Salaries", "Net Salary")),
]

OTHER_SOURCES_FIELDS = [
    ("savings_bank_interest", ("Income from Other Sources", "Savings Bank Interest")),
    ("deposit_interest", ("Income from Other Sources", "Deposit Interest")),
    ("epf_taxable_interest", ("Income from Other Sources", "Other Interest", "EPF Taxable Interest")),
]

AGGREGATE_FIELDS = [
    ("gross_total_income", ("Gross Total Income",)),
    ("total_taxable_income", ("Total Taxable Income",)),
]

DEDUCTION_LEAF_FIELDS = [
    ("80ccd_1b", ("Deductions", "80CCD(1B)")),
    ("80ccd_2", ("Deductions", "80CCD(2)")),
    ("80d", ("Deductions", "80D")),
    ("80e", ("Deductions", "80E")),
    ("80g", ("Deductions", "80G")),
    ("80tta", ("Deductions", "80TTA")),
    ("80ttb", ("Deductions", "80TTB")),
    ("total_deductions", ("Deductions", "Total Deductions")),
]

TAX_FIELDS = [
    ("tax_at_slab_rates", ("Tax Computation", "Tax at Slab Rates")),
    ("tax_stcg_111a", ("Tax Computation", "Tax on STCG (Section 111A)")),
    ("tax_stcg_other", ("Tax Computation", "Tax on STCG (Other)")),
    ("tax_ltcg_112a", ("Tax Computation", "Tax on LTCG (Section 112A)")),
    ("tax_ltcg_non_equity", ("Tax Computation", "Tax on LTCG (Non-Equity)")),
    ("tax_ltcg_other", ("Tax Computation", "Tax on LTCG (Other)")),
    ("total_tax_before_rebate", ("Tax Computation", "Total Tax Before Rebate")),
    ("rebate_87a", ("Tax Computation", "Less: Rebate under Section 87A")),
    ("tax_after_rebate", ("Tax Computation", "Tax After Rebate")),
    ("surcharge", ("Tax Computation", "Surcharge")),
    ("cess", ("Tax Computation", "Health and Education Cess")),
    ("total_tax_liability", ("Tax Computation", "Total Tax Liability")),
    ("tds", ("Tax Computation", "Less: TDS")),
    ("net_tax_payable", ("Tax Computation", "Net Tax Payable / Refund")),
]

COMBINED_FIELDS = ["combined_stcg", "combined_ltcg", "80c_80ccc_80ccd1"]

ALL_FIELD_NAMES = (
    [f[0] for f in SALARY_FIELDS]
    + COMBINED_FIELDS[:2]  # combined_stcg, combined_ltcg
    + [f[0] for f in OTHER_SOURCES_FIELDS]
    + [f[0] for f in AGGREGATE_FIELDS]
    + [COMBINED_FIELDS[2]]  # 80c_80ccc_80ccd1
    + [f[0] for f in DEDUCTION_LEAF_FIELDS]
    + [f[0] for f in TAX_FIELDS]
)
N_FIELDS = len(ALL_FIELD_NAMES)  # 37

SECTION_MAP = {
    "salary": [f[0] for f in SALARY_FIELDS],
    "capital_gains": COMBINED_FIELDS[:2],
    "other_sources": [f[0] for f in OTHER_SOURCES_FIELDS],
    "aggregates": [f[0] for f in AGGREGATE_FIELDS],
    "deductions": [COMBINED_FIELDS[2]] + [f[0] for f in DEDUCTION_LEAF_FIELDS],
    "tax_computation": [f[0] for f in TAX_FIELDS],
}


def get_nested(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def safe_float(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def pct_error(expected_val, actual_val):
    e = safe_float(expected_val)
    a = safe_float(actual_val)
    denom = max(abs(e), 1.0)
    return abs(e - a) / denom


def score_case(expected, actual):
    """Returns (scores, pct_errors) dicts keyed by field name. Same as evaluate_llm.py."""
    scores = {}
    pct_errors = {}

    def leaf(name, *keys):
        ev = get_nested(expected, *keys)
        av = get_nested(actual, *keys) if actual else None
        if ev is None or av is None:
            scores[name] = 0
            pct_errors[name] = 1.0 if ev is not None else 0.0
            return
        try:
            ef, af = float(ev), float(av)
            correct = abs(ef - af) <= TOLERANCE
            scores[name] = 1 if correct else 0
            pct_errors[name] = 0.0 if correct else pct_error(ev, av)
        except (TypeError, ValueError):
            scores[name] = 0
            pct_errors[name] = 1.0

    def combined(name, exp_val, act_val):
        correct = abs(exp_val - act_val) <= TOLERANCE
        scores[name] = 1 if correct else 0
        pct_errors[name] = 0.0 if correct else abs(exp_val - act_val) / max(abs(exp_val), 1.0)

    def total_of(d, *paths):
        return sum(safe_float(get_nested(d, *p)) for p in paths)

    stcg_paths = [("Capital Gains", "STCG (Section 111A)"), ("Capital Gains", "STCG (Other)", "Total")]
    ltcg_paths = [("Capital Gains", "LTCG (Section 112A)"), ("Capital Gains", "LTCG (Non-Equity)", "Total"),
                  ("Capital Gains", "LTCG (Other)")]
    cce_paths = [("Deductions", "80C"), ("Deductions", "80CCC"), ("Deductions", "80CCD(1)")]

    # Salary
    for fname, keys in SALARY_FIELDS:
        leaf(fname, *keys)

    # Combined STCG / LTCG
    for name, paths in (("combined_stcg", stcg_paths), ("combined_ltcg", ltcg_paths)):
        if actual:
            combined(name, total_of(expected, *paths), total_of(actual, *paths))
        else:
            scores[name], pct_errors[name] = 0, 1.0

    # Other sources
    for fname, keys in OTHER_SOURCES_FIELDS:
        leaf(fname, *keys)

    # Aggregates
    for fname, keys in AGGREGATE_FIELDS:
        leaf(fname, *keys)

    # Combined 80CCE
    if actual:
        combined("80c_80ccc_80ccd1", total_of(expected, *cce_paths), total_of(actual, *cce_paths))
    else:
        scores["80c_80ccc_80ccd1"], pct_errors["80c_80ccc_80ccd1"] = 0, 1.0

    # Deduction leaf fields
    for fname, keys in DEDUCTION_LEAF_FIELDS:
        leaf(fname, *keys)

    # Tax computation
    for fname, keys in TAX_FIELDS:
        leaf(fname, *keys)

    return scores, pct_errors


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def model_slug(model):
    return model.replace("/", "_").replace(":", "_")


def load_output(path):
    """Parsed output dict, or None if the file is missing, unreadable or not a non-empty dict."""
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) and obj else None


def case_number(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Reporting (same columns as evaluate_llm.py, minus API-only ones)
# ---------------------------------------------------------------------------
def write_results_csv(path, model, method, results):
    fieldnames = (["case_file", "output_file", "description", "model", "method", "parsed"]
                  + ALL_FIELD_NAMES + [f"{f}_pct_error" for f in ALL_FIELD_NAMES]
                  + ["total_score", "total_pct"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = {"case_file": r["case_file"], "output_file": r["output_file"],
                   "description": r["description"], "model": model, "method": method,
                   "parsed": 1 if r["parsed"] else 0,
                   "total_score": r["total_score"], "total_pct": r["total_pct"]}
            for fname in ALL_FIELD_NAMES:
                row[fname] = r["scores"].get(fname, 0)
                row[f"{fname}_pct_error"] = round(r["pct_errors"].get(fname, 1.0), 4)
            w.writerow(row)


def summary_row(model, results):
    n = len(results)

    def section_acc(fields):
        return round(sum(r["scores"].get(f, 0) for r in results for f in fields) / (n * len(fields)), 4)

    return {
        "model": model,
        "overall_accuracy": round(sum(r["total_pct"] for r in results) / n, 4),
        "salary_accuracy": section_acc(SECTION_MAP["salary"]),
        "capital_gains_accuracy": section_acc(SECTION_MAP["capital_gains"]),
        "other_sources_accuracy": section_acc(SECTION_MAP["other_sources"]),
        "aggregates_accuracy": section_acc(SECTION_MAP["aggregates"]),
        "deductions_accuracy": section_acc(SECTION_MAP["deductions"]),
        "tax_computation_accuracy": section_acc(SECTION_MAP["tax_computation"]),
        "parse_fail_count": sum(1 for r in results if not r["parsed"]),
        "total_cases": n,
    }


def write_summary_csv(path, row):
    """Add or replace this model's row, keeping rows for other models."""
    rows = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("model") != row["model"]]
    rows.append(row)
    fieldnames = list(row)
    for r in rows:                      # keep any extra columns an evaluate_llm.py summary has
        fieldnames += [k for k in r if k not in fieldnames]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        w.writeheader()
        w.writerows(rows)


def print_summary(model, method, results, row):
    n = len(results)
    full = sum(1 for r in results if r["total_score"] == N_FIELDS)
    ttl = sum(r["scores"].get("total_tax_liability", 0) for r in results)
    print(f"\n=== Score Report: {model} [{method}] ===")
    print(f"Overall accuracy:    {row['overall_accuracy']*100:.1f}% ({n} cases)")
    print(f"Failed to parse:     {row['parse_fail_count']} cases (scored as 0)")
    print(f"All {N_FIELDS} fields right: {full} cases ({full/n*100:.1f}%)")
    print(f"Total Tax Liability: {ttl/n*100:.1f}% correct")
    print("\nPer-section accuracy:")
    for sec, fields in SECTION_MAP.items():
        label = f"{sec.replace('_', ' ').title()} ({len(fields)} fields):"
        print(f"  {label:30s}{row[sec + '_accuracy']*100:.1f}%")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases-dir", default=str(GENERATED_DIR),
                   help="Folder with input_NNNN.json holding _expected (default: tests/generated)")
    p.add_argument("--outputs-dir", default=str(OUTPUTS_DIR),
                   help="Folder with output_NNNN.json (default: tests/llm_outputs)")
    p.add_argument("--results-dir", default=str(RESULTS_DIR),
                   help="Where the CSVs are written (default: tests/evaluation_results)")
    p.add_argument("--model", default="qwen3:4b", help="Model name for the reports (default: qwen3:4b)")
    p.add_argument("--method", default="local", help="Method label for the reports (default: local)")
    args = p.parse_args()

    cases_dir, outputs_dir, results_dir = Path(args.cases_dir), Path(args.outputs_dir), Path(args.results_dir)
    case_files = sorted(glob.glob(str(cases_dir / "input_*.json")))
    if not case_files:
        raise SystemExit(f"ERROR: no input_*.json in {cases_dir}")

    results = []
    for cf in case_files:
        data = json.loads(Path(cf).read_text(encoding="utf-8-sig"))
        n = case_number(os.path.basename(cf))
        out_path = outputs_dir / f"output_{n:04d}.json"
        output = load_output(out_path)
        scores, pct_errors = score_case(data["_expected"], output)
        total = sum(scores.values())
        results.append({
            "case_file": os.path.basename(cf), "output_file": out_path.name,
            "description": data.get("_description", ""), "parsed": output is not None,
            "scores": scores, "pct_errors": pct_errors,
            "total_score": total, "total_pct": round(total / N_FIELDS, 4),
        })

    results_dir.mkdir(parents=True, exist_ok=True)
    results_csv = results_dir / f"{model_slug(args.model)}__{args.method}_results.csv"
    summary_csv = results_dir / f"{args.method}_summary.csv"
    write_results_csv(results_csv, args.model, args.method, results)
    row = summary_row(args.model, results)
    write_summary_csv(summary_csv, row)

    print_summary(args.model, args.method, results, row)
    print(f"\nWritten: {results_csv}\n         {summary_csv}")


if __name__ == "__main__":
    main()
