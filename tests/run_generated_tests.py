#!/usr/bin/env python3
"""Ground-truth verification: runs the calculator on each generated test case
and verifies that the output matches the _expected field.

Usage:
    python3 tests/run_generated_tests.py
"""

import glob
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GENERATED_DIR = SCRIPT_DIR / "generated"
TOLERANCE = 0.01

sys.path.insert(0, str(PROJECT_DIR))
import tax_calculator


def compare(expected, actual, path=""):
    """Recursively compare two nested dicts. Returns list of (path, exp, act)."""
    diffs = []
    if isinstance(expected, dict):
        for k in expected:
            child_path = f"{path}.{k}" if path else k
            if k not in actual:
                diffs.append((child_path, expected[k], "<MISSING>"))
            else:
                diffs.extend(compare(expected[k], actual[k], child_path))
        for k in actual:
            if k not in expected:
                child_path = f"{path}.{k}" if path else k
                diffs.append((child_path, "<UNEXPECTED>", actual[k]))
    else:
        try:
            ev, av = float(expected), float(actual)
            if abs(ev - av) > TOLERANCE:
                diffs.append((path, expected, actual))
        except (TypeError, ValueError):
            if expected != actual:
                diffs.append((path, expected, actual))
    return diffs


def main():
    case_files = sorted(glob.glob(str(GENERATED_DIR / "input_*.json")))
    if not case_files:
        print(f"No test cases found in {GENERATED_DIR}")
        sys.exit(1)

    passed = 0
    failed = 0
    errors = []

    for f in case_files:
        fname = os.path.basename(f)
        with open(f) as fh:
            data = json.load(fh)

        expected = data["_expected"]
        description = data.get("_description", "")
        input_data = data["input"]

        try:
            result = tax_calculator.calculate(input_data)
        except Exception as e:
            failed += 1
            errors.append((fname, description, f"Calculator error: {e}"))
            continue

        diffs = compare(expected, result)
        if diffs:
            failed += 1
            errors.append((fname, description, diffs))
        else:
            passed += 1

    print(f"\n{'='*60}")
    print(f"  Ground-truth verification: {passed + failed} cases")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"{'='*60}")

    if errors:
        print(f"\nFailed cases:\n")
        for fname, desc, diffs in errors:
            print(f"  {fname}")
            print(f"    {desc[:100]}")
            if isinstance(diffs, list):
                for path, exp, act in diffs[:5]:
                    print(f"    {path}: expected={exp}, actual={act}")
                if len(diffs) > 5:
                    print(f"    ... and {len(diffs) - 5} more differences")
            else:
                print(f"    {diffs}")
            print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
