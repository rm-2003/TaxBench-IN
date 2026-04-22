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

    prior_lt_losses = sum(
        g(t, "Loss Amount") for t in inp.get("Long Term Capital Loss", [])
    )
    prior_st_losses = sum(
        g(t, "Loss Amount") for t in inp.get("Short Term Capital Loss", [])
    )

    stcg_111A  = max(0.0, stcg_raw - prior_st_losses)
    ltcg_112A  = max(0.0, ltcg_raw - prior_lt_losses)
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
        stcg_111A, stcg_other,
        ltcg_112A, ltcg_other,
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
    special_income = stcg_111A + ltcg_112A + ltcg_other
    normal_income  = max(0.0, total_taxable - special_income)

    tax_slab       = compute_slab_tax(normal_income, NEW_REGIME_SLABS)
    tax_stcg_111A  = stcg_111A * STCG_111A_RATE
    tax_stcg_other = 0.0  # STCG Other taxed at slab rates — already in tax_slab
    tax_ltcg_112A  = max(0.0, ltcg_112A - LTCG_112A_EXEMPT) * LTCG_112A_RATE
    tax_ltcg_other = 0.0  # pass-through placeholder

    total_before_rebate = tax_slab + tax_stcg_111A + tax_ltcg_112A

    # Section 87A rebate — applies only to slab tax, not special-rate taxes
    if total_taxable <= REBATE_87A_THRESHOLD:
        rebate_87A = min(tax_slab, REBATE_87A_MAX)
    else:
        rebate_87A = 0.0

    tax_after_rebate   = total_before_rebate - rebate_87A
    surcharge          = 0.0   # placeholder
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
