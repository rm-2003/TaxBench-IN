"""
run_tests.py
Runs all test cases against v1.1_calculator.py and reports pass/fail.

Usage:
    python3 tests/run_tests.py
(from the V1.1 directory)
"""

import json
import subprocess
import sys
import tempfile
import os

CALCULATOR = os.path.join(os.path.dirname(__file__), "..", "v1.1_calculator.py")

TESTS = [
    {
        "name": "Test 1 — All zeros",
        "input": "test1_all_zeros.json",
        "checks": [
            ("Under Head Salaries.Gross Salary", 0),
            ("Under Head Salaries.Net Salary", 0),
            ("Gross Total Income", 0),
            ("Total Taxable Income", 0),
            ("Tax Computation.Net Tax Payable / Refund", 0),
        ],
    },
    {
        "name": "Test 2 — HRA exemption",
        "input": "test2_hra_exemption.json",
        "checks": [
            ("Under Head Salaries.Exemptions.Section 10(13A)", 120000),
        ],
    },
    {
        "name": "Test 3a — STCG classification",
        "input": "test3a_stcg.json",
        "checks": [
            ("Capital Gains.STCG (Section 111A)", 400),
            ("Capital Gains.LTCG (Section 112A)", 0),
        ],
    },
    {
        "name": "Test 3b — LTCG with grandfathering",
        "input": "test3b_ltcg_grandfathering.json",
        "checks": [
            ("Capital Gains.LTCG (Section 112A)", 950),
            ("Capital Gains.STCG (Section 111A)", 0),
        ],
    },
    {
        "name": "Test 4 — 80C cap at 1.5L",
        "input": "test4_80c_cap.json",
        "checks": [
            ("Deductions.80CCE.80C", 150000),
            (lambda out: out["Deductions"]["80CCE"]["Total (capped at 1.5L)"], 150000),
        ],
    },
    {
        "name": "Test 5 — 80G donations",
        "input": "test5_80g_donations.json",
        "checks": [
            ("Deductions.80G", 7000),
        ],
    },
    {
        "name": "Test 6 — Section 87A rebate",
        "input": "test6_87a_rebate.json",
        "checks": [
            # rebate should equal slab tax (full zeroing out)
            ("Tax Computation.Less: Rebate under Section 87A",
             lambda out: out["Tax Computation"]["Tax at Slab Rates"]),
        ],
    },
]


def get_nested(d, path: str):
    keys = path.split(".")
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def run_test(test: dict, tests_dir: str) -> bool:
    input_path = os.path.join(tests_dir, test["input"])
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, CALCULATOR, input_path, output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  FAIL — calculator error: {result.stderr.strip()}")
            return False

        with open(output_path) as f:
            out = json.load(f)

        all_pass = True
        for path, expected in test["checks"]:
            actual = path(out) if callable(path) else get_nested(out, path)
            exp_val = expected(out) if callable(expected) else expected
            label = path.__name__ if callable(path) else path
            if actual != exp_val:
                print(f"  FAIL  {label}: got {actual}, expected {exp_val}")
                all_pass = False
            else:
                print(f"  PASS  {label} = {actual}")
        return all_pass

    finally:
        os.unlink(output_path)


def main():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    passed = failed = 0

    for test in TESTS:
        print(f"\n{test['name']}")
        if run_test(test, tests_dir):
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
