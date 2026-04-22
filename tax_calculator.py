"""
v1.1_calculator.py
Converts a v1.1_script_input.json into a filled v1.1_script_output.json.

Usage:
    python3 v1.1_calculator.py <input.json> <output.json>
"""

import json
import sys
from datetime import date

# ---------------------------------------------------------------------------
# Configurable constants — update here to change FY or regime assumptions
# ---------------------------------------------------------------------------

# New Regime FY 2025-26 slab rates: (upper_limit_inclusive, marginal_rate)
# Income up to the upper limit is taxed at that rate on the incremental amount.
NEW_REGIME_SLABS = [
    (400_000,       0.00),
    (800_000,       0.05),
    (1_200_000,     0.10),
    (1_600_000,     0.15),
    (2_000_000,     0.20),
    (2_400_000,     0.25),
    (float("inf"),  0.30),
]

REBATE_87A_THRESHOLD = 1_200_000   # 12 L (new regime FY 2025-26)
REBATE_87A_MAX       = 60_000
STANDARD_DEDUCTION_OLD = 50_000    # Section 16(ia) old regime
STANDARD_DEDUCTION_NEW = 75_000    # Section 16(ia) new regime
LTCG_112A_EXEMPT     = 1_25_000    # 1.25 L exemption before 12.5% kicks in
LTCG_112A_RATE       = 0.125
STCG_111A_RATE       = 0.20
CESS_RATE            = 0.04

OLD_REGIME_SURCHARGE_RATES = [
    (5_000_000,    0.00),
    (10_000_000,   0.10),
    (20_000_000,   0.15),
    (50_000_000,   0.25),
    (float("inf"), 0.37),
]

NEW_REGIME_SURCHARGE_RATES = [
    (5_000_000,    0.00),
    (10_000_000,   0.10),
    (20_000_000,   0.15),
    (50_000_000,   0.25),
    (float("inf"), 0.25),
]

SURCHARGE_BOUNDARIES = [5_000_000, 10_000_000, 20_000_000, 50_000_000]

CII_TABLE = {
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117, 2006: 122,
    2007: 129, 2008: 137, 2009: 148, 2010: 167, 2011: 184, 2012: 200,
    2013: 220, 2014: 240, 2015: 254, 2016: 264, 2017: 272, 2018: 280,
    2019: 289, 2020: 301, 2021: 317, 2022: 331, 2023: 348, 2024: 363,
    2025: 376,
}
DEBT_PRE_2023_CUTOFF = date(2023, 4, 1)
EQUITY_LIKE_TYPES    = {"equity", "hybrid-equity", "elss"}
ELSS_LOCK_IN_MONTHS  = 36

def fy_start(d: date) -> int:
    """Return the FY start year for a date (Apr–Mar cycle). Jan 2024 → 2023 (FY 2023-24)."""
    return d.year if d.month >= 4 else d.year - 1

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
            return ("ltcg_112A", 0.0)
        return ("ltcg_112A", sv - pv)

    elif fund_type in EQUITY_LIKE_TYPES:
        gain = sv - pv
        return ("stcg_111A", gain) if months_held <= 12 else ("ltcg_112A", gain)

    elif fund_type == "debt":
        is_pre_2023 = purchase_dt < DEBT_PRE_2023_CUTOFF
        if is_pre_2023 and months_held > 24:
            cii_p = CII_TABLE.get(fy_start(purchase_dt), 100)
            cii_s = CII_TABLE.get(fy_start(sale_dt), cii_p)
            indexed_cost = pv * (cii_s / cii_p)
            return ("ltcg_other_12_mf", sv - indexed_cost)
        else:
            return ("stcg_other_mf", sv - pv)

    elif fund_type == "gold-etf":
        gain = sv - pv
        return ("stcg_other_mf", gain) if months_held <= 12 else ("ltcg_other_12_mf", gain)

    elif fund_type in {"gold-mf", "international"}:
        gain = sv - pv
        return ("stcg_other_mf", gain) if months_held <= 24 else ("ltcg_other_12_mf", gain)

    return None


VALID_BENEFICIARIES = {"self", "spouse", "children", "parents"}

def compute_80d(entries, age):
    self_prem = 0.0
    parents_prem = 0.0
    total_checkup = 0.0
    self_senior = age >= 60
    parents_senior = False

    for e in entries:
        purpose     = e.get("Payment Purpose", "").lower()
        beneficiary = e.get("Beneficiary", "").lower()
        paid_by     = e.get("Paid By", "self").lower()
        mode        = e.get("Payment Mode", "cheque").lower()
        amount      = e.get("Amount", 0)
        yrs         = max(1, e.get("Number of Years Paid", 1))
        ben_age     = e.get("Beneficiary Age", 0)

        if beneficiary not in VALID_BENEFICIARIES:
            continue
        if paid_by == "group medical insurance":
            continue

        if purpose == "insurance premium":
            if mode == "cash":
                continue
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
            total_checkup += amount

    total_checkup = min(total_checkup, 5_000)
    self_limit    = 50_000 if self_senior else 25_000
    parents_limit = 50_000 if parents_senior else 25_000
    self_80d      = min(self_prem + total_checkup, self_limit)
    parents_80d   = min(parents_prem, parents_limit)
    return self_80d + parents_80d


def compute_surcharge_with_relief(total_taxable, tax_after_rebate, surcharge_rate, slabs, surcharge_table):
    if surcharge_rate == 0.0:
        return 0.0
    crossed_boundary = None
    for b in SURCHARGE_BOUNDARIES:
        if total_taxable > b:
            crossed_boundary = b
    if crossed_boundary is None:
        return 0.0
    surcharge_raw    = tax_after_rebate * surcharge_rate
    tax_at_boundary  = compute_slab_tax(crossed_boundary, slabs)
    tax_with_surcharge = tax_after_rebate + surcharge_raw
    excess_income    = total_taxable - crossed_boundary
    excess_tax       = tax_with_surcharge - tax_at_boundary
    relief           = max(0.0, excess_tax - excess_income)
    return max(0.0, surcharge_raw - relief)


FULL_EXEMPT_SCHEMES = {
    "National Defence Fund",
    "PM Cares Fund",
    "National Sports Fund",
    "National Cultural Fund",
}
HALF_EXEMPT_SCHEMES = {
    "Prime Minister's Drought Relief Fund",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def g(d, *keys, default=0):
    """Safely get a nested value from a dict, returning default if missing."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def compute_slab_tax(income: float, slabs: list) -> float:
    """Compute income tax given a positive income and a slab table."""
    if income <= 0:
        return 0.0
    tax = 0.0
    prev = 0
    for upper, rate in slabs:
        if income <= prev:
            break
        taxable_in_slab = min(income, upper) - prev
        tax += taxable_in_slab * rate
        prev = upper
    return tax


def parse_date(s: str):
    """Parse YYYY-MM-DD string to date object; returns None on failure."""
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def round2(x: float) -> float:
    return round(x, 2)


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

def calculate(inp: dict) -> dict:
    employment = inp.get("Employment Type", "private").lower()
    regime     = inp.get("Tax Regime", "new").lower()   # "old" or "new"
    city       = inp.get("City", "non-metro").lower()

    gs = inp.get("Gross Salary", {})

    # ------------------------------------------------------------------
    # Under Head Salaries
    # ------------------------------------------------------------------
    gross_salary = sum([
        g(gs, "Basic Salary"),
        g(gs, "Dearness Allowance"),
        g(gs, "HRA"),
        g(gs, "Conveyance Allowance"),
        g(gs, "Medical Allowance"),
        g(gs, "Bonuses and Incentives"),
        g(gs, "Overtime Pay"),
        g(gs, "LTA"),
        g(gs, "Special Allowance"),
    ])

    basic_da = g(gs, "Basic Salary") + g(gs, "Dearness Allowance")
    metro_pct = 0.50 if "metro" in city else 0.40

    # Section 10(13A) — HRA exemption
    hra_received  = g(gs, "HRA")
    rent_paid     = g(inp, "Actual Rent Paid")
    hra_candidate = rent_paid - 0.10 * basic_da
    hra_10_13A = max(0.0, min(
        hra_received,
        metro_pct * basic_da,
        hra_candidate,
    ))

    # Section 10(5) — LTA exemption
    lta_in_salary    = g(gs, "LTA")
    lta_claimed      = g(inp, "LTA Travel Expenses Claimed")
    lta_10_5         = min(lta_in_salary, lta_claimed)

    # Section 16(ia) — standard deduction
    std_ded = STANDARD_DEDUCTION_NEW if regime == "new" else STANDARD_DEDUCTION_OLD
    s16_ia  = min(std_ded, gross_salary)

    # Section 16(ii) — entertainment allowance (govt only)
    entertainment = g(gs, "Entertainment Allowance")
    if employment == "government":
        s16_ii = min(5_000, 0.20 * g(gs, "Basic Salary"), entertainment)
    else:
        s16_ii = 0.0

    # Section 16(iii) — professional tax (max 2,500)
    s16_iii = min(2_500, g(inp, "Professional Tax"))

    net_salary = gross_salary - hra_10_13A - lta_10_5 - s16_ia - s16_ii - s16_iii

    # ------------------------------------------------------------------
    # Capital Gains
    # ------------------------------------------------------------------
    stcg_raw = 0.0
    ltcg_raw = 0.0

    for txn in inp.get("Stock Sale Transactions", []):
        sale_price  = g(txn, "Sale Price")
        cost_price  = g(txn, "Cost Price")
        quantity    = g(txn, "Quantity")
        brokerage   = g(txn, "Brokerage")
        fmv         = g(txn, "FMV as of 31 Jan 2018")
        purchase_dt = parse_date(txn.get("Purchase Date", ""))
        sale_dt     = parse_date(txn.get("Sale Date", ""))

        if purchase_dt is None or sale_dt is None:
            continue
        if quantity == 0:
            continue

        days_held    = (sale_dt - purchase_dt).days
        is_long_term = days_held > 365

        if is_long_term:
            effective_cost_per_share = max(cost_price, fmv)
            gain = (sale_price - effective_cost_per_share) * quantity - brokerage
            ltcg_raw += gain
        else:
            gain = (sale_price - cost_price) * quantity - brokerage
            stcg_raw += gain

    # Mutual Fund transactions
    mf_stcg_111A     = 0.0
    mf_ltcg_112A     = 0.0
    mf_stcg_other    = 0.0
    mf_ltcg_other_12 = 0.0

    for txn in inp.get("Mutual Fund Transactions", []):
        result = classify_mf_transaction(txn)
        if result is None:
            continue
        bucket, gain = result
        if bucket == "stcg_111A":           mf_stcg_111A     += gain
        elif bucket == "ltcg_112A":         mf_ltcg_112A     += gain
        elif bucket == "stcg_other_mf":     mf_stcg_other    += gain
        elif bucket == "ltcg_other_12_mf":  mf_ltcg_other_12 += gain

    stcg_raw += mf_stcg_111A
    ltcg_raw += mf_ltcg_112A

    # Capital losses are eligible for set-off only up to 8 assessment years.
    # "Financial Year" format is "YYYY-YY" (e.g. "2017-18"); parse start year.
    # Current AY start year = fy_start(today) + 1; loss AY start = loss FY start + 1.
    # Loss is expired if (current_ay_start - loss_ay_start) > 8, i.e. loss_fy_start < current_ay_start - 9.
    current_ay_start = 2025  # AY 2025-26
    def _loss_eligible(entry):
        fy = str(entry.get("Financial Year", ""))
        try:
            loss_fy_start = int(fy[:4])
        except ValueError:
            return False
        return (current_ay_start - loss_fy_start) <= 8

    prior_lt_losses = sum(
        g(t, "Loss Amount") for t in inp.get("Long Term Capital Loss", []) if _loss_eligible(t)
    )
    prior_st_losses = sum(
        g(t, "Loss Amount") for t in inp.get("Short Term Capital Loss", []) if _loss_eligible(t)
    )

    # Asymmetric loss set-off: STCL offsets STCG first, residual offsets LTCG; LTCL offsets LTCG only
    ltcg_after_ltcl  = max(0.0, ltcg_raw - prior_lt_losses)
    stcg_after_stcl  = max(0.0, stcg_raw - prior_st_losses)
    residual_stcl    = max(0.0, prior_st_losses - stcg_raw)
    stcg_111A        = stcg_after_stcl
    ltcg_112A        = max(0.0, ltcg_after_ltcl - residual_stcl)

    stcg_other = g(inp, "Other Short Term Capital Gains")
    ltcg_other = g(inp, "Other Long Term Capital Gains")

    # ------------------------------------------------------------------
    # Income from Other Sources
    # ------------------------------------------------------------------
    savings_bank_interest = g(inp, "Savings Bank Interest")
    deposit_interest      = g(inp, "Deposit Interest")
    other_interest        = g(inp, "Other Interest")
    epf_taxable_interest  = g(inp, "EPF Taxable Interest")

    # ------------------------------------------------------------------
    # Gross Total Income
    # ------------------------------------------------------------------
    gross_total = sum([
        net_salary,
        stcg_111A, stcg_other, mf_stcg_other,
        ltcg_112A, ltcg_other, mf_ltcg_other_12,
        savings_bank_interest, deposit_interest,
        other_interest, epf_taxable_interest,
    ])

    # ------------------------------------------------------------------
    # Deductions
    # ------------------------------------------------------------------

    # 80C
    epf_employee = (
        g(inp, "EPF", "Employee Contribution", "Deducted from Salary")
        + g(inp, "EPF", "Employee Contribution", "Voluntary")
    )
    c80_items = sum([
        g(inp, "PPF"),
        epf_employee,
        g(inp, "ELSS"),
        g(inp, "NSC"),
        g(inp, "Sukanya Samriddhi Yojana"),
        g(inp, "SCSS"),
    ])
    c80 = min(c80_items, 150_000)

    # 80CCC
    pension    = inp.get("Pension Scheme Premium", {})
    pen_amount = g(pension, "Amount")
    pen_years  = max(1, g(pension, "Number of Years Paid"))
    c80ccc     = pen_amount / pen_years

    # 80CCD(1)
    nps = inp.get("NPS", {})
    nps_self       = g(nps, "Tier-1 Self Contribution")
    nps_employer   = g(nps, "Tier-1 Employer Contribution")
    c80ccd1_limit  = 0.10 * basic_da
    c80ccd1        = min(nps_self, c80ccd1_limit)

    # 80CCE — combined cap of 1,50,000
    c80cce_uncapped = c80 + c80ccc + c80ccd1
    c80cce_total    = min(c80cce_uncapped, 150_000)

    # Scale down individual components proportionally if capped; third is derived
    # so the three always sum to exactly c80cce_total (no rounding gap)
    if c80cce_uncapped > 0:
        scale            = c80cce_total / c80cce_uncapped
        c80_reported     = round2(c80 * scale)
        c80ccc_reported  = round2(c80ccc * scale)
        c80ccd1_reported = round2(c80cce_total - c80_reported - c80ccc_reported)
    else:
        c80_reported = c80ccc_reported = c80ccd1_reported = 0.0

    # 80CCD(1B) — extra 50k outside 80CCE
    c80ccd1b = min(max(0.0, nps_self - c80ccd1), 50_000)

    # 80CCD(2) — employer NPS contribution
    # New regime: 14% for all; Old regime: 14% for govt, 10% for others
    if regime == "new" or employment == "government":
        c80ccd2_pct = 0.14
    else:
        c80ccd2_pct = 0.10
    c80ccd2 = min(nps_employer, c80ccd2_pct * basic_da)

    # 80G — Donations
    c80g = 0.0
    for donation in inp.get("Donations", []):
        amount = g(donation, "Amount")
        mode   = donation.get("Mode", "").lower()
        scheme = donation.get("Scheme Name", "")
        if mode == "cash" and amount > 2_000:
            continue
        if scheme in FULL_EXEMPT_SCHEMES:
            c80g += amount
        elif scheme in HALF_EXEMPT_SCHEMES:
            c80g += amount * 0.50

    age = inp.get("Age", 30)

    # 80D
    c80d = compute_80d(inp.get("Health Insurance", []), age)

    # 80E — education loan interest, 8-year repayment limit
    edu = inp.get("Education Loan Interest", {})
    if isinstance(edu, dict):
        edu_interest = g(edu, "Interest Paid")
        edu_year     = g(edu, "Year of Repayment")
        c80e = edu_interest if 1 <= edu_year <= 8 else 0.0
    else:
        c80e = 0.0

    # 80TTA / 80TTB — age-gated; mutually exclusive
    if age >= 60:
        c80tta = 0.0
        c80ttb = min(50_000, savings_bank_interest + deposit_interest)
    else:
        c80tta = min(10_000, savings_bank_interest)
        c80ttb = 0.0

    total_deductions = sum([
        c80cce_total,
        c80ccd1b,
        c80ccd2,
        c80g,
        c80d, c80e, c80tta, c80ttb,
    ])

    # ------------------------------------------------------------------
    # Total Taxable Income
    # ------------------------------------------------------------------
    total_taxable = gross_total - total_deductions

    # ------------------------------------------------------------------
    # Tax Computation
    # ------------------------------------------------------------------

    # Special-rate incomes (outside normal slabs)
    special_income = stcg_111A + ltcg_112A + ltcg_other + mf_ltcg_other_12
    normal_income  = max(0.0, total_taxable - special_income)

    tax_slab       = compute_slab_tax(normal_income, NEW_REGIME_SLABS)
    tax_stcg_111A  = stcg_111A * STCG_111A_RATE
    tax_stcg_other = 0.0  # STCG Other taxed at slab rates — already in tax_slab
    tax_ltcg_112A  = max(0.0, ltcg_112A - LTCG_112A_EXEMPT) * LTCG_112A_RATE
    tax_ltcg_other = 0.0  # pass-through placeholder
    # MF LTCG Other @ 12.5% — no ₹1.25L exemption (that applies to equity 112A only)
    tax_mf_ltcg_other_12 = mf_ltcg_other_12 * LTCG_112A_RATE

    total_before_rebate = tax_slab + tax_stcg_111A + tax_ltcg_112A + tax_mf_ltcg_other_12

    # Section 87A rebate — applies only to slab tax, not special-rate taxes
    if total_taxable <= REBATE_87A_THRESHOLD:
        rebate_87A = min(tax_slab, REBATE_87A_MAX)
    else:
        income_above_threshold = max(0.0, normal_income - REBATE_87A_THRESHOLD)
        rebate_87A = max(0.0, tax_slab - income_above_threshold)

    tax_after_rebate = total_before_rebate - rebate_87A

    # Surcharge
    surcharge_table = NEW_REGIME_SURCHARGE_RATES if regime == "new" else OLD_REGIME_SURCHARGE_RATES
    slab_table      = NEW_REGIME_SLABS
    surcharge_rate  = 0.0
    for upper, rate in surcharge_table:
        if total_taxable <= upper:
            surcharge_rate = rate
            break
    surcharge = compute_surcharge_with_relief(
        total_taxable, tax_after_rebate, surcharge_rate, slab_table, surcharge_table
    )
    cess               = (tax_after_rebate + surcharge) * CESS_RATE
    total_tax_liability = tax_after_rebate + surcharge + cess

    tds     = g(inp, "TDS")
    net_tax = total_tax_liability - tds   # negative = refund

    # ------------------------------------------------------------------
    # Assemble output
    # ------------------------------------------------------------------
    output = {
        "Under Head Salaries": {
            "Gross Salary": round2(gross_salary),
            "Exemptions": {
                "Section 10(13A)": round2(hra_10_13A),
                "Section 10(5)":   round2(lta_10_5),
            },
            "Section 16(ia)":  round2(s16_ia),
            "Section 16(ii)":  round2(s16_ii),
            "Section 16(iii)": round2(s16_iii),
            "Net Salary":      round2(net_salary),
        },
        "Capital Gains": {
            "STCG (Section 111A)": round2(stcg_111A),
            "STCG (Other)":        round2(stcg_other),
            "LTCG (Section 112A)": round2(ltcg_112A),
            "LTCG (Other)":        round2(ltcg_other),
        },
        "Income from Other Sources": {
            "Savings Bank Interest": round2(savings_bank_interest),
            "Deposit Interest":      round2(deposit_interest),
            "Other Interest": {
                "EPF Taxable Interest": round2(epf_taxable_interest),
            },
        },
        "Gross Total Income": round2(gross_total),
        "Deductions": {
            "80C":       round2(c80_reported),
            "80CCC":     round2(c80ccc_reported),
            "80CCD(1)":  round2(c80ccd1_reported),
            "80CCD(1B)": round2(c80ccd1b),
            "80CCD(2)":  round2(c80ccd2),
            "80D":   round2(c80d),
            "80E":   round2(c80e),
            "80G":   round2(c80g),
            "80TTA": round2(c80tta),
            "80TTB": round2(c80ttb),
            "Total Deductions": round2(total_deductions),
        },
        "Total Taxable Income": round2(total_taxable),
        "Tax Computation": {
            "Tax at Slab Rates":                    round2(tax_slab),
            "Tax on STCG (Section 111A) at 20%":    round2(tax_stcg_111A),
            "Tax on STCG (Other)":                  round2(tax_stcg_other),
            "Tax on LTCG (Section 112A) at 12.5%":  round2(tax_ltcg_112A),
            "Tax on LTCG (Other)":                  round2(tax_ltcg_other),
            "Total Tax Before Rebate":              round2(total_before_rebate),
            "Less: Rebate under Section 87A":       round2(rebate_87A),
            "Tax After Rebate":                     round2(tax_after_rebate),
            "Surcharge":                            round2(surcharge),
            "Health and Education Cess (4%)":       round2(cess),
            "Total Tax Liability":                  round2(total_tax_liability),
            "Less: TDS":                            round2(tds),
            "Net Tax Payable / Refund":             round2(net_tax),
        },
    }
    return output


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 v1.1_calculator.py <input.json> <output.json>")
        sys.exit(1)

    input_path  = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r") as f:
        inp = json.load(f)

    result = calculate(inp)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)

    print(f"Output written to {output_path}")


if __name__ == "__main__":
    main()
