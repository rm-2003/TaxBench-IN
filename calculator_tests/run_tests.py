"""Unit tests for tax_calculator.py: one hand-computed case per rule or edge case.

Usage (from repo root):
    python3 calculator_tests/run_tests.py
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
        "name": "Test 3c — LTCG, acquired AFTER 1-Feb-2018: no grandfathering",
        "input": "test3c_ltcg_no_grandfathering_post_2018.json",
        "checks": [
            # Same figures as 3b but bought in 2020, so the FMV of 200 must be ignored
            # and the actual cost of 100 used: (300-100)*10 - 50 = 1950.
            ("Capital Gains.LTCG (Section 112A)", 1950),
        ],
    },
    {
        "name": "Test 3d — grandfathering step-up capped at sale consideration",
        "input": "test3d_ltcg_grandfather_clamped_at_sale.json",
        "checks": [
            # FMV 500 above the sale price of 300: cost = max(100, min(500,300)) = 300,
            # so the gain is 0.
            ("Capital Gains.LTCG (Section 112A)", 0),
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
    {
        "name": "Test 16 — MF equity STCG (held 6 months)",
        "input": "test16_mf_equity_stcg.json",
        "checks": [
            ("Capital Gains.STCG (Section 111A)", 20000),
            ("Capital Gains.LTCG (Section 112A)", 0),
        ],
    },
    {
        "name": "Test 17 — ELSS lock-in (35 months < 36, no taxable event)",
        "input": "test17_mf_elss_lockin.json",
        "checks": [
            ("Capital Gains.LTCG (Section 112A)", 0),
        ],
    },
    {
        "name": "Test 18 — Debt MF pre-2023 LTCG, no indexation (post Budget 2024)",
        "input": "test18_mf_debt_pre2023.json",
        "checks": [
            ("Gross Total Income", 50000),
        ],
    },
    {
        "name": "Test 19 — STCL asymmetry (residual STCL offsets LTCG)",
        "input": "test19_mf_stcl_asymmetry.json",
        "checks": [
            ("Capital Gains.STCG (Section 111A)", 0),
            ("Capital Gains.LTCG (Section 112A)", 7000),
        ],
    },
    {
        "name": "Test 20 — LTCL 8-year expiry (2016-17 expired, 2017-18 eligible)",
        "input": "test20_ltcl_8yr_expiry.json",
        "checks": [
            ("Capital Gains.LTCG (Section 112A)", 5000),
        ],
    },
    {
        "name": "Test 21 — Bonds STCG (held 1 year)",
        "input": "test21_bonds_stcg.json",
        "checks": [
            ("Capital Gains.STCG (Other).Bonds", 50000),
            ("Capital Gains.STCG (Other).Total", 50000),
            ("Capital Gains.LTCG (Non-Equity).Total", 0),
        ],
    },
    {
        "name": "Test 22 — the 1.25L exemption is s.112A-only; it does NOT reach non-equity LTCG",
        "input": "test22_gsecs_ltcg.json",
        "checks": [
            ("Capital Gains.LTCG (Section 112A)", 100000),
            ("Capital Gains.LTCG (Non-Equity).G-Secs", 200000),
            # 1,00,000 of equity LTCG sits entirely inside the 1,25,000 relief,
            # so s.112A tax is nil.
            ("Tax Computation.Tax on LTCG (Section 112A)", 0),
            # The 25,000 of UNUSED relief must not spill onto the G-Secs gain: that is
            # charged under s.112, which has no such allowance.
            ("Tax Computation.Tax on LTCG (Non-Equity)", 25000),
        ],
    },
    {
        "name": "Test 23 — Privately Owned Vehicle (always exempt)",
        "input": "test23_vehicle_exempt.json",
        "checks": [
            ("Gross Total Income", 0),
            ("Capital Gains.STCG (Other).Total", 0),
            ("Capital Gains.LTCG (Non-Equity).Total", 0),
        ],
    },
    {
        "name": "Test 24 — Cross-bucket loss set-off (STCL + LTCL across equity & non-equity)",
        "input": "test24_cross_bucket_loss.json",
        "checks": [
            ("Capital Gains.STCG (Section 111A)", 0),
            ("Capital Gains.STCG (Other).Total", 0),
            ("Capital Gains.LTCG (Section 112A)", 4000),
            ("Capital Gains.LTCG (Non-Equity).Debentures", 6000),
            ("Gross Total Income", 10000),
        ],
    },
    {
        "name": "Test 27 — s.80A(2): deductions capped at gross total income",
        "input": "test27_80a2_deduction_cap.json",
        "checks": [
            ("Gross Total Income", 68000),
            ("Deductions.Total Deductions", 68000),
            ("Total Taxable Income", 0),
            ("Tax Computation.Total Tax Liability", 0),
        ],
    },
    {
        "name": "Test 28 — 80CCD(2): employer NPS is taxable salary before it is deducted",
        "input": "test28_80ccd2_employer_nps_in_salary.json",
        "checks": [
            # 13,00,000 of components + the 50,000 employer contribution.
            ("Under Head Salaries.Gross Salary", 1350000),
            ("Under Head Salaries.Net Salary", 1275000),
            ("Gross Total Income", 1290000),
            ("Deductions.80CCD(2)", 50000),
            # The whole point of the deduction: the taxpayer ends up exactly
            # where they would have been with no NPS arrangement at all.
            ("Total Taxable Income", 1240000),
        ],
    },
    {
        "name": "Test 29 — Other Interest is a reportable sibling of EPF Taxable Interest",
        "input": "test29_other_interest_reportable.json",
        "checks": [
            # Other Interest and EPF Taxable Interest are reported as separate fields.
            ("Income from Other Sources.Other Interest", 3000),
            ("Income from Other Sources.EPF Taxable Interest", 2000),
            ("Gross Total Income", 20000),
            # The invariant, stated as an assertion: every rupee of income in
            # GTI is visible in a reported head.
            (lambda out: sum(out["Income from Other Sources"].values()),
             lambda out: out["Gross Total Income"]),
        ],
    },
    {
        "name": "Test 30 — no 14% imputation for a government employee",
        "input": "test30_no_govt_nps_imputation.json",
        "checks": [
            # Basic 5,00,000 + DA 1,00,000 and 0 declared.
            ("Under Head Salaries.Gross Salary", 600000),
            ("Deductions.80CCD(2)", 0),
            ("Under Head Salaries.Net Salary", 550000),
            ("Gross Total Income", 550000),
        ],
    },
    {
        "name": "Test 31 — old regime, senior citizen (60-79): 3,00,000 basic exemption",
        "input": "test31_old_regime_senior_exemption.json",
        "checks": [
            # Taxable 5,50,000 at age 65: (5,00,000-3,00,000) at 5% = 10,000 plus
            # (5,50,000-5,00,000) at 20% = 10,000.
            ("Total Taxable Income", 550000),
            ("Tax Computation.Tax at Slab Rates", 20000),
        ],
    },
    {
        "name": "Test 32 — old regime, super senior (80+): 5,00,000 basic exemption",
        "input": "test32_old_regime_super_senior_exemption.json",
        "checks": [
            # The 5% band vanishes: the exemption already reaches its top.
            ("Total Taxable Income", 550000),
            ("Tax Computation.Tax at Slab Rates", 10000),
        ],
    },
    {
        "name": "Test 33 — 80CCE full: NPS self-contribution goes to 80CCD(1B)",
        "input": "test33_80ccd1b_takes_nps_when_80cce_full.json",
        "checks": [
            # 80C alone fills the 1,50,000 80CCE cap, so there is no room for 80CCD(1).
            ("Deductions.80C", 150000),
            ("Deductions.80CCD(1)", 0),
            ("Deductions.80CCD(1B)", 50000),
            ("Deductions.Total Deductions", 200000),
        ],
    },
    {
        "name": "Test 34 — 80CCE not binding: NPS stays under 80CCD(1)",
        "input": "test34_80ccd1_unchanged_when_80cce_not_binding.json",
        "checks": [
            # Guards the other side of the Test 33 fix: with room under the cap
            # the split is exactly what it was before.
            ("Deductions.80C", 50000),
            ("Deductions.80CCD(1)", 50000),
            ("Deductions.80CCD(1B)", 0),
            ("Deductions.Total Deductions", 100000),
        ],
    },
]


def get_nested(d, path: str):
    parts = path.split(".")
    i = 0
    while i < len(parts):
        if not isinstance(d, dict):
            return None
        for j in range(len(parts), i, -1):
            candidate = ".".join(parts[i:j])
            if candidate in d:
                d = d[candidate]
                i = j
                break
        else:
            return None
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
