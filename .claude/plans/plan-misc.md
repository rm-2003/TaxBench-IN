# Sub-plan: Misc Changes

Covers: Section 16(ii), 80C narrowing, 80E, 80TTA/80TTB, 80G mode expansion, 80EE/80P removal.

---

## Script_input.json changes

### A. Change top-level `"Age"` field from string to numeric:
```json
"Age": 35
```
Replace the current `"Age": "<60"` string. All downstream age checks in the calculator use `>= 60` (senior) and `> 80` (super senior) numeric comparisons.

### B. Add to `"Gross Salary"` dict:
```json
"Entertainment Allowance": 0
```

### B. Remove these 80C fields entirely:
- `"Life Insurance Premium": 0`
- `"Tax Saving FD (5 Year)": 0`
- `"Home Loan Principal": 0`
- `"Stamp Duty and Registration": 0`

### C. Replace `"Education Loan Interest": 0` with:
```json
"Education Loan Interest": {
    "Interest Paid": 0,
    "Year of Repayment": 0
}
```
Year of Repayment = current year number since loan was taken (e.g. loan taken Aug 2020, payment in Aug 2025 → Year 6). Deduction = 0 if Year of Repayment > 8.

### D. Update `"Donations"` template — no structural change, but update the Mode comment/example:
Valid modes for `"Mode"`: `"cash"`, `"cheque"`, `"upi"`, `"credit card"`, `"net banking"`. Cash > ₹2,000 excluded.

---

## Script_output.json changes

### A. Remove from Deductions:
- `"80EE": 0`
- `"80P": 0`

---

## tax_calculator.py changes

### A. Section 16(ii) — government employees only:
```python
entertainment = g(gs, "Entertainment Allowance")
if employment == "government":
    s16_ii = min(5_000, 0.20 * g(gs, "Basic Salary"), entertainment)
else:
    s16_ii = 0.0
```

### B. Remove from `c80_items` sum:
```python
# Remove these four lines:
g(inp, "Life Insurance Premium"),
g(inp, "Tax Saving FD (5 Year)"),
g(inp, "Home Loan Principal"),
g(inp, "Stamp Duty and Registration"),
```

### C. 80E — enforce 8-year limit:
```python
edu = inp.get("Education Loan Interest", {})
if isinstance(edu, dict):
    edu_interest = g(edu, "Interest Paid")
    edu_year     = g(edu, "Year of Repayment")
    c80e = edu_interest if 1 <= edu_year <= 8 else 0.0
else:
    c80e = 0.0
```

### D. 80TTA / 80TTB — age-gated:
```python
age = inp.get("Age", 30)   # numeric age
if age >= 60:
    c80tta = 0.0
    c80ttb = min(50_000, savings_bank_interest + deposit_interest)
else:
    c80tta = min(10_000, savings_bank_interest)
    c80ttb = 0.0
```

### E. Remove `c80ee` and `c80p`:
- Delete lines: `c80d = c80e = c80ee = c80tta = c80ttb = c80p = 0.0`
- Replace with individual assignments for c80d, c80e, c80tta, c80ttb (see above)
- Remove `c80ee` and `c80p` from `total_deductions` sum
- Remove `"80EE"` and `"80P"` from output dict

### F. 80G — no code change needed:
The existing check `if mode == "cash" and amount > 2_000: continue` already passes all non-cash modes (cheque, UPI, credit card, net banking) through correctly. The reference update just clarifies the valid mode names.

---

## CHANGELOG.md notes (to be added to v1.2 section)
- Section 16(ii): implemented for government employees — MIN(₹5,000, 20% Basic Salary, entertainment allowance received); input field added to Gross Salary
- 80C narrowed: LIP, Tax Saving FD (5yr), Home Loan Principal, Stamp Duty removed from eligible instruments
- 80E: education loan interest, enforced 8-year limit on year of repayment
- 80TTA: min(₹10,000, savings bank interest) for age < 60
- 80TTB: min(₹50,000, savings + deposit interest) for age 60+; mutually exclusive with 80TTA
- 80EE, 80P: removed from schema and calculator (out of scope)
- 80G: mode field now accepts cheque/UPI/credit card/net banking in addition to cash; cash > ₹2,000 still excluded
