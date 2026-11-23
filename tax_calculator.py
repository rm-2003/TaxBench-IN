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

OLD_REGIME_SLABS = [
    (250_000,       0.00),
    (500_000,       0.05),
    (1_000_000,     0.20),
    (float("inf"),  0.30),
]

# The old regime's basic exemption is age-dependent: 2,50,000 below 60,
# 3,00,000 for a senior citizen (60-79) and 5,00,000 for a super senior (80+).
# A single 2,50,000 table was used for every age, overtaxing 48 of the 569
# generated cases (all exactly age 72) by 2,500 each. The 80+ table loses the
# 5% band entirely, since the exemption already reaches the top of it.
OLD_REGIME_SLABS_SENIOR = [
    (300_000,       0.00),
    (500_000,       0.05),
    (1_000_000,     0.20),
    (float("inf"),  0.30),
]

OLD_REGIME_SLABS_SUPER_SENIOR = [
    (500_000,       0.00),
    (1_000_000,     0.20),
    (float("inf"),  0.30),
]


def old_regime_slabs_for_age(age: int) -> list:
    if age >= 80:
        return OLD_REGIME_SLABS_SUPER_SENIOR
    if age >= 60:
        return OLD_REGIME_SLABS_SENIOR
    return OLD_REGIME_SLABS


OLD_REGIME_REBATE_87A_THRESHOLD = 500_000
OLD_REGIME_REBATE_87A_MAX       = 12_500

NEW_REGIME_REBATE_87A_THRESHOLD = 1_200_000
NEW_REGIME_REBATE_87A_MAX       = 60_000

STANDARD_DEDUCTION_OLD = 50_000
STANDARD_DEDUCTION_NEW = 75_000
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

# Surcharge on income taxed under s.111A, s.112A and s.112 is capped at 15%
# however high total income goes. Applying the headline 25%/37% rate to the
# whole liability overstated surcharge on 48 cases that clear 2 crore while
# holding capital gains.
SURCHARGE_CAP_SPECIAL = 0.15

DEBT_PRE_2023_CUTOFF = date(2023, 4, 1)
EQUITY_LIKE_TYPES    = {"equity", "hybrid-equity", "elss"}
ELSS_LOCK_IN_MONTHS  = 36

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
        # Units bought on/after 1 Apr 2023 are "specified mutual funds" under
        # Section 50AA — always deemed short-term regardless of holding period.
        # Units bought earlier get normal long/short-term treatment, but Budget
        # 2024 (23 Jul 2024) retroactively withdrew indexation for ALL debt-fund
        # LTCG — so even pre-2023 units are taxed on the flat (unindexed) gain.
        is_pre_2023 = purchase_dt < DEBT_PRE_2023_CUTOFF
        if is_pre_2023 and months_held > 24:
            return ("ltcg_other_12_mf", sv - pv)
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


def _surcharge_rate_for(total_taxable, surcharge_table):
    for upper, rate in surcharge_table:
        if total_taxable <= upper:
            return rate
    return 0.0


def _surcharge_amount(tax_normal, tax_special, rate):
    """Surcharge with the statutory 15% ceiling on special-rate tax.

    s.111A/112A/112 income bears at most 15% surcharge regardless of how high
    total income is, so the two components are charged at different rates.
    """
    return tax_normal * rate + tax_special * min(rate, SURCHARGE_CAP_SPECIAL)


def compute_surcharge_with_relief(total_taxable, tax_normal, tax_special,
                                  special_income, slabs, surcharge_table):
    """Surcharge, with the 15% special-rate cap and marginal relief.

    Two faults in the previous version:

    1. It charged the whole of `tax_after_rebate` at the headline rate, ignoring
       the 15% ceiling on s.111A/112A/112 income (48 cases above 2 crore).

    2. Marginal relief compared against `compute_slab_tax(boundary)` -- the tax
       on the boundary as though every rupee of it were slab income. For the 129
       of 163 surcharge cases that hold capital gains that is the wrong
       comparator: it overstates the boundary tax (slab rates reach 30% against
       12.5% on LTCG) and so understates relief. The comparison must hold the
       income COMPOSITION fixed, varying only the slab-rate part, which is what
       marginal relief means -- the taxpayer should never pay more extra tax
       than the extra rupee of income that crossed the threshold.
    """
    rate = _surcharge_rate_for(total_taxable, surcharge_table)
    if rate == 0.0:
        return 0.0
    crossed_boundary = None
    for b in SURCHARGE_BOUNDARIES:
        if total_taxable > b:
            crossed_boundary = b
    if crossed_boundary is None:
        return 0.0

    surcharge_raw = _surcharge_amount(tax_normal, tax_special, rate)

    # Tax at exactly the boundary, same composition: special-rate income is held
    # at its actual amount and the slab-rate part is reduced so the total lands
    # on the boundary. At the boundary itself the LOWER band's rate applies
    # (nil at 50 lakh, 10% at 1 crore, and so on).
    normal_at_boundary = max(0.0, crossed_boundary - special_income)
    tax_normal_at_boundary = compute_slab_tax(normal_at_boundary, slabs)
    rate_at_boundary = _surcharge_rate_for(crossed_boundary, surcharge_table)
    tax_at_boundary = (tax_normal_at_boundary + tax_special
                       + _surcharge_amount(tax_normal_at_boundary, tax_special,
                                           rate_at_boundary))

    excess_income = total_taxable - crossed_boundary
    excess_tax    = (tax_normal + tax_special + surcharge_raw) - tax_at_boundary
    relief        = max(0.0, excess_tax - excess_income)
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

# s.80G splits donations four ways: 100% or 50% deductible, each either WITH or
# WITHOUT a qualifying limit. The two sets above are the "without limit"
# categories. Schemes in the sets below are subject to s.80G(4): the aggregate
# qualifies only up to 10% of adjusted gross total income (GTI less Chapter VI-A
# deductions other than 80G, and less income charged at special rates).
#
# Both sets are EMPTY because the generator only ever emits PM Cares Fund (353
# cases, 100% without limit) and the Prime Minister's Drought Relief Fund (216,
# 50% without limit), so the limit is inactive on all 569 cases. The mechanism
# is implemented anyway: the omission was a latent fault, and a scheme in either
# category would otherwise be silently over-deducted.
FULL_EXEMPT_LIMITED_SCHEMES = set()   # 100%, capped at 10% of adjusted GTI
HALF_EXEMPT_LIMITED_SCHEMES = set()   # 50%,  capped at 10% of adjusted GTI


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
    basic_da = g(gs, "Basic Salary") + g(gs, "Dearness Allowance")

    # The employer's NPS contribution is TAXABLE SALARY under s.17(1)(viii) and is
    # then relieved by the 80CCD(2) deduction further down — net neutral up to the
    # cap, but it has to enter income before it can be taken out of it. This was
    # previously deducted under 80CCD(2) without ever being added to salary, so the
    # same rupees were both excluded from income and subtracted from it, and every
    # affected case's Total Taxable Income came out low by the contribution. The
    # ITD estimator disagreed with the stored ground truth on input_0176 for
    # exactly this reason (12,89,500 against our 12,39,500) and was right.
    #
    # Computed here, ahead of gross_salary, because a government employee's
    # contribution is imputed rather than declared (below) and the imputed amount
    # is just as taxable as a declared one. basic_da stays Basic + DA only: it is
    # the base for the HRA exemption and for the 80CCD caps, none of which count
    # the employer's contribution.
    nps          = inp.get("NPS", {})
    nps_employer = g(nps, "Tier-1 Employer Contribution")
    c80ccd2_pct  = 0.14 if (regime == "new" or employment == "government") else 0.10
    # NO imputation for government employees. An earlier version raised the
    # employer contribution to the statutory 14% of Basic+DA whenever the input
    # declared less, on the grounds that government employers contribute that
    # much compulsorily. That is true of the real world but wrong for this
    # benchmark: the amount appears nowhere in the input JSON and the rule is
    # stated nowhere in the system prompt, so the ground truth depended on a
    # figure no model could derive. It affected all 212 government cases -- a
    # median of 90,000 and up to 272,000 of salary invented out of nothing, with
    # 48 cases declaring exactly 0 -- and silently cost every model 1-2 points
    # (nemotron zero-shot 60.6% -> 62.5% once removed). The declared figure is
    # now taken at face value: a benchmark may only ask what its inputs support.
    #
    # The imputation cancelled out of Total Taxable Income (the 80CCD(2)
    # deduction equalled it exactly in all 212 cases), which is why this hid for
    # so long -- the tax chain was right while Gross Salary, Net Salary, Gross
    # Total Income, Total Deductions and 80CCD(2) were all wrong.

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
        g(gs, "Entertainment Allowance"),
        nps_employer,
    ])

    metro_pct = 0.50 if city == "metro" else 0.40

    # Section 10(13A) — HRA exemption (old regime only)
    if regime == "old":
        hra_received  = g(gs, "HRA")
        rent_paid     = g(inp, "Actual Rent Paid")
        hra_candidate = rent_paid - 0.10 * basic_da
        hra_10_13A = max(0.0, min(
            hra_received,
            metro_pct * basic_da,
            hra_candidate,
        ))
    else:
        hra_10_13A = 0.0

    # Section 10(5) — LTA exemption (old regime only)
    if regime == "old":
        lta_in_salary = g(gs, "LTA")
        lta_claimed   = g(inp, "LTA Travel Expenses Claimed")
        lta_10_5      = min(lta_in_salary, lta_claimed)
    else:
        lta_10_5 = 0.0

    # Section 16(ia) — standard deduction
    std_ded = STANDARD_DEDUCTION_NEW if regime == "new" else STANDARD_DEDUCTION_OLD
    s16_ia  = min(std_ded, gross_salary)

    # Section 16(ii) — entertainment allowance (govt + old regime only)
    entertainment = g(gs, "Entertainment Allowance")
    if employment == "government" and regime == "old":
        s16_ii = min(5_000, 0.20 * g(gs, "Basic Salary"), entertainment)
    else:
        s16_ii = 0.0

    # Section 16(iii) — professional tax (old regime only)
    s16_iii = min(5_000, g(inp, "Professional Tax")) if regime == "old" else 0.0

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
            # s.55(2)(ac) grandfathering, with the two conditions the previous
            # `max(cost_price, fmv)` left out.
            #
            # 1. It applies ONLY to equity shares acquired BEFORE 1 Feb 2018.
            #    Without the date test every long-term holding got the step-up,
            #    including shares bought in 2024 whose "FMV as of 31 Jan 2018"
            #    is a meaningless number. That inflated the cost basis on 166
            #    transactions across 166 cases (29% of the benchmark) and
            #    understated LTCG by 1,32,80,000 in total.
            #
            # 2. The step-up is capped at the sale consideration: cost is the
            #    HIGHER of actual cost and the LOWER of FMV and sale price.
            #    Without the inner min() an FMV above the sale price would
            #    manufacture a loss. No case in the current dataset trips this
            #    (0 of 777 transactions have fmv > sale_price), so it is a
            #    latent fault rather than an observed one -- fixed because the
            #    generator is expected to produce such a case eventually.
            #
            # NOTE: no stock transaction in the current dataset is acquired
            # before the cutoff -- the earliest purchase date anywhere is
            # 2024-04-01 -- so after this fix the FMV field is DEAD: carried in
            # every transaction, described in the system prompt, and never
            # load-bearing. The `ltcg_fmv_benefit` variant in
            # generate_test_cases.py sets FMV 180 with a 2024-04-01 purchase
            # date, so it was never eligible; the missing date test above is the
            # only reason it appeared to do anything. Two complementary errors
            # that cancelled into a plausible result, which is why 28 calculator
            # tests and four ITD-estimator checks all passed over it. Giving the
            # provision real coverage needs pre-2018 purchase dates in the
            # generator, which changes the inputs and so invalidates collected
            # model outputs -- deferred, see CHANGELOG.
            if purchase_dt < date(2018, 2, 1):
                effective_cost_per_share = max(cost_price, min(fmv, sale_price))
            else:
                effective_cost_per_share = cost_price
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

    # Other asset classification (Bonds, Debentures, G-Secs)
    OTHER_ASSETS = ["Bonds", "Debentures", "G-Secs"]
    stcg_other_breakdown = {}
    ltcg_noneq_12_breakdown = {}

    for asset in OTHER_ASSETS:
        asset_inp = inp.get(asset, {})
        sale  = g(asset_inp, "Sale Amount")
        cost  = g(asset_inp, "Purchase Amount")
        years = g(asset_inp, "Held for duration in years")
        gain  = sale - cost
        if gain <= 0:
            stcg_other_breakdown[asset] = 0.0
            ltcg_noneq_12_breakdown[asset] = 0.0
        elif years > 1:
            stcg_other_breakdown[asset] = 0.0
            ltcg_noneq_12_breakdown[asset] = gain
        else:
            stcg_other_breakdown[asset] = gain
            ltcg_noneq_12_breakdown[asset] = 0.0

    stcg_other_breakdown["Mutual Funds"] = round2(mf_stcg_other)
    ltcg_noneq_12_breakdown["Mutual Funds"] = round2(mf_ltcg_other_12)

    stcg_other    = sum(stcg_other_breakdown.values())
    ltcg_noneq_12 = sum(ltcg_noneq_12_breakdown.values())
    ltcg_other_20 = 0.0

    # Capital loss eligibility — 8 assessment year limit
    current_ay_start = 2025
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

    # Sequential priority-based loss set-off
    stcg_111A     = stcg_raw
    stcg_other_net = stcg_other
    ltcg_112A     = ltcg_raw
    ltcg_noneq_net = ltcg_noneq_12

    # LTCL: offsets LTCG 112A first, then LTCG Non-Equity
    lt_loss = prior_lt_losses
    used = min(lt_loss, ltcg_112A)
    ltcg_112A -= used
    lt_loss -= used
    used = min(lt_loss, ltcg_noneq_net)
    ltcg_noneq_net -= used

    # STCL: offsets STCG 111A → STCG Other → LTCG 112A → LTCG Non-Equity
    st_loss = prior_st_losses
    used = min(st_loss, stcg_111A)
    stcg_111A -= used
    st_loss -= used
    used = min(st_loss, stcg_other_net)
    stcg_other_net -= used
    st_loss -= used
    used = min(st_loss, ltcg_112A)
    ltcg_112A -= used
    st_loss -= used
    used = min(st_loss, ltcg_noneq_net)
    ltcg_noneq_net -= used

    # Scale breakdowns to match post-loss totals
    if stcg_other > 0:
        stcg_other_breakdown = {k: v * (stcg_other_net / stcg_other) for k, v in stcg_other_breakdown.items()}
    stcg_other = stcg_other_net
    if ltcg_noneq_12 > 0:
        ltcg_noneq_12_breakdown = {k: v * (ltcg_noneq_net / ltcg_noneq_12) for k, v in ltcg_noneq_12_breakdown.items()}
    ltcg_noneq_12 = ltcg_noneq_net

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
        ltcg_112A, ltcg_noneq_12,
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
    # `nps`, `nps_employer` and `c80ccd2_pct` are set up top, before gross_salary,
    # because the employer's contribution has to be added to salary income there.
    nps_self       = g(nps, "Tier-1 Self Contribution")
    c80ccd1_limit  = 0.10 * basic_da
    # Claim under 80CCD(1) only what fits in the 80CCE room left by 80C and
    # 80CCC; the rest goes to 80CCD(1B) below. Taking it all under 80CCD(1) and
    # letting the 80CCE cap scale it down threw the squeezed-out contribution
    # away, although s.80CCD(1B) allows it "whether or not any deduction is
    # allowed under sub-section (1)" -- a smaller deduction than any taxpayer
    # would claim. Unchanged whenever the 80CCE cap does not bind.
    c80cce_room    = max(0.0, 150_000 - c80 - c80ccc)
    c80ccd1        = min(nps_self, c80ccd1_limit, c80cce_room)

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
    # The rate (14% new regime or government, else 10%) and the government
    # imputation are applied up top, where the contribution is added to salary.
    # Only the capped amount is deductible while the WHOLE contribution is
    # taxable, so a contribution above the cap is correctly left partly taxed.
    c80ccd2 = min(nps_employer, c80ccd2_pct * basic_da)

    # 80G — Donations
    c80g = 0.0
    c80g_limited = 0.0          # the part subject to the 10%-of-adjusted-GTI cap
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
        elif scheme in FULL_EXEMPT_LIMITED_SCHEMES:
            c80g_limited += amount
        elif scheme in HALF_EXEMPT_LIMITED_SCHEMES:
            c80g_limited += amount * 0.50

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

    if regime == "new":
        c80cce_total = c80_reported = c80ccc_reported = c80ccd1_reported = 0.0
        c80ccd1b = 0.0
        c80g = 0.0
        c80d = 0.0
        c80e = 0.0
        c80tta = 0.0
        c80ttb = 0.0

    # s.80G(4): the "with qualifying limit" categories are deductible only up to
    # 10% of ADJUSTED gross total income -- GTI less the other Chapter VI-A
    # deductions and less income charged at special rates. Inactive on all 569
    # current cases (both schemes the generator emits are "without limit"), so
    # c80g_limited is always 0 and this adds nothing; present so that adding a
    # limited-category scheme does not silently over-deduct.
    adjusted_gti = max(0.0, gross_total
                       - (stcg_111A + ltcg_112A + ltcg_noneq_12)
                       - (c80cce_total + c80ccd1b + c80ccd2
                          + c80d + c80e + c80tta + c80ttb))
    c80g += min(c80g_limited, 0.10 * adjusted_gti)

    total_deductions = sum([
        c80cce_total,
        c80ccd1b,
        c80ccd2,
        c80g,
        c80d, c80e, c80tta, c80ttb,
    ])

    # Section 80A(2): the aggregate of Chapter VI-A deductions "shall not, in any
    # case, exceed the gross total income of the assessee". Deductions may reduce
    # taxable income to zero but never below it — without this cap 11 of the 569
    # generated cases produced a negative Total Taxable Income, and a model that
    # correctly answered zero was scored wrong.
    total_deductions = min(total_deductions, gross_total)

    # s.112A(6) and s.111A(2): where gross total income includes gains charged
    # under those sections, Chapter VI-A deductions are allowed from GTI "as
    # reduced by" them. Capping at gross_total alone let deductions shelter
    # capital-gains income on 25 cases, 16,16,500 in total. The tax barely
    # moves -- the gains are charged at special rates from their own gross
    # amounts and the slab-rate part was already clamped at zero -- but the
    # REPORTED Total Deductions and Total Taxable Income were both wrong, and
    # both are scored fields.
    special_gains = stcg_111A + ltcg_112A + ltcg_noneq_12
    total_deductions = min(total_deductions, max(0.0, gross_total - special_gains))

    # ------------------------------------------------------------------
    # Total Taxable Income
    # ------------------------------------------------------------------
    total_taxable = gross_total - total_deductions

    # ------------------------------------------------------------------
    # Tax Computation
    # ------------------------------------------------------------------

    # Special-rate incomes (outside normal slabs)
    special_income = stcg_111A + ltcg_112A + ltcg_noneq_12
    normal_income  = max(0.0, total_taxable - special_income)

    slab_rates     = (NEW_REGIME_SLABS if regime == "new"
                      else old_regime_slabs_for_age(age))
    rebate_threshold = NEW_REGIME_REBATE_87A_THRESHOLD if regime == "new" else OLD_REGIME_REBATE_87A_THRESHOLD
    rebate_max       = NEW_REGIME_REBATE_87A_MAX if regime == "new" else OLD_REGIME_REBATE_87A_MAX

    tax_slab       = compute_slab_tax(normal_income, slab_rates)
    tax_stcg_111A  = stcg_111A * STCG_111A_RATE
    tax_stcg_other = 0.0
    tax_ltcg_112A  = max(0.0, ltcg_112A - LTCG_112A_EXEMPT) * LTCG_112A_RATE
    # The 1,25,000 relief in s.112A(2) attaches to "such long-term capital
    # gains" -- the s.112A(1) ones, i.e. equity shares and equity-oriented units
    # with STT paid. LTCG on bonds, debentures, G-Secs and debt funds is charged
    # under s.112, which carries no equivalent allowance, so an unused remainder
    # must NOT be spilled onto it. The previous code did exactly that:
    #     ltcg_exempt_remaining = max(0, LTCG_112A_EXEMPT - ltcg_112A)
    #     tax = max(0, ltcg_noneq_12 - ltcg_exempt_remaining) * RATE
    # which undertaxed non-equity LTCG on 94 of the 569 cases and taxed it at
    # ZERO on 44 of them -- 5,36,625 of tax before cess. Test 22 asserted the
    # behaviour and its name ("shared 1.25L exemption") read it as a rule.
    tax_ltcg_noneq_12 = ltcg_noneq_12 * LTCG_112A_RATE
    tax_ltcg_other_20  = 0.0

    total_before_rebate = tax_slab + tax_stcg_111A + tax_ltcg_112A + tax_ltcg_noneq_12

    # Section 87A rebate — applies only to slab tax, not special-rate taxes
    # New regime: marginal relief when income > threshold
    # Old regime: simple rebate, no marginal relief
    if total_taxable <= rebate_threshold:
        rebate_87A = min(tax_slab, rebate_max)
    elif regime == "new":
        income_above_threshold = max(0.0, normal_income - rebate_threshold)
        rebate_87A = max(0.0, tax_slab - income_above_threshold)
    else:
        rebate_87A = 0.0

    tax_after_rebate = total_before_rebate - rebate_87A

    # Surcharge
    surcharge_table = NEW_REGIME_SURCHARGE_RATES if regime == "new" else OLD_REGIME_SURCHARGE_RATES
    # Split the liability so the 15% ceiling can be applied to the special-rate
    # part. The 87A rebate reduces only slab tax, so it belongs to the normal
    # component.
    tax_normal_after_rebate = max(0.0, tax_slab - rebate_87A)
    tax_special             = tax_stcg_111A + tax_ltcg_112A + tax_ltcg_noneq_12
    surcharge = compute_surcharge_with_relief(
        total_taxable, tax_normal_after_rebate, tax_special,
        special_income, slab_rates, surcharge_table
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
            "STCG (Other)": {
                **{k: round2(v) for k, v in stcg_other_breakdown.items()},
                "Total": round2(stcg_other),
            },
            "LTCG (Section 112A)": round2(ltcg_112A),
            "LTCG (Non-Equity)": {
                **{k: round2(v) for k, v in ltcg_noneq_12_breakdown.items()},
                "Total": round2(ltcg_noneq_12),
            },
            "LTCG (Other)": round2(ltcg_other_20),
        },
        "Income from Other Sources": {
            "Savings Bank Interest": round2(savings_bank_interest),
            "Deposit Interest":      round2(deposit_interest),
            # `Other Interest` is a REPORTABLE AMOUNT here, matching the input,
            # and `EPF Taxable Interest` is its sibling rather than its child.
            # It used to be a container holding only the EPF figure, so the
            # input's Other Interest amount entered Gross Total Income (see
            # gross_total above) with nowhere to be reported -- which is why
            # "GTI = sum of the heads" failed on exactly the 336 cases that
            # carry a non-zero value. The old shape also invited models writing
            # scripts to read the INPUT the same way, as
            # data["Other Interest"]["EPF Taxable Interest"], which raises
            # TypeError on an int; both retry transcripts in the project do
            # exactly that, and gemma's script arm conflated the two meanings on
            # 6 of 49 cases (63.3% correct on this field against 100.0% for the
            # same model in zero-shot).
            "Other Interest":        round2(other_interest),
            "EPF Taxable Interest":  round2(epf_taxable_interest),
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
            "Tax on STCG (Section 111A)":    round2(tax_stcg_111A),
            "Tax on STCG (Other)":                  round2(tax_stcg_other),
            "Tax on LTCG (Section 112A)":  round2(tax_ltcg_112A),
            "Tax on LTCG (Non-Equity)":    round2(tax_ltcg_noneq_12),
            "Tax on LTCG (Other)":            round2(tax_ltcg_other_20),
            "Total Tax Before Rebate":              round2(total_before_rebate),
            "Less: Rebate under Section 87A":       round2(rebate_87A),
            "Tax After Rebate":                     round2(tax_after_rebate),
            "Surcharge":                            round2(surcharge),
            "Health and Education Cess":       round2(cess),
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
