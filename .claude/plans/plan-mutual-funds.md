# Sub-plan: Mutual Funds

## Classification logic

All MF types are in a single `"Mutual Fund Transactions"` list. The calculator determines the rate bucket based on Type + holding period. For `"debt"` type, the purchase date additionally determines whether pre/post Apr 2023 rules apply.

### Rate table by type

| Type | Holding threshold | STCG rate | LTCG rate | Notes |
|---|---|---|---|---|
| `equity` | 12 months | 20% (→ 111A) | 12.5% above ₹1.25L (→ 112A) | ≥65% equity funds |
| `hybrid-equity` | 12 months | 20% (→ 111A) | 12.5% (→ 112A) | same as equity |
| `elss` | 36 months (lock-in) | N/A | 12.5% above ₹1.25L (→ 112A) | STCG not applicable due to lock-in |
| `debt` | 24 months (pre-2023 only) | slab (→ STCG Other) | pre-2023 + >24m: 12.5% with indexation (→ LTCG Other 12.5%); otherwise slab | purchase date drives pre/post 2023 split |
| `gold-etf` | 12 months | slab (→ STCG Other) | 12.5% (→ LTCG Other 12.5%) | listed gold/silver ETFs |
| `gold-mf` | 24 months | slab (→ STCG Other) | 12.5% (→ LTCG Other 12.5%) | gold MFs / gold FoFs |
| `international` | 24 months | slab (→ STCG Other) | 12.5% (→ LTCG Other 12.5%) | international funds / FoFs |

**Debt fund rule:** if `Purchase Date < 1 Apr 2023` and `months_held > 24` → LTCG @ 12.5% with CII indexation. Otherwise (post-2023 purchase, or held ≤ 24 months) → always slab regardless of holding period.

**CII indexation (debt pre-2023 LTCG only):** `indexed_cost = Purchase Value × (CII[sale_year] / CII[purchase_year])`. Both values looked up from the embedded `CII_TABLE` constant in the calculator using the calendar year of the respective dates.

---

## Script_input.json changes

Add top-level field (alongside `"Stock Sale Transactions"`):
```json
"Mutual Fund Transactions": [
    {
        "Type": "equity",
        "Purchase Date": "YYYY-MM-DD",
        "Sale Date": "YYYY-MM-DD",
        "Purchase Value": 0,
        "Sale Value": 0
    }
]
```

Valid `"Type"` values: `"equity"`, `"hybrid-equity"`, `"elss"`, `"debt"`, `"gold-etf"`, `"gold-mf"`, `"international"`

No `"CII at Sale"` — the embedded CII table in the calculator handles both purchase and sale year lookups using the dates provided. No `"FMV as of 31 Jan 2018"` — grandfathering does not apply to MFs.

---

## Script_output.json changes

MF gains feed into existing buckets — no new top-level output sections. The `"Mutual Funds"` sub-key is added to the `"STCG (Other)"` and `"LTCG (Other @ 12.5%)"` dicts (defined in `plan-capital-gains.md`):

```json
"STCG (Other)": {
    "Bonds": 0,
    "Debentures": 0,
    "G-Secs": 0,
    "Mutual Funds": 0,
    "Total": 0
},
"LTCG (Other @ 12.5%)": {
    "Bonds": 0,
    "Debentures": 0,
    "G-Secs": 0,
    "Mutual Funds": 0,
    "Total": 0
}
```

Equity/hybrid-equity/ELSS gains flow into existing `"STCG (Section 111A)"` and `"LTCG (Section 112A)"` fields — no output change needed there.

---

## tax_calculator.py changes

### Embedded CII table (add as constant):
```python
CII_TABLE = {
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117, 2006: 122,
    2007: 129, 2008: 137, 2009: 148, 2010: 167, 2011: 184, 2012: 200,
    2013: 220, 2014: 240, 2015: 254, 2016: 264, 2017: 272, 2018: 280,
    2019: 289, 2020: 301, 2021: 317, 2022: 331, 2023: 348, 2024: 363,
}
DEBT_PRE_2023_CUTOFF = date(2023, 4, 1)
```

### MF classification function:
```python
EQUITY_LIKE_TYPES = {"equity", "hybrid-equity", "elss"}
ELSS_LOCK_IN_MONTHS = 36

def classify_mf_transaction(txn):
    fund_type   = txn.get("Type", "").lower()
    purchase_dt = parse_date(txn.get("Purchase Date", ""))
    sale_dt     = parse_date(txn.get("Sale Date", ""))
    pv = g(txn, "Purchase Value")
    sv = g(txn, "Sale Value")

    if purchase_dt is None or sale_dt is None or pv == 0:
        return None

    months_held = (sale_dt - purchase_dt).days / 30.44

    if fund_type == "elss":
        if months_held < ELSS_LOCK_IN_MONTHS:
            return ("ltcg_112A", 0.0)   # still locked in, no taxable event
        return ("ltcg_112A", sv - pv)

    elif fund_type in EQUITY_LIKE_TYPES:
        gain = sv - pv
        return ("stcg_111A", gain) if months_held <= 12 else ("ltcg_112A", gain)

    elif fund_type == "debt":
        is_pre_2023 = purchase_dt < DEBT_PRE_2023_CUTOFF
        if is_pre_2023 and months_held > 24:
            cii_p = CII_TABLE.get(purchase_dt.year, 100)
            cii_s = CII_TABLE.get(sale_dt.year, cii_p)
            indexed_cost = pv * (cii_s / cii_p)
            return ("ltcg_other_12_mf", sv - indexed_cost)
        else:
            return ("stcg_other_mf", sv - pv)   # always slab

    elif fund_type == "gold-etf":
        gain = sv - pv
        return ("stcg_other_mf", gain) if months_held <= 12 else ("ltcg_other_12_mf", gain)

    elif fund_type in {"gold-mf", "international"}:
        gain = sv - pv
        return ("stcg_other_mf", gain) if months_held <= 24 else ("ltcg_other_12_mf", gain)

    return None
```

### Integrate into main calculate() flow:
After stock transactions loop, before loss netting:
```python
mf_stcg_111A     = 0.0
mf_ltcg_112A     = 0.0
mf_stcg_other    = 0.0
mf_ltcg_other_12 = 0.0

for txn in inp.get("Mutual Fund Transactions", []):
    result = classify_mf_transaction(txn)
    if result is None:
        continue
    bucket, gain = result
    if bucket == "stcg_111A":          mf_stcg_111A     += gain
    elif bucket == "ltcg_112A":        mf_ltcg_112A     += gain
    elif bucket == "stcg_other_mf":    mf_stcg_other    += gain
    elif bucket == "ltcg_other_12_mf": mf_ltcg_other_12 += gain

# Merge equity MF gains into raw totals before loss netting
stcg_raw += mf_stcg_111A
ltcg_raw += mf_ltcg_112A

# Non-equity MF gains go into breakdown dicts after loss netting
stcg_other_breakdown["Mutual Funds"]    = round2(mf_stcg_other)
ltcg_other_12_breakdown["Mutual Funds"] = round2(mf_ltcg_other_12)
```

### Capital loss set-off rules (update existing logic)

Current calculator applies prior losses independently to each gain bucket. This must be updated to reflect the asymmetric set-off rules:

**Within the same year (intra-year, not yet in calculator):**
- STCL offsets STCG first; any remaining STCL then offsets LTCG
- LTCL offsets LTCG only — cannot touch STCG

**Prior-year carry-forward (existing `Long Term Capital Loss` / `Short Term Capital Loss` input fields):**
- Prior STCL → offsets STCG first, then any residual offsets LTCG
- Prior LTCL → offsets LTCG only

Updated loss netting logic:
```python
prior_ltcl = sum(g(t, "Loss Amount") for t in inp.get("Long Term Capital Loss", []))
prior_stcl = sum(g(t, "Loss Amount") for t in inp.get("Short Term Capital Loss", []))

# LTCL offsets LTCG only
ltcg_after_ltcl = max(0.0, ltcg_raw - prior_ltcl)

# STCL offsets STCG first, residual offsets LTCG
stcg_after_stcl = max(0.0, stcg_raw - prior_stcl)
residual_stcl   = max(0.0, prior_stcl - stcg_raw)
ltcg_112A       = max(0.0, ltcg_after_ltcl - residual_stcl)
stcg_111A       = stcg_after_stcl

# ₹1.25L exemption applies to net LTCG after all set-offs
tax_ltcg_112A = max(0.0, ltcg_112A - LTCG_112A_EXEMPT) * LTCG_112A_RATE
```

Note: capital losses are ring-fenced within the capital gains head — they cannot offset salary, house property, or any other income head.

---

## Data Generator Notes

Test cases to cover for MF-specific edge cases:

### ELSS lock-in boundary
- Sale at exactly 35 months → locked in, gain = 0 (no taxable event)
- Sale at exactly 36 months → LTCG @ 12.5% applies

### Debt fund pre/post 2023 boundary
- Purchase date 31 Mar 2023, held > 24 months → LTCG @ 12.5% with indexation
- Purchase date 1 Apr 2023, held > 24 months → slab rate (no LTCG benefit)

### Capital loss set-off asymmetry
- STCL > STCG: residual STCL reduces LTCG (STCL is "stronger")
- LTCL with no LTCG: loss carries forward, STCG is untouched
- STCL + LTCL both present: LTCL applied to LTCG first, then residual STCL applied to remaining LTCG

### LTCL + ₹1.25L exemption interaction
- LTCG = ₹2L, prior LTCL = ₹50k → net LTCG = ₹1.5L → taxable = ₹25k (after ₹1.25L exemption)
- The loss compounds the benefit of the exemption — verify net taxable after set-off and exemption

---

## CHANGELOG.md note (to be added to v1.2 section)
- Mutual Funds: single `"debt"` type (pre/post Apr 2023 split handled by purchase date); CII indexation via embedded table (no user input); equity/ELSS/hybrid-equity → 111A/112A buckets; debt/gold/international → Other buckets
- Capital loss set-off: corrected to asymmetric rules — STCL offsets STCG then LTCG; LTCL offsets LTCG only; ₹1.25L exemption applied after set-off
