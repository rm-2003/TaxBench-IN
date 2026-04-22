"""
run_tests.py
Runs all test cases against tax_calculator.py and reports pass/fail.

Usage (from repo root):
    python3 tests/run_tests.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tax_calculator import calculate

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
            ("Deductions.80C", 150000),
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
            (lambda out: out["Tax Computation"]["Less: Rebate under Section 87A"],
             lambda out: out["Tax Computation"]["Tax at Slab Rates"]),
            ("Tax Computation.Tax After Rebate", 0),
        ],
    },
    {
        "name": "Test 7 — Section 16(ii) govt employee",
        "input": "test7_s16ii_govt.json",
        "checks": [
            ("Under Head Salaries.Section 16(ii)", 5000),
        ],
    },
    {
        "name": "Test 8 — 80E within 8-year limit",
        "input": "test8_80e_limit.json",
        "checks": [
            ("Deductions.80E", 50000),
        ],
    },
    {
        "name": "Test 8b — 80E beyond 8-year limit",
        "input": "test8b_80e_expired.json",
        "checks": [
            ("Deductions.80E", 0),
        ],
    },
    {
        "name": "Test 9 — 80TTA (age < 60)",
        "input": "test9_80tta.json",
        "checks": [
            ("Deductions.80TTA", 10000),
            ("Deductions.80TTB", 0),
        ],
    },
    {
        "name": "Test 10 — 80TTB (age >= 60)",
        "input": "test10_80ttb.json",
        "checks": [
            ("Deductions.80TTB", 50000),
            ("Deductions.80TTA", 0),
        ],
    },
    {
        "name": "Test 11 — 80D basic (self + senior parents + checkup)",
        "input": "test11_80d_basic.json",
        "checks": [
            ("Deductions.80D", 38000),
        ],
    },
    {
        "name": "Test 12 — 80D exclusions (cash/group/invalid beneficiary/checkup cap)",
        "input": "test12_80d_exclusions.json",
        "checks": [
            ("Deductions.80D", 17000),
        ],
    },
    {
        "name": "Test 13 — 80D multi-year premium split",
        "input": "test13_80d_multiyear.json",
        "checks": [
            ("Deductions.80D", 25000),
        ],
    },
    {
        "name": "Test 14 — 87A marginal relief (total_taxable > 12L with STCG)",
        "input": "test14_87a_marginal_relief.json",
        "checks": [
            ("Tax Computation.Less: Rebate under Section 87A", 38750),
            ("Tax Computation.Tax After Rebate", 29000),
        ],
    },
    {
        "name": "Test 15 — Surcharge marginal relief (51L income, new regime)",
        "input": "test15_surcharge_marginal_relief.json",
        "checks": [
            ("Tax Computation.Surcharge", 70000),
            ("Tax Computation.Tax After Rebate", 1110000),
        ],
    },
]


def get_nested(d, path: str):
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def run_test(test: dict, tests_dir: str) -> bool:
    input_path = os.path.join(tests_dir, test["input"])
    with open(input_path) as f:
        inp = json.load(f)
    inp.pop("_description", None)

    try:
        out = calculate(inp)
    except Exception as e:
        print(f"  FAIL — calculator raised: {e}")
        return False

    all_pass = True
    for path, expected in test["checks"]:
        actual  = path(out)  if callable(path)     else get_nested(out, path)
        exp_val = expected(out) if callable(expected) else expected
        label   = path.__name__ if callable(path) else path
        if actual != exp_val:
            print(f"  FAIL  {label}: got {actual!r}, expected {exp_val!r}")
            all_pass = False
        else:
            print(f"  PASS  {label} = {actual!r}")
    return all_pass


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
