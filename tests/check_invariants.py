#!/usr/bin/env python3
"""Oracle-free validation of the ground truth.

Usage:
    python3 tests/check_invariants.py
    python3 tests/check_invariants.py --monotonic-sample 40
"""

import argparse
import copy
import glob
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))
from tax_calculator import calculate

TOL = 0.011  # outputs are rounded to 2dp, so allow a hair over half a paisa


def g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return 0.0
        d = d.get(k, 0.0)
    return d if isinstance(d, (int, float)) else 0.0


def check_case(inp, exp):
    """Return a list of (invariant_name, expected, actual) violations."""
    v = []

    def eq(name, lhs, rhs):
        if abs(lhs - rhs) > TOL:
            v.append((name, lhs, rhs))

    sal = exp.get("Under Head Salaries", {})
    cg = exp.get("Capital Gains", {})
    ded = exp.get("Deductions", {})
    tax = exp.get("Tax Computation", {})

    # --- salary: net = gross - exemptions - section 16 deductions ---
    eq("Net Salary = Gross - Exemptions - 16(ia/ii/iii)",
       g(sal, "Net Salary"),
       g(sal, "Gross Salary")
       - g(sal, "Exemptions", "Section 10(13A)") - g(sal, "Exemptions", "Section 10(5)")
       - g(sal, "Section 16(ia)") - g(sal, "Section 16(ii)") - g(sal, "Section 16(iii)"))

    # --- capital gains subtotals equal their components ---
    for head in ("STCG (Other)", "LTCG (Non-Equity)"):
        block = cg.get(head, {})
        parts = sum(val for key, val in block.items()
                    if key != "Total" and isinstance(val, (int, float)))
        eq(f"{head}.Total = sum of components", g(cg, head, "Total"), parts)

    # --- gross total income equals the sum of every head ---
    eq("Gross Total Income = sum of all heads",
       g(exp, "Gross Total Income"),
       g(sal, "Net Salary")
       + g(cg, "STCG (Section 111A)") + g(cg, "STCG (Other)", "Total")
       + g(cg, "LTCG (Section 112A)") + g(cg, "LTCG (Non-Equity)", "Total")
       + g(cg, "LTCG (Other)")
       + g(exp, "Income from Other Sources", "Savings Bank Interest")
       + g(exp, "Income from Other Sources", "Deposit Interest")
       + g(exp, "Income from Other Sources", "Other Interest")
       + g(exp, "Income from Other Sources", "EPF Taxable Interest"))

    # --- deductions total equals its parts, and taxable income follows ---
    # s.80A(2) caps the aggregate at GTI, and s.111A(2)/s.112A(6) exclude special-rate
    # gains from what deductions may be set against.
    ded_parts = sum(val for key, val in ded.items()
                    if key != "Total Deductions" and isinstance(val, (int, float)))
    special_gains = (g(cg, "STCG (Section 111A)") + g(cg, "LTCG (Section 112A)")
                     + g(cg, "LTCG (Non-Equity)", "Total"))
    eq("Total Deductions = min(sum of sections, GTI less special-rate gains)",
       g(ded, "Total Deductions"),
       min(ded_parts, max(0.0, g(exp, "Gross Total Income") - special_gains)))
    eq("Taxable Income = GTI - Total Deductions",
       g(exp, "Total Taxable Income"),
       g(exp, "Gross Total Income") - g(ded, "Total Deductions"))

    # --- tax build-up identities ---
    eq("Tax Before Rebate = sum of tax components",
       g(tax, "Total Tax Before Rebate"),
       g(tax, "Tax at Slab Rates")
       + g(tax, "Tax on STCG (Section 111A)") + g(tax, "Tax on STCG (Other)")
       + g(tax, "Tax on LTCG (Section 112A)") + g(tax, "Tax on LTCG (Non-Equity)")
       + g(tax, "Tax on LTCG (Other)"))
    eq("Tax After Rebate = Before Rebate - 87A",
       g(tax, "Tax After Rebate"),
       g(tax, "Total Tax Before Rebate") - g(tax, "Less: Rebate under Section 87A"))
    eq("Cess = 4% of (After Rebate + Surcharge)",
       g(tax, "Health and Education Cess"),
       round(0.04 * (g(tax, "Tax After Rebate") + g(tax, "Surcharge")), 2))
    eq("Total Liability = After Rebate + Surcharge + Cess",
       g(tax, "Total Tax Liability"),
       g(tax, "Tax After Rebate") + g(tax, "Surcharge") + g(tax, "Health and Education Cess"))
    eq("Net Payable = Total Liability - TDS",
       g(tax, "Net Tax Payable / Refund"),
       g(tax, "Total Tax Liability") - g(tax, "Less: TDS"))

    # --- bounds and signs ---
    if g(tax, "Less: Rebate under Section 87A") > g(tax, "Total Tax Before Rebate") + TOL:
        v.append(("87A rebate exceeds tax before rebate",
                  g(tax, "Total Tax Before Rebate"),
                  g(tax, "Less: Rebate under Section 87A")))

    regime = (inp.get("Tax Regime") or "").lower()
    cap = 60_000 if regime == "new" else 12_500
    if g(tax, "Less: Rebate under Section 87A") > cap + TOL:
        v.append((f"87A rebate over {regime}-regime cap", cap,
                  g(tax, "Less: Rebate under Section 87A")))

    # Net payable may be negative (a refund); nothing else may be.
    for label, val in (("Gross Total Income", g(exp, "Gross Total Income")),
                       ("Total Taxable Income", g(exp, "Total Taxable Income")),
                       ("Total Deductions", g(ded, "Total Deductions")),
                       ("Tax After Rebate", g(tax, "Tax After Rebate")),
                       ("Surcharge", g(tax, "Surcharge")),
                       ("Total Tax Liability", g(tax, "Total Tax Liability"))):
        if val < -TOL:
            v.append((f"{label} is negative", ">= 0", val))

    return v


def check_monotonic(inp, step=100_000):
    """More salary must never mean less tax. Catches slab/surcharge/marginal-relief
    and rebate-cliff bugs, which are invisible to a single-case comparison."""
    base = calculate(copy.deepcopy(inp))["Tax Computation"]["Total Tax Liability"]
    bumped = copy.deepcopy(inp)
    gs = bumped.get("Gross Salary")
    if not isinstance(gs, dict) or "Basic Salary" not in gs:
        return None
    gs["Basic Salary"] += step
    after = calculate(bumped)["Tax Computation"]["Total Tax Liability"]
    return None if after >= base - TOL else (base, after)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--monotonic-sample", type=int, default=40,
                    help="how many cases to run the (slower) monotonicity check on")
    args = ap.parse_args()

    files = sorted(glob.glob(str(SCRIPT_DIR / "generated" / "input_*.json")))
    if not files:
        print("No generated cases found.")
        sys.exit(1)

    failures = {}
    for f in files:
        data = json.load(open(f))
        viol = check_case(data["input"], data["_expected"])
        if viol:
            failures[Path(f).name] = viol

    print(f"\n{'='*66}")
    print(f"  Invariant check: {len(files)} cases, {len(failures)} with violations")
    print(f"{'='*66}")
    for name, viol in list(failures.items())[:15]:
        print(f"\n  {name}")
        for inv, expected, actual in viol[:6]:
            print(f"    {inv}\n      expected {expected}, got {actual}")
    if len(failures) > 15:
        print(f"\n  ... and {len(failures)-15} more cases")

    mono_bad = []
    for f in files[: args.monotonic_sample]:
        data = json.load(open(f))
        res = check_monotonic(data["input"])
        if res:
            mono_bad.append((Path(f).name, res))
    print(f"\n  Monotonicity (+₹100,000 basic salary) over "
          f"{min(args.monotonic_sample, len(files))} cases: "
          f"{len(mono_bad)} violations")
    for name, (base, after) in mono_bad[:10]:
        print(f"    {name}: tax fell {base} -> {after}")

    sys.exit(1 if failures or mono_bad else 0)


if __name__ == "__main__":
    main()
