# Plan: Synthetic Test Data Generator

## Context
The tax calculator has ~20 distinct thresholds and conditional branches. We need a generator that programmatically creates input JSONs by combining factor values across income/expense categories. The design is explicitly extensible: adding a new category = adding one new dict entry, and the number of generated cases scales automatically.

## Status: PENDING CLARIFICATION
Two questions remain unanswered before implementation:

### Q1: Combination strategy
With one parameter per category, case count = product of all factor counts. Options:
- **Full factorial** — every combination. Explodes but complete.
- **Full factorial, capped** — up to MAX_CASES, then random-sample remainder.
- **Pairwise (L2)** — every pair of factor values appears at least once. ~O(max_factors²) cases; stays manageable as categories grow.

### Q2: Factor values location
- **Config dict at top** — all factor values in one place; add category by adding a new dict entry, no logic change.
- **Hardcoded inline** — simpler but requires touching logic to change values.

---

## Agreed Design (from user)

- **One parameter per income/expense category** (e.g. HRA, NPS, LTCG, Donations = separate parameters)
- **Each parameter has N factors** (e.g. HRA: [zero, typical, high], Donations: [none, cash_excluded, mixed])
- **Generator is fully extensible**: adding a new section = adding one new entry to a top-level `PARAMETERS` dict
- **Output**: Each generated case is a valid `Script_input.json` + `_description` + `_expected` fields
- **Runner**: `run_generated_tests.py` strips meta fields, runs calculator, verifies `_expected`

---

## Proposed Category → Factor structure (starting point)

```python
PARAMETERS = {
    "salary_level": [
        {"label": "zero", "overrides": {}},
        {"label": "low",  "overrides": {"Gross Salary": {"Basic Salary": 400000, ...}}},
        {"label": "high", "overrides": {"Gross Salary": {"Basic Salary": 2400000, ...}}},
    ],
    "hra": [
        {"label": "none",           "overrides": {"Actual Rent Paid": 0}},
        {"label": "partial_exempt", "overrides": {"Actual Rent Paid": 120000}},
        {"label": "full_binding",   "overrides": {"Actual Rent Paid": 600000}},
    ],
    "capital_gains": [
        {"label": "none",       "overrides": {}},
        {"label": "stcg_only",  "overrides": {"Stock Sale Transactions": [...365 day txn...]}},
        {"label": "ltcg_below_exempt", "overrides": {"Stock Sale Transactions": [...ltcg 125000...]}},
        {"label": "ltcg_above_exempt", "overrides": {"Stock Sale Transactions": [...ltcg 200000...]}},
    ],
    "deductions_80c": [
        {"label": "none",     "overrides": {}},
        {"label": "partial",  "overrides": {"PPF": 80000, "ELSS": 40000}},
        {"label": "at_cap",   "overrides": {"PPF": 100000, "ELSS": 50000}},
        {"label": "over_cap", "overrides": {"PPF": 100000, "ELSS": 100000}},
    ],
    "nps": [
        {"label": "none",         "overrides": {}},
        {"label": "within_ccd1",  "overrides": {"NPS": {"Tier-1 Self Contribution": 30000, ...}}},
        {"label": "spills_ccd1b", "overrides": {"NPS": {"Tier-1 Self Contribution": 200000, ...}}},
    ],
    "donations": [
        {"label": "none",            "overrides": {}},
        {"label": "cash_excluded",   "overrides": {"Donations": [{"Scheme Name": "PM Cares Fund", "Amount": 3000, "Mode": "cash"}]}},
        {"label": "noncash_100pct",  "overrides": {"Donations": [{"Scheme Name": "PM Cares Fund", "Amount": 5000, "Mode": "non-cash"}]}},
        {"label": "mixed",           "overrides": {"Donations": [{"Scheme Name": "PM Cares Fund", "Amount": 5000, "Mode": "non-cash"}, {"Scheme Name": "Prime Minister's Drought Relief Fund", "Amount": 4000, "Mode": "non-cash"}]}},
    ],
    "employment_city": [
        {"label": "private_metro",   "overrides": {"Employment Type": "private", "City": "metro"}},
        {"label": "govt_nonmetro",   "overrides": {"Employment Type": "government", "City": "non-metro"}},
    ],
    "tds": [
        {"label": "none",    "overrides": {"TDS": 0}},
        {"label": "partial", "overrides": {"TDS": 20000}},
        {"label": "excess",  "overrides": {"TDS": 500000}},
    ],
}
```

---

## Files

| File | Action |
|------|--------|
| `tests/generate_test_cases.py` | Create — builds all combinations, writes `tests/generated/*.json` |
| `tests/run_generated_tests.py` | Create — runs calculator on each, verifies `_expected` fields |
| `tests/generated/` | Created at runtime by generator |

---

## Expected values
For each generated case, `_expected` is computed by the generator itself running the calculator inline — so ground truth is always in sync with the calculator version at generation time.

## Verification
`python3 tests/run_generated_tests.py` — all cases pass (since expected values are derived from the calculator itself, this validates that the runner and generator agree, and acts as a regression suite when the calculator changes).
