# Sub-plan: 80D — Medical Insurance

## Input structure design

`"Health Insurance"` becomes a list of payment entries. Each entry is one payment event (one premium or one checkup). The calculator aggregates them, enforces beneficiary eligibility, applies limits, and returns a single `c80d` number.

---

## Script_input.json changes

Replace the old flat `"Health Insurance"` dict with a list:

```json
"Health Insurance": [
    {
        "Payment Purpose": "insurance premium",
        "Number of Years Paid": 1,
        "Beneficiary": "self",
        "Beneficiary Age": 35,
        "Paid By": "self",
        "Payment Mode": "cheque",
        "Amount": 0
    },
    {
        "Payment Purpose": "preventive health checkup",
        "Beneficiary": "self",
        "Beneficiary Age": 35,
        "Paid By": "self",
        "Payment Mode": "cash",
        "Amount": 0
    }
]
```

Field rules:
- `"Payment Purpose"`: `"insurance premium"` | `"preventive health checkup"`
- `"Number of Years Paid"`: integer ≥ 1 — only relevant for `"insurance premium"`;
- `"Beneficiary"`: `"self"` | `"spouse"` | `"children"` | `"parents"` — any other value → entry excluded
- `"Beneficiary Age"`: numeric age; used to determine senior citizen status (≥ 60 → senior)
- `"Paid By"`: `"self"` | `"group medical insurance"` — if `"group medical insurance"` → entry excluded
- `"Payment Mode"`: for `"insurance premium"` — must be non-cash (`"cheque"`, `"upi"`, `"credit card"`, `"net banking"`); cash → entry excluded. For `"preventive health checkup"` — all modes valid
- `"Amount"`: total amount paid (for multi-year premium, calculator divides by `Number of Years Paid`)

---

## Script_output.json changes

`"80D": 0` — no structural change, remains a single computed number.

---

## tax_calculator.py changes

### Beneficiary grouping logic

Entries are split into two buckets for the purpose of applying the two separate limits:
- **Self bucket**: beneficiary is `"self"`, `"spouse"`, or `"children"`
- **Parents bucket**: beneficiary is `"parents"`

Senior citizen status per bucket:
- Self bucket: senior if `Beneficiary Age >= 60` for the self/spouse entry (or use the top-level `Age` field as fallback for self)
- Parents bucket: senior if any parent entry has `Beneficiary Age >= 60`

Limits:
- Self bucket: ₹50,000 if senior, ₹25,000 otherwise
- Parents bucket: ₹50,000 if any parent is senior, ₹25,000 otherwise

### Preventive checkup cap

₹5,000 total across **all entries** (both self bucket and parents bucket combined) — not ₹5,000 per bucket.

### Calculation logic

```python
VALID_BENEFICIARIES = {"self", "spouse", "children", "parents"}
NON_CASH_MODES = {"cheque", "upi", "credit card", "net banking"}

def compute_80d(entries, age):
    self_prem = 0.0
    parents_prem = 0.0
    total_checkup = 0.0
    self_senior = False
    parents_senior = False

    # Top-level numeric age as fallback for self senior check
    if age >= 60:
        self_senior = True

    for e in entries:
        purpose     = e.get("Payment Purpose", "").lower()
        beneficiary = e.get("Beneficiary", "").lower()
        paid_by     = e.get("Paid By", "self").lower()
        mode        = e.get("Payment Mode", "cheque").lower()
        amount      = e.get("Amount", 0)
        yrs         = max(1, e.get("Number of Years Paid", 1))
        ben_age     = e.get("Beneficiary Age", 0)

        # Exclude ineligible entries
        if beneficiary not in VALID_BENEFICIARIES:
            continue
        if paid_by == "group medical insurance":
            continue

        if purpose == "insurance premium":
            if mode == "cash":
                continue   # cash not allowed for premium
            annual = amount / yrs
            if beneficiary in {"self", "spouse", "children"}:
                self_prem += annual
                if ben_age >= 60:
                    self_senior = True
            elif beneficiary == "parents":
                parents_prem += annual
                if ben_age >= 60:
                    parents_senior = True

        elif purpose == "preventive health checkup":
            # all modes valid; accumulate for global ₹5k cap
            total_checkup += amount

    # Apply global ₹5k preventive checkup cap
    total_checkup = min(total_checkup, 5_000)

    # Apply category limits
    self_limit    = 50_000 if self_senior else 25_000
    parents_limit = 50_000 if parents_senior else 25_000

    # Distribute checkup into the two buckets proportionally only if both have premiums,
    # otherwise assign to whichever bucket has any entry.
    # Simpler rule: add checkup entirely to self bucket (no split — checkup is personal).
    self_80d    = min(self_prem + total_checkup, self_limit)
    parents_80d = min(parents_prem, parents_limit)

    return self_80d + parents_80d
```

Call site in `calculate()`:
```python
c80d = compute_80d(inp.get("Health Insurance", []), inp.get("Age", 30))
```

Note: top-level `"Age"` field in `Script_input.json` changes from the string `"<60"` to a **numeric age** (e.g. `35`). All age checks in `tax_calculator.py` that currently compare against `"60-80"` / `">80"` must be updated to `>= 60` / `> 80` numeric comparisons. This affects: 80D, 80TTB, any other age-gated logic.

---

## Key rules summary
- Beneficiaries: self, spouse, children, parents only — siblings, grandparents, working children, others excluded
- Group medical insurance entries: always excluded
- Premium mode: must be non-cash (cheque/UPI/credit card/net banking); cash → excluded
- Checkup mode: all modes valid
- Multi-year premium: annual = total ÷ years paid
- Preventive checkup: single ₹5,000 cap across all entries combined
- Senior citizen: age ≥ 60 in any entry for that bucket raises the limit to ₹50,000
- Self/family limit applied to (self_prem + checkup); parents limit applied to parents_prem alone

---

## CHANGELOG.md note (to be added to v1.2 section)
- 80D: restructured as list of payment entries; per-entry beneficiary filtering (self/spouse/children/parents only), paid-by check (group insurance excluded), mode check (premium must be non-cash), multi-year premium split, single ₹5k preventive checkup cap across all entries, age-based limits (₹25k/₹50k)
