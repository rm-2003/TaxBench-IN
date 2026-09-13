# Sub-plan: Capital Gains (Other)

## Background
The "Other" capital gains section covers: Privately Owned Vehicles, Bonds, Debentures, G-Secs. Debt MF and Hybrid-Debt MF are excluded here — they are handled in `plan-mutual-funds.md`. Each asset is entered as a separate top-level key with {Sale Amount, Purchase Amount, Held for duration in years}. Calculator auto-classifies based on holding period (>12 months = LTCG @ 12.5%, ≤12 months = STCG at slab rates), except Privately Owned Vehicles which are always tax-exempt.

LTCG @ 20% exists in the reference but no assets are assigned to it yet — output keeps the field as a 0 placeholder.

---

## Script_input.json changes

Remove:
- `"Other Short Term Capital Gains": 0`
- `"Other Long Term Capital Gains": 0`

Add as separate top-level fields (each independent, calculator resolves to correct bucket):
```json
"Privately Owned Vehicle": {
    "Sale Amount": 0,
    "Purchase Amount": 0,
    "Held for duration in years": 0
},
"Bonds": {
    "Sale Amount": 0,
    "Purchase Amount": 0,
    "Held for duration in years": 0
},
"Debentures": {
    "Sale Amount": 0,
    "Purchase Amount": 0,
    "Held for duration in years": 0
},
"G-Secs": {
    "Sale Amount": 0,
    "Purchase Amount": 0,
    "Held for duration in years": 0
}
```

---

## Script_output.json changes

Replace:
```json
"STCG (Other)": 0,
"LTCG (Other)": 0
```

With:
```json
"STCG (Other)": {
    "Bonds": 0,
    "Debentures": 0,
    "G-Secs": 0,
    "Mutual Funds": 0,
    "Total": 0
},
"LTCG (Non-Equity @ 12.5%)": {
    "Bonds": 0,
    "Debentures": 0,
    "G-Secs": 0,
    "Mutual Funds": 0,
    "Total": 0
},
"LTCG (Other @ 20%)": 0
```

Also replace in Tax Computation:
```json
"Tax on STCG (Other)": 0,
"Tax on LTCG (Other)": 0
```
With:
```json
"Tax on STCG (Other)": 0,
"Tax on LTCG (Non-Equity) at 12.5%": 0,
"Tax on LTCG (Other) at 20%": 0
```

---

## tax_calculator.py changes

### Classification logic (replace old stcg_other / ltcg_other lines):

```python
OTHER_ASSETS = ["Bonds", "Debentures", "G-Secs"]

stcg_other_breakdown = {}
ltcg_noneq_12_breakdown = {}

for asset in OTHER_ASSETS:
    asset_inp = inp.get(asset, {})
    sale   = g(asset_inp, "Sale Amount")
    cost   = g(asset_inp, "Purchase Amount")
    years  = g(asset_inp, "Held for duration in years")
    gain   = sale - cost
    if gain <= 0:
        stcg_other_breakdown[asset] = 0.0
        ltcg_noneq_12_breakdown[asset] = 0.0
    elif years > 1:   # >12 months
        stcg_other_breakdown[asset] = 0.0
        ltcg_noneq_12_breakdown[asset] = gain
    else:
        stcg_other_breakdown[asset] = gain
        ltcg_noneq_12_breakdown[asset] = 0.0

# Privately Owned Vehicle — always tax-exempt, not added to any gain bucket
# (vehicle gain is computed but not included in stcg_other or ltcg totals)

stcg_other = sum(stcg_other_breakdown.values())
ltcg_other_12 = sum(ltcg_noneq_12_breakdown.values())
ltcg_other_20 = 0.0   # placeholder
```

### Capital loss set-off rules

#### Full set-off matrix

| Loss type | Offsets (in priority order) | Cannot offset |
|---|---|---|
| STCL (111A) | STCG 111A → STCG Other → LTCG 112A → LTCG Non-Equity | Salary, Other Sources, House Property |
| STCL (Other) | STCG Other → STCG 111A → LTCG 112A → LTCG Non-Equity | Salary, Other Sources, House Property |
| LTCL (112A) | LTCG 112A → LTCG Non-Equity | Any STCG; non-capital-gains heads |
| LTCL (Other) | LTCG Non-Equity → LTCG 112A | Any STCG; non-capital-gains heads |

Key rules:
- STCL can offset any capital gain (short or long term) — STCG first, then LTCG
- LTCL can only offset LTCG — never STCG
- All losses are ring-fenced within the Capital Gains head
- Carry-forward: up to 8 assessment years for both STCL and LTCL

#### Implementation approach
Currently `prior_st_losses` and `prior_lt_losses` only net against `stcg_raw`/`ltcg_raw` (111A/112A). Expand to:

```python
# 1. LTCL offsets all LTCG (112A + Non-Equity)
total_ltcg = ltcg_raw + ltcg_other_12 + mf_ltcg_other_12
ltcg_after_ltcl = max(0.0, total_ltcg - prior_lt_losses)
# Distribute remaining LTCG back proportionally to 112A vs Non-Equity

# 2. STCL offsets all STCG first, then residual offsets all LTCG
total_stcg = stcg_raw + stcg_other + mf_stcg_other
stcg_after_stcl = max(0.0, total_stcg - prior_st_losses)
residual_stcl = max(0.0, prior_st_losses - total_stcg)
# Apply residual STCL to remaining LTCG
```

### Tax computation updates:

`special_income` must include `ltcg_other_12` (taxed at 12.5%, not slab):
```python
special_income = stcg_111A + ltcg_112A + ltcg_other_12
```

STCG Other is slab-rated, so it stays in `normal_income` (already correct since it's not in `special_income`).

Add:
```python
# LTCG Other @ 12.5% — shares the ₹1.25L exemption with 112A
ltcg_exempt_remaining = max(0.0, LTCG_112A_EXEMPT - ltcg_112A)
tax_ltcg_other_12 = max(0.0, ltcg_other_12 - ltcg_exempt_remaining) * LTCG_112A_RATE
tax_ltcg_other_20 = 0.0   # placeholder

tax_stcg_other = 0.0   # slab-rated, already in tax_slab
```

Update `total_before_rebate`:
```python
total_before_rebate = tax_slab + tax_stcg_111A + tax_ltcg_112A + tax_ltcg_other_12
```

### Output assembly update:
```python
"Capital Gains": {
    "STCG (Section 111A)": round2(stcg_111A),
    "STCG (Other)": {
        **{k: round2(v) for k, v in stcg_other_breakdown.items()},
        "Total": round2(stcg_other),
    },
    "LTCG (Section 112A)": round2(ltcg_112A),
    "LTCG (Non-Equity @ 12.5%)": {
        **{k: round2(v) for k, v in ltcg_noneq_12_breakdown.items()},
        "Total": round2(ltcg_other_12),
    },
    "LTCG (Other @ 20%)": round2(ltcg_other_20),
},
```

And in Tax Computation:
```python
"Tax on STCG (Other)":          round2(tax_stcg_other),
"Tax on LTCG (Non-Equity) at 12.5%": round2(tax_ltcg_other_12),
"Tax on LTCG (Other) at 20%":   round2(tax_ltcg_other_20),
```

---

## CHANGELOG.md note (to be added to v1.2 section)
- Capital Gains Other: asset types Bonds, Debentures, G-Secs, Privately Owned Vehicle entered with Sale/Purchase/Duration; calculator classifies to STCG (slab) or LTCG @ 12.5% using 12-month threshold; vehicles always exempt; Debt MF / Hybrid-Debt MF handled in Mutual Funds plan; LTCG @ 20% placeholder
