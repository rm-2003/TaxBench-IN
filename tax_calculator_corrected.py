"""
tax_calculator_corrected.py
Income-tax computation for an individual, FY 2025-26 (AY 2026-27), following the Income-tax
Act, 1961 as amended by the Finance (No. 2) Act 2024 and the Finance Act 2025.

Same input format, output schema and command line as tax_calculator.py:
    python tax_calculator_corrected.py <input.json> <output.json>

Corrections relative to tax_calculator.py
-----------------------------------------
Capital gains
  C1  Grandfathering (s.55(2)(ac)) only for listed equity bought on or before 31-Jan-2018, and
      the FMV used is capped at the sale price: cost = max(actual cost, min(FMV, sale price)).
      (Original: max(cost, FMV) for any purchase date.)
  C2  Holding periods use calendar months ("more than 12/24 months"), not days/365 or
      days/30.44. A sale exactly 12 months after purchase is short-term.
  C3  Pre-1-Apr-2023 debt funds held > 24 months: LTCG u/s 112 at 12.5% WITHOUT indexation
      (indexation withdrawn for transfers after 23-Jul-2024). (Original: indexed cost.)
  C4  Losses on Bonds / Debentures / G-Secs are capital losses and are set off, not discarded.
  C5  Loss set-off follows s.70/s.74: short-term losses (current year and brought forward)
      against any capital gain; long-term losses only against long-term gains. Within those
      rules the taxpayer may choose the order; a fixed, stated order is used (long-term loss:
      s.112 then s.112A; short-term loss: s.111A, STCG other, s.112, s.112A), with current-year
      losses pooled with brought-forward ones. OPTIMISE_ORDERS = True picks the cheapest order.
      (Original: negative STCG (Other) could not reduce STCG 111A and negative non-equity LTCG
      could not reduce LTCG 112A.)
  C6  The Rs 1.25 lakh exemption applies to s.112A gains only; it does not spill over to
      non-equity LTCG u/s 112. (Original: unused exemption reduced non-equity LTCG.)
Deductions
  C7  80CCC is the premium paid in the year, not divided by the years it covers (dividing
      is an 80D(4A) rule and applies only to health insurance).
  C8  80CCE: 80C, then 80CCC, then 80CCD(1) fill the Rs 1.5 lakh ceiling; NPS self-
      contribution not used under 80CCD(1) goes to 80CCD(1B) (up to Rs 50,000).
      (Original: proportional scaling, and the part of 80CCD(1) cut by the ceiling was lost.)
  C9  80CCD(2) is the employer's actual contribution up to 14% / 10% of salary; there is no
      floor. (Original: government employees floored at 14% of salary.)
  C10 80D: preventive check-ups (Rs 5,000 in aggregate) sit inside the limit of the person
      checked (self/family or parents), placed where the limit has room. The Rs 50,000 senior
      limit comes from the assessee's age or a deductible entry for a senior (a cash premium,
      which isn't deductible, doesn't raise it). (Original: all check-ups in the self bucket.)
  C11 Chapter VI-A deductions cannot exceed gross total income excluding income under
      s.111A / 112 / 112A (s.80A(2), s.111A(2), s.112(2), s.112A(6)), so taxable income is never
      negative. (Original: deductions could exceed income.)
Tax
  C12 Old regime basic exemption by age: Rs 2.5 lakh below 60, Rs 3 lakh for 60-79,
      Rs 5 lakh for 80+. (Original: Rs 2.5 lakh at every age.)
  C13 Unused basic exemption reduces s.111A / s.112 / s.112A income (provisos to those
      sections; residents). The Act sets no order; a fixed order is used (s.111A, then s.112,
      then s.112A above Rs 1.25 lakh). OPTIMISE_ORDERS = True picks the cheapest order.
  C14 87A: the rebate is not available against tax on s.112A income (old regime) or on any
      special-rate income (new regime, Finance Act 2025). New regime: the Rs 12 lakh test and
      marginal relief use income excluding special-rate income, and relief is
      max(0, slab tax - (that income - 12 lakh)). Confirmed against the e-Filing portal's
      calculator (files 176, 218) and the Finance Bill 2025 memorandum.
Salary / capital gains (added after checking official sources)
  C18 The employer's Tier-1 NPS contribution is salary income (s.17(1)(viii)); 80CCD(2) then
      deducts it up to the limit. (Original: deducted but never added to salary.)
  C19 s.111A and s.112A need STT paid. A stock sale with STT = 0 is taxed at slab rates
      (short-term) or u/s 112 at 12.5% without the Rs 1.25 lakh exemption (long-term). Such
      gains are counted in the STCG (Other) / LTCG (Non-Equity) totals but have no key of
      their own in the output schema's breakdown.
  C15 Surcharge: tax on s.111A / 112 / 112A income is surcharged at no more than 15%; the
      25%/37% rates apply to the rest only when income excluding those gains crosses the
      Rs 2 crore / Rs 5 crore threshold. (Original: full rate on everything.)
  C16 Surcharge marginal relief compares with the tax INCLUDING surcharge payable on income
      equal to the threshold. (Original: slab tax on the threshold, without surcharge or
      special-rate tax.)
  C17 s.288A / s.288B: total income and total tax rounded to the nearest Rs 10
      (STATUTORY_ROUNDING, on by default).

Assumptions (the input doesn't say; change the constants below if needed)
  * Resident individual; returns filed on time so brought-forward losses are available.
  * Bonds / Debentures / G-Secs are listed (long-term after 12 months). "Held for duration in
    years" is whole years, so 1 year is treated as not more than 12 months. Unlisted bonds and
    debentures sold after 23-Jul-2024 would be short-term regardless (s.50AA).
  * gold-etf units are listed (12 months); gold-mf and international funds are unlisted fund
    of funds (24 months). Neither is a "specified mutual fund" for AY 2026-27.
  * ELSS units sold inside the 3-year lock-in are ignored (such a sale can't happen).
  * NPS Tier-2 is not deducted (the 80C benefit is for central government employees only and
    the input does not say which government).
  * A personal vehicle is not a capital asset (s.2(14)), so no gain arises.
  * NEW_REGIME_REBATE_TEST_EXCLUDES_SPECIAL (default True, as the portal does): set False to
    test the Rs 12 lakh limit on total income instead.
  * Surcharge marginal relief at a threshold reduces normal income first, then s.112, s.111A
    and s.112A income, to build the income "equal to the threshold" (matched the portal on
    files 64 and 76).
  * "government" means a Central/State Government employer (14% 80CCD(2) limit); a public
    sector company would be 10%.

Not handled (no input field carries the data)
  * Employer PF + NPS + superannuation above Rs 7.5 lakh as a perquisite (s.17(2)(vii)).
  * Grandfathering of equity mutual fund units bought before 1-Feb-2018 (needs the NAV on
    31-Jan-2018); dividends; non-residents; 80G funds other than the five listed.
"""

import itertools
import json
import sys
from calendar import monthrange
from datetime import date

# ---------------------------------------------------------------------------
# Constants - FY 2025-26
# ---------------------------------------------------------------------------
NEW_REGIME_SLABS = [(400_000, 0.00), (800_000, 0.05), (1_200_000, 0.10), (1_600_000, 0.15),
                    (2_000_000, 0.20), (2_400_000, 0.25), (float("inf"), 0.30)]


def old_regime_slabs(age):
    exempt = 500_000 if age >= 80 else 300_000 if age >= 60 else 250_000
    table = [(exempt, 0.00)]
    if exempt < 500_000:
        table.append((500_000, 0.05))
    table += [(1_000_000, 0.20), (float("inf"), 0.30)]
    return table


REBATE = {"old": (500_000, 12_500), "new": (1_200_000, 60_000)}
NEW_REGIME_REBATE_TEST_EXCLUDES_SPECIAL = True
OPTIMISE_ORDERS = False      # True: pick the loss set-off / exemption order giving the lowest tax
STATUTORY_ROUNDING = True

STANDARD_DEDUCTION = {"old": 50_000, "new": 75_000}
LTCG_112A_EXEMPT = 125_000
RATE_111A, RATE_112A, RATE_112 = 0.20, 0.125, 0.125
CESS_RATE = 0.04
SURCHARGE_THRESHOLDS = [5_000_000, 10_000_000, 20_000_000, 50_000_000]
SPECIAL_SURCHARGE_CAP = 0.15
GRANDFATHER_CUTOFF = date(2018, 1, 31)
DEBT_SPECIFIED_MF_FROM = date(2023, 4, 1)
ELSS_LOCK_IN_MONTHS = 36
CURRENT_AY_START = 2026            # AY 2026-27
LOSS_CARRY_FORWARD_YEARS = 8

FULL_EXEMPT_SCHEMES = {"National Defence Fund", "PM Cares Fund", "National Sports Fund",
                       "National Cultural Fund"}
HALF_EXEMPT_SCHEMES = {"Prime Minister's Drought Relief Fund"}
VALID_BENEFICIARIES = {"self", "spouse", "children", "parents"}
OTHER_ASSETS = ["Bonds", "Debentures", "G-Secs"]
SCHEMA_COMPONENTS = OTHER_ASSETS + ["Mutual Funds"]      # breakdown keys in the output schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def g(d, *keys, default=0):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def held_more_than(purchase, sale, months):
    return sale > add_months(purchase, months)


def slab_tax(income, slabs):
    tax, prev = 0.0, 0
    for upper, rate in slabs:
        if income <= prev:
            break
        tax += (min(income, upper) - prev) * rate
        prev = upper
    return tax


def round10(x):
    """s.288A / s.288B: nearest multiple of Rs 10 (5 rounds up)."""
    sign = -1 if x < 0 else 1
    return sign * int((abs(x) + 5) // 10 * 10)


def round2(x):
    return round(x + 0.0, 2)


# ---------------------------------------------------------------------------
# Capital gains
# ---------------------------------------------------------------------------
def classify_gains(inp):
    """Return raw (pre set-off) pools: s111, l112a (floats) and component dicts so, lt."""
    s111 = l112a = 0.0
    so = {a: 0.0 for a in OTHER_ASSETS + ["Mutual Funds", "Shares"]}   # "Shares": no-STT sales only
    lt = dict(so)

    for t in inp.get("Stock Sale Transactions", []):
        pd, sd = parse_date(t.get("Purchase Date", "")), parse_date(t.get("Sale Date", ""))
        qty = g(t, "Quantity")
        if pd is None or sd is None or qty == 0:
            continue
        sp, cp, brk, fmv = g(t, "Sale Price"), g(t, "Cost Price"), g(t, "Brokerage"), g(t, "FMV as of 31 Jan 2018")
        stt_paid = "STT" not in t or g(t, "STT") > 0                   # C19: s.111A / s.112A need STT
        if held_more_than(pd, sd, 12):
            if stt_paid:
                cost = cp
                if pd <= GRANDFATHER_CUTOFF and fmv:                   # C1
                    cost = max(cp, min(fmv, sp))
                l112a += (sp - cost) * qty - brk
            else:
                lt["Shares"] += (sp - cp) * qty - brk                  # s.112 at 12.5%, no exemption
        elif stt_paid:
            s111 += (sp - cp) * qty - brk
        else:
            so["Shares"] += (sp - cp) * qty - brk                      # slab rates

    for t in inp.get("Mutual Fund Transactions", []):
        pd, sd = parse_date(t.get("Purchase Date", "")), parse_date(t.get("Sale Date", ""))
        pv, sv = g(t, "Purchase Value"), g(t, "Sale Value")
        if pd is None or sd is None or pv == 0:
            continue
        typ, gain = t.get("Type", "").lower(), sv - pv
        if typ == "elss":
            if held_more_than(pd, sd, ELSS_LOCK_IN_MONTHS) or sd == add_months(pd, ELSS_LOCK_IN_MONTHS):
                l112a += gain
        elif typ in ("equity", "hybrid-equity"):
            if held_more_than(pd, sd, 12):
                l112a += gain
            else:
                s111 += gain
        elif typ == "debt":                                             # C3
            if pd < DEBT_SPECIFIED_MF_FROM and held_more_than(pd, sd, 24):
                lt["Mutual Funds"] += gain
            else:
                so["Mutual Funds"] += gain
        elif typ == "gold-etf":
            (lt if held_more_than(pd, sd, 12) else so)["Mutual Funds"] += gain
        elif typ in ("gold-mf", "international"):
            (lt if held_more_than(pd, sd, 24) else so)["Mutual Funds"] += gain

    for a in OTHER_ASSETS:                                              # C4
        x = inp.get(a, {})
        sale, cost = g(x, "Sale Amount"), g(x, "Purchase Amount")
        if sale == 0 and cost == 0:
            continue
        (lt if g(x, "Held for duration in years") > 1 else so)[a] += sale - cost
    return s111, l112a, so, lt


def apply_losses(pools, st_loss, lt_loss, st_order, lt_order):
    """Set off losses in the given orders. pools: dict with keys s111, so, l112a, l112 (>= 0)."""
    p = dict(pools)
    for k in lt_order:
        u = min(lt_loss, p[k]); p[k] -= u; lt_loss -= u
    for k in st_order:
        u = min(st_loss, p[k]); p[k] -= u; st_loss -= u
    return p, st_loss, lt_loss


def scale_components(comp, total):
    """Split a post set-off total across the positive components (losses were set off)."""
    pos = {k: max(0.0, v) for k, v in comp.items()}
    s = sum(pos.values())
    return {k: (v / s * total if s else 0.0) for k, v in pos.items()}


# ---------------------------------------------------------------------------
# Tax on a given income composition
# ---------------------------------------------------------------------------
def tax_on(normal, s111, l112, l112a, regime, age, total_income):
    """Tax before cess on one income composition; returns dict of the pieces."""
    slabs = NEW_REGIME_SLABS if regime == "new" else old_regime_slabs(age)
    exempt = slabs[0][0]
    t_slab = slab_tax(normal, slabs)
    limit, cap = REBATE[regime]
    best = None
    # C13: the Act fixes no order for using the unexhausted exemption against special-rate
    # income. A fixed order (s.111A, then s.112, then s.112A) is used so the rule can be stated
    # simply; set OPTIMISE_ORDERS = True to try every order and keep the lowest tax instead.
    orders = itertools.permutations(("s111", "l112", "l112a")) if OPTIMISE_ORDERS \
        else [("s111", "l112", "l112a")]
    for order in orders:
        room = {"s111": s111, "l112": l112, "l112a": max(0.0, l112a - LTCG_112A_EXEMPT)}
        adj = dict.fromkeys(room, 0.0)
        shortfall = max(0.0, exempt - normal)
        for k in order:
            adj[k] = min(room[k], shortfall)
            shortfall -= adj[k]
        t111 = (s111 - adj["s111"]) * RATE_111A
        t112 = (l112 - adj["l112"]) * RATE_112                          # C6: no exemption
        t112a = max(0.0, l112a - LTCG_112A_EXEMPT - adj["l112a"]) * RATE_112A
        before = t_slab + t111 + t112 + t112a

        if regime == "new":                                             # C14
            # Rs 12 lakh test and marginal relief both use income other than special-rate
            # income, and the rebate can only reduce tax at slab rates.
            test_income = normal if NEW_REGIME_REBATE_TEST_EXCLUDES_SPECIAL else total_income
            if test_income <= limit:
                rebate = min(t_slab, cap)
            else:
                rebate = max(0.0, t_slab - (test_income - limit))
            normal_part = t_slab - rebate
            special_part = t111 + t112 + t112a
        else:
            rebate = min(cap, before - t112a) if total_income <= limit else 0.0
            r = rebate
            normal_part = t_slab - min(r, t_slab); r -= min(r, t_slab)
            special_part = t111 + t112 + t112a - r
        result = {"slab": t_slab, "t111": t111, "t112": t112, "t112a": t112a, "before": before,
                  "rebate": rebate, "after": before - rebate, "normal_part": normal_part,
                  "special_part": special_part}
        if best is None or result["after"] < best["after"] - 0.005:
            best = result
    return best


def surcharge_on(t, total_income, special_income, regime):
    """C15: 25%/37% only on tax on non-special income, and only if that income crosses the band."""
    ti = total_income
    if ti <= SURCHARGE_THRESHOLDS[0]:
        return 0.0
    rate = 0.10 if ti <= 10_000_000 else 0.15 if ti <= 20_000_000 else 0.25 if ti <= 50_000_000 \
        else (0.37 if regime == "old" else 0.25)
    rate_normal = rate
    if rate > 0.15:
        other = ti - special_income
        if ti > 50_000_000 and other > 50_000_000:
            rate_normal = 0.37 if regime == "old" else 0.25
        elif other > 20_000_000:
            rate_normal = 0.25
        else:
            rate_normal = 0.15
    return t["normal_part"] * rate_normal + t["special_part"] * min(rate, SPECIAL_SURCHARGE_CAP)


def total_tax(normal, s111, l112, l112a, regime, age):
    """Tax + surcharge (with marginal relief) + cess for one composition."""
    ti = normal + s111 + l112 + l112a
    special = s111 + l112 + l112a
    t = tax_on(normal, s111, l112, l112a, regime, age, ti)
    sur = surcharge_on(t, ti, special, regime)
    relief = 0.0
    crossed = [b for b in SURCHARGE_THRESHOLDS if ti > b]
    if sur > 0 and crossed:                                             # C16
        b = crossed[-1]
        excess = ti - b
        parts = {"normal": normal, "l112": l112, "s111": s111, "l112a": l112a}
        for k in ("normal", "l112", "s111", "l112a"):
            cut = min(parts[k], excess); parts[k] -= cut; excess -= cut
        tb = tax_on(parts["normal"], parts["s111"], parts["l112"], parts["l112a"], regime, age, b)
        sb = surcharge_on(tb, b, parts["s111"] + parts["l112"] + parts["l112a"], regime)
        relief = max(0.0, (t["after"] + sur) - (tb["after"] + sb + (ti - b)))
    surcharge = max(0.0, sur - relief)
    cess = (t["after"] + surcharge) * CESS_RATE
    return t, surcharge, cess


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------
def calculate(inp: dict, details: bool = False) -> dict:
    employment = inp.get("Employment Type", "private").lower()
    regime = inp.get("Tax Regime", "new").lower()
    city = inp.get("City", "non-metro").lower()
    age = inp.get("Age", 30)
    old = regime == "old"
    gs = inp.get("Gross Salary", {})

    # ---- Salaries
    nps = inp.get("NPS", {})
    employer_nps = g(nps, "Tier-1 Employer Contribution")
    gross_salary = sum(g(gs, k) for k in ["Basic Salary", "Dearness Allowance", "HRA", "Conveyance Allowance",
                                          "Medical Allowance", "Bonuses and Incentives", "Overtime Pay", "LTA",
                                          "Special Allowance", "Entertainment Allowance"])
    gross_salary += employer_nps                    # C18: s.17(1)(viii); 80CCD(2) deducts it below
    basic_da = g(gs, "Basic Salary") + g(gs, "Dearness Allowance")
    if old:
        hra = max(0.0, min(g(gs, "HRA"), (0.50 if city == "metro" else 0.40) * basic_da,
                           g(inp, "Actual Rent Paid") - 0.10 * basic_da))
        lta = min(g(gs, "LTA"), g(inp, "LTA Travel Expenses Claimed"))
    else:
        hra = lta = 0.0
    s16_ia = min(STANDARD_DEDUCTION[regime], gross_salary)
    s16_ii = min(5_000, 0.20 * g(gs, "Basic Salary"), g(gs, "Entertainment Allowance")) \
        if (employment == "government" and old) else 0.0
    s16_iii = min(2_500, g(inp, "Professional Tax")) if old else 0.0
    net_salary = gross_salary - hra - lta - s16_ia - s16_ii - s16_iii

    # ---- Other sources
    sb, dep = g(inp, "Savings Bank Interest"), g(inp, "Deposit Interest")
    oth, epf_int = g(inp, "Other Interest"), g(inp, "EPF Taxable Interest")
    other_sources = sb + dep + oth + epf_int

    # ---- Deductions (before the s.80A(2) cap)
    ded = {k: 0.0 for k in ["80C", "80CCC", "80CCD(1)", "80CCD(1B)", "80CCD(2)", "80D", "80E", "80G", "80TTA", "80TTB"]}
    base_pct = 0.14 if (not old or employment == "government") else 0.10
    ded["80CCD(2)"] = min(employer_nps, base_pct * basic_da)                            # C9
    if old:
        c80 = sum([g(inp, "PPF"), g(inp, "EPF", "Employee Contribution", "Deducted from Salary"),
                   g(inp, "EPF", "Employee Contribution", "Voluntary"), g(inp, "ELSS"), g(inp, "NSC"),
                   g(inp, "Sukanya Samriddhi Yojana"), g(inp, "SCSS")])
        ded["80C"] = min(c80, 150_000)
        ded["80CCC"] = min(g(inp, "Pension Scheme Premium", "Amount"), 150_000 - ded["80C"])   # C7, C8
        nps_self = g(nps, "Tier-1 Self Contribution")
        ded["80CCD(1)"] = min(nps_self, 0.10 * basic_da, 150_000 - ded["80C"] - ded["80CCC"])
        ded["80CCD(1B)"] = min(50_000, nps_self - ded["80CCD(1)"])

        # 80D (C10)
        premiums = {"self": 0.0, "parents": 0.0}
        checkups = {"self": 0.0, "parents": 0.0}
        senior = {"self": age >= 60, "parents": False}
        for e in inp.get("Health Insurance", []):
            ben = e.get("Beneficiary", "").lower()
            if ben not in VALID_BENEFICIARIES or e.get("Paid By", "self").lower() == "group medical insurance":
                continue
            grp = "parents" if ben == "parents" else "self"
            purpose = e.get("Payment Purpose", "").lower()
            if purpose == "insurance premium":
                if e.get("Payment Mode", "cheque").lower() == "cash":
                    continue                     # not deductible, so it can't raise the limit either
                premiums[grp] += g(e, "Amount") / max(1, g(e, "Number of Years Paid", default=1))
            elif purpose == "preventive health checkup":
                checkups[grp] += g(e, "Amount")
            else:
                continue
            if ben in ("self", "spouse", "parents") and g(e, "Beneficiary Age") >= 60:
                senior[grp] = True
        limits = {k: 50_000 if senior[k] else 25_000 for k in premiums}
        # Check-ups: Rs 5,000 in aggregate, each inside its own group's limit; placed where there's room.
        checkup_room = sum(min(checkups[k], max(0.0, limits[k] - premiums[k])) for k in premiums)
        ded["80D"] = sum(min(premiums[k], limits[k]) for k in premiums) + min(5_000, checkup_room)

        edu = inp.get("Education Loan Interest", {})
        if isinstance(edu, dict) and 1 <= g(edu, "Year of Repayment") <= 8:
            ded["80E"] = g(edu, "Interest Paid")
        for d in inp.get("Donations", []):
            amt = g(d, "Amount")
            if d.get("Mode", "").lower() == "cash" and amt > 2_000:
                continue
            name = d.get("Scheme Name", "")
            ded["80G"] += amt if name in FULL_EXEMPT_SCHEMES else 0.5 * amt if name in HALF_EXEMPT_SCHEMES else 0
        if age >= 60:
            ded["80TTB"] = min(50_000, sb + dep)
        else:
            ded["80TTA"] = min(10_000, sb)
    ded_claimed = sum(ded.values())

    # ---- Capital gains and loss set-off (C4, C5): try every legal order, keep the cheapest
    s111_raw, l112a_raw, so_comp, lt_comp = classify_gains(inp)
    pools = {"s111": s111_raw, "so": sum(so_comp.values()), "l112a": l112a_raw, "l112": sum(lt_comp.values())}
    st_loss = sum(-pools[k] for k in ("s111", "so") if pools[k] < 0)
    lt_loss = sum(-pools[k] for k in ("l112a", "l112") if pools[k] < 0)
    pools = {k: max(0.0, v) for k, v in pools.items()}

    def eligible(e):
        try:
            return 0 < CURRENT_AY_START - (int(str(e.get("Financial Year", ""))[:4]) + 1) <= LOSS_CARRY_FORWARD_YEARS
        except ValueError:
            return False
    st_loss += sum(g(e, "Loss Amount") for e in inp.get("Short Term Capital Loss", []) if eligible(e))
    lt_loss += sum(g(e, "Loss Amount") for e in inp.get("Long Term Capital Loss", []) if eligible(e))

    def finish(p):
        special = p["s111"] + p["l112"] + p["l112a"]
        gti = net_salary + other_sources + p["s111"] + p["so"] + p["l112a"] + p["l112"]
        allowed = min(ded_claimed, max(0.0, gti - special))                        # C11
        ti = gti - allowed
        ti_r = round10(ti) if STATUTORY_ROUNDING else ti                          # C17
        normal = max(0.0, ti_r - special)
        t, sur, cess = total_tax(normal, p["s111"], p["l112"], p["l112a"], regime, age)
        liability = t["after"] + sur + cess
        if STATUTORY_ROUNDING:
            liability = round10(liability)
        return {"gti": gti, "allowed": allowed, "ti": ti_r, "t": t, "sur": sur, "cess": cess, "liability": liability}

    best = None
    # C5: the taxpayer may choose the set-off order. A fixed order is used (long-term loss:
    # s.112 then s.112A; short-term loss: 111A, STCG other, s.112, s.112A); set
    # OPTIMISE_ORDERS = True to try every order and keep the lowest tax instead.
    lt_orders = (("l112", "l112a"), ("l112a", "l112")) if OPTIMISE_ORDERS else (("l112", "l112a"),)
    for lt_order in lt_orders:
        st_orders = itertools.permutations(("s111", "so", "l112", "l112a")) if OPTIMISE_ORDERS \
            else [("s111", "so", "l112", "l112a")]
        for st_order in st_orders:
            p, st_left, lt_left = apply_losses(pools, st_loss, lt_loss, st_order, lt_order)
            r = finish(p)
            if best is None or r["liability"] < best[1]["liability"] - 0.005:
                best = (p, r, st_left, lt_left, st_order, lt_order)
    p, r, st_cf, lt_cf, st_order, lt_order = best
    so_out = scale_components(so_comp, p["so"])
    lt_out = scale_components(lt_comp, p["l112"])
    t = r["t"]
    tds = g(inp, "TDS")

    output = {
        "Under Head Salaries": {
            "Gross Salary": round2(gross_salary),
            "Exemptions": {"Section 10(13A)": round2(hra), "Section 10(5)": round2(lta)},
            "Section 16(ia)": round2(s16_ia), "Section 16(ii)": round2(s16_ii),
            "Section 16(iii)": round2(s16_iii), "Net Salary": round2(net_salary),
        },
        "Capital Gains": {
            "STCG (Section 111A)": round2(p["s111"]),
            "STCG (Other)": {**{k: round2(v) for k, v in so_out.items() if k in SCHEMA_COMPONENTS},
                             "Total": round2(p["so"])},
            "LTCG (Section 112A)": round2(p["l112a"]),
            "LTCG (Non-Equity)": {**{k: round2(v) for k, v in lt_out.items() if k in SCHEMA_COMPONENTS},
                                  "Total": round2(p["l112"])},
            "LTCG (Other)": 0.0,
        },
        "Income from Other Sources": {
            "Savings Bank Interest": round2(sb), "Deposit Interest": round2(dep),
            "Other Interest": {"EPF Taxable Interest": round2(epf_int)},
        },
        "Gross Total Income": round2(r["gti"]),
        "Deductions": {**{k: round2(v) for k, v in ded.items()}, "Total Deductions": round2(r["allowed"])},
        "Total Taxable Income": round2(r["ti"]),
        "Tax Computation": {
            "Tax at Slab Rates": round2(t["slab"]),
            "Tax on STCG (Section 111A)": round2(t["t111"]),
            "Tax on STCG (Other)": 0.0,
            "Tax on LTCG (Section 112A)": round2(t["t112a"]),
            "Tax on LTCG (Non-Equity)": round2(t["t112"]),
            "Tax on LTCG (Other)": 0.0,
            "Total Tax Before Rebate": round2(t["before"]),
            "Less: Rebate under Section 87A": round2(t["rebate"]),
            "Tax After Rebate": round2(t["after"]),
            "Surcharge": round2(r["sur"]),
            "Health and Education Cess": round2(r["cess"]),
            "Total Tax Liability": round2(r["liability"]),
            "Less: TDS": round2(tds),
            "Net Tax Payable / Refund": round2(r["liability"] - tds),
        },
    }
    if details:
        return output, {"deductions_claimed_before_cap": round2(ded_claimed),
                        "st_loss_carried_forward": round2(st_cf), "lt_loss_carried_forward": round2(lt_cf),
                        "st_setoff_order": st_order, "lt_setoff_order": lt_order}
    return output


def main():
    if len(sys.argv) != 3:
        print("Usage: python tax_calculator_corrected.py <input.json> <output.json>")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        inp = json.load(f)
    inp = inp.get("input", inp)          # accepts a raw input or an input_NNNN.json test file
    with open(sys.argv[2], "w") as f:
        json.dump(calculate(inp), f, indent=4)
    print(f"Output written to {sys.argv[2]}")


if __name__ == "__main__":
    main()
