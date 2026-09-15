"""
Generates synthetic benchmark test cases for the Indian Income Tax Calculator.

Supports three modes:
- pairwise: covering array across all 19 parameters (~200-400 cases)
- ota: baseline + one variation each (~70 cases)
- profiles: 10 taxpayer profiles x ~50 cases each = ~500 dense cases

Usage:
    python3 tests/generate_test_cases.py [pairwise|ota|profiles]
"""

import copy
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tax_calculator import calculate

from allpairspy import AllPairs

# ---------------------------------------------------------------------------
# BASE_INPUT — all zeros, age=35, private, new, metro
# ---------------------------------------------------------------------------

BASE_INPUT = {
    "Age": 35,
    "Employment Type": "private",
    "Tax Regime": "new",
    "City": "metro",
    "Gross Salary": {
        "Basic Salary": 0,
        "Dearness Allowance": 0,
        "HRA": 0,
        "Conveyance Allowance": 0,
        "Medical Allowance": 0,
        "Bonuses and Incentives": 0,
        "Overtime Pay": 0,
        "LTA": 0,
        "Special Allowance": 0,
        "Entertainment Allowance": 0,
    },
    "Actual Rent Paid": 0,
    "LTA Travel Expenses Claimed": 0,
    "Professional Tax": 0,
    "Stock Sale Transactions": [],
    "Long Term Capital Loss": [],
    "Short Term Capital Loss": [],
    "Mutual Fund Transactions": [],
    "Privately Owned Vehicle": {
        "Sale Amount": 0, "Purchase Amount": 0, "Held for duration in years": 0,
    },
    "Bonds": {
        "Sale Amount": 0, "Purchase Amount": 0, "Held for duration in years": 0,
    },
    "Debentures": {
        "Sale Amount": 0, "Purchase Amount": 0, "Held for duration in years": 0,
    },
    "G-Secs": {
        "Sale Amount": 0, "Purchase Amount": 0, "Held for duration in years": 0,
    },
    "Savings Bank Interest": 0,
    "Deposit Interest": 0,
    "Other Interest": 0,
    "EPF Taxable Interest": 0,
    "PPF": 0,
    "EPF": {
        "Employee Contribution": {"Deducted from Salary": 0, "Voluntary": 0},
        "Employer Contribution": 0,
    },
    "ELSS": 0,
    "NSC": 0,
    "Sukanya Samriddhi Yojana": 0,
    "SCSS": 0,
    "Pension Scheme Premium": {"Amount": 0, "Number of Years Paid": 1},
    "NPS": {
        "Tier-1 Self Contribution": 0,
        "Tier-1 Employer Contribution": 0,
        "Tier-2": 0,
    },
    "Education Loan Interest": {"Interest Paid": 0, "Year of Repayment": 0},
    "Health Insurance": [],
    "Donations": [],
    "TDS": 0,
}

# ---------------------------------------------------------------------------
# PARAMETERS — 19 parameters, each with named factor overrides
# Keys starting with _ are meta-keys consumed by resolve_cross_dependencies
# or build_case (not merged into the input).
# ---------------------------------------------------------------------------

PARAMETERS = {

    # ---- 1. salary_level (7 factors) ----
    "salary_level": {
        "zero": {},
        "low_below_rebate": {
            "Gross Salary": {
                "Basic Salary": 400_000, "Dearness Allowance": 100_000,
                "HRA": 80_000, "LTA": 20_000, "Conveyance Allowance": 15_000,
                "Medical Allowance": 10_000, "Bonuses and Incentives": 25_000,
                "Special Allowance": 350_000,
            },
            "Professional Tax": 2_400,
        },
        "just_above_12L_marginal": {
            "Gross Salary": {
                "Basic Salary": 500_000, "Dearness Allowance": 100_000,
                "HRA": 100_000, "LTA": 25_000, "Conveyance Allowance": 20_000,
                "Medical Allowance": 15_000, "Bonuses and Incentives": 50_000,
                "Special Allowance": 490_000,
            },
            "Professional Tax": 2_500,
        },
        "mid": {
            "Gross Salary": {
                "Basic Salary": 800_000, "Dearness Allowance": 200_000,
                "HRA": 200_000, "LTA": 50_000, "Conveyance Allowance": 30_000,
                "Medical Allowance": 20_000, "Bonuses and Incentives": 100_000,
                "Special Allowance": 700_000,
            },
            "Professional Tax": 2_500,
        },
        "just_above_50L": {
            "Gross Salary": {
                "Basic Salary": 2_000_000, "Dearness Allowance": 300_000,
                "HRA": 500_000, "LTA": 80_000, "Conveyance Allowance": 50_000,
                "Medical Allowance": 30_000, "Bonuses and Incentives": 300_000,
                "Overtime Pay": 50_000, "Special Allowance": 1_890_000,
            },
            "Professional Tax": 2_500,
        },
        "just_above_1Cr": {
            "Gross Salary": {
                "Basic Salary": 3_500_000, "Dearness Allowance": 500_000,
                "HRA": 800_000, "LTA": 100_000, "Conveyance Allowance": 80_000,
                "Medical Allowance": 50_000, "Bonuses and Incentives": 600_000,
                "Overtime Pay": 100_000, "Special Allowance": 4_570_000,
            },
            "Professional Tax": 2_500,
        },
        "above_2Cr": {
            "Gross Salary": {
                "Basic Salary": 7_000_000, "Dearness Allowance": 800_000,
                "HRA": 1_500_000, "LTA": 150_000, "Conveyance Allowance": 100_000,
                "Medical Allowance": 80_000, "Bonuses and Incentives": 1_500_000,
                "Overtime Pay": 200_000, "Special Allowance": 9_770_000,
            },
            "Professional Tax": 2_500,
        },
    },

    # ---- 2. hra_city (5 factors) ----
    "hra_city": {
        "none": {"City": "metro", "Actual Rent Paid": 0},
        "metro_rent_10pct_binding": {
            "City": "metro", "_hra_mode": "rent_binding",
        },
        "metro_pct_binding": {
            "City": "metro", "_hra_mode": "pct_binding",
        },
        "metro_hra_received_binding": {
            "City": "metro", "_hra_mode": "hra_binding",
        },
        "nonmetro_40pct_binding": {
            "City": "non-metro", "_hra_mode": "pct_binding",
        },
    },

    # ---- 3. lta (3 factors) ----
    "lta": {
        "none": {"LTA Travel Expenses Claimed": 0},
        "claim_less_than_salary_lta": {"_lta_mode": "partial_claim"},
        "claim_exceeds_salary_lta": {"_lta_mode": "excess_claim"},
    },

    # ---- 4. employment_type (2 factors) ----
    "employment_type": {
        "private": {"Employment Type": "private"},
        "government": {"Employment Type": "government"},
    },

    # ---- 5. entertainment_allowance (3 factors) ----
    "entertainment_allowance": {
        "none": {},
        "low_amount_binding": {
            "Gross Salary": {"Entertainment Allowance": 3_000},
        },
        "high_5k_cap_binding": {
            "Gross Salary": {"Entertainment Allowance": 50_000},
        },
    },

    # ---- 6. stock_stcg (3 factors) ----
    "stock_stcg": {
        "none": {},
        "stcg_gain": {
            "_stock_txns": [{
                "Sale Price": 250, "Cost Price": 200, "Quantity": 1000,
                "Brokerage": 500, "STT": 250,
                "Purchase Date": "2025-04-01", "Sale Date": "2025-10-15",
                "FMV as of 31 Jan 2018": 0,
            }],
        },
        "stcg_loss": {
            "_stock_txns": [{
                "Sale Price": 150, "Cost Price": 200, "Quantity": 1000,
                "Brokerage": 500, "STT": 250,
                "Purchase Date": "2025-04-01", "Sale Date": "2025-10-15",
                "FMV as of 31 Jan 2018": 0,
            }],
        },
    },

    # ---- 7. stock_ltcg (4 factors) ----
    "stock_ltcg": {
        "none": {},
        "ltcg_below_exempt": {
            "_stock_txns": [{
                "Sale Price": 280, "Cost Price": 200, "Quantity": 1000,
                "Brokerage": 0, "STT": 500,
                "Purchase Date": "2024-04-01", "Sale Date": "2025-10-15",
                "FMV as of 31 Jan 2018": 0,
            }],
        },
        "ltcg_above_exempt": {
            "_stock_txns": [{
                "Sale Price": 500, "Cost Price": 200, "Quantity": 1000,
                "Brokerage": 500, "STT": 500,
                "Purchase Date": "2024-04-01", "Sale Date": "2025-10-15",
                "FMV as of 31 Jan 2018": 0,
            }],
        },
        "ltcg_fmv_benefit": {
            "_stock_txns": [{
                "Sale Price": 400, "Cost Price": 100, "Quantity": 1000,
                "Brokerage": 0, "STT": 500,
                "Purchase Date": "2024-04-01", "Sale Date": "2025-10-15",
                "FMV as of 31 Jan 2018": 180,
            }],
        },
    },

    # ---- 8. capital_loss_carryforward (6 factors) ----
    "capital_loss_carryforward": {
        "none": {},
        "stcl_offsets_stcg": {
            "Short Term Capital Loss": [
                {"Financial Year": "2023-24", "Loss Amount": 20_000},
            ],
        },
        "stcl_spills_to_ltcg": {
            "Short Term Capital Loss": [
                {"Financial Year": "2023-24", "Loss Amount": 200_000},
            ],
        },
        "ltcl_offsets_ltcg": {
            "Long Term Capital Loss": [
                {"Financial Year": "2023-24", "Loss Amount": 50_000},
            ],
        },
        "ltcl_exceeds_ltcg": {
            "Long Term Capital Loss": [
                {"Financial Year": "2023-24", "Loss Amount": 500_000},
            ],
        },
        "loss_beyond_8_years": {
            "Long Term Capital Loss": [
                {"Financial Year": "2015-16", "Loss Amount": 100_000},
            ],
        },
    },

    # ---- 9. other_assets (4 factors) ----
    "other_assets": {
        "none": {},
        "bonds_short_term": {
            "Bonds": {
                "Sale Amount": 120_000, "Purchase Amount": 100_000,
                "Held for duration in years": 0.5,
            },
        },
        "gsecs_long_term": {
            "G-Secs": {
                "Sale Amount": 150_000, "Purchase Amount": 100_000,
                "Held for duration in years": 2,
            },
        },
        "vehicle_gain": {
            "Privately Owned Vehicle": {
                "Sale Amount": 300_000, "Purchase Amount": 200_000,
                "Held for duration in years": 3,
            },
        },
    },

    # ---- 10. equity_mf (4 factors) ----
    "equity_mf": {
        "none": {},
        "equity_stcg": {
            "_mf_txns": [{
                "Type": "equity", "Purchase Date": "2025-06-01",
                "Sale Date": "2025-11-15",
                "Purchase Value": 100_000, "Sale Value": 130_000,
            }],
        },
        "equity_ltcg": {
            "_mf_txns": [{
                "Type": "equity", "Purchase Date": "2024-01-15",
                "Sale Date": "2025-06-15",
                "Purchase Value": 200_000, "Sale Value": 350_000,
            }],
        },
        "elss_matured": {
            "_mf_txns": [{
                "Type": "elss", "Purchase Date": "2022-01-01",
                "Sale Date": "2025-06-01",
                "Purchase Value": 150_000, "Sale Value": 250_000,
            }],
        },
    },

    # ---- 11. non_equity_mf (7 factors) ----
    "non_equity_mf": {
        "none": {},
        "debt_pre2023_jan_mar": {
            "_mf_txns": [{
                "Type": "debt", "Purchase Date": "2022-03-15",
                "Sale Date": "2025-06-01",
                "Purchase Value": 200_000, "Sale Value": 280_000,
            }],
        },
        "debt_pre2023_apr_dec": {
            "_mf_txns": [{
                "Type": "debt", "Purchase Date": "2021-09-10",
                "Sale Date": "2025-06-01",
                "Purchase Value": 200_000, "Sale Value": 280_000,
            }],
        },
        "debt_post2023_slab": {
            "_mf_txns": [{
                "Type": "debt", "Purchase Date": "2023-06-01",
                "Sale Date": "2025-12-01",
                "Purchase Value": 200_000, "Sale Value": 260_000,
            }],
        },
        "gold_etf_stcg": {
            "_mf_txns": [{
                "Type": "gold-etf", "Purchase Date": "2025-03-01",
                "Sale Date": "2025-09-01",
                "Purchase Value": 100_000, "Sale Value": 125_000,
            }],
        },
        "gold_etf_ltcg": {
            "_mf_txns": [{
                "Type": "gold-etf", "Purchase Date": "2024-01-01",
                "Sale Date": "2025-06-01",
                "Purchase Value": 100_000, "Sale Value": 140_000,
            }],
        },
        "international_ltcg": {
            "_mf_txns": [{
                "Type": "international", "Purchase Date": "2023-01-01",
                "Sale Date": "2025-06-01",
                "Purchase Value": 150_000, "Sale Value": 200_000,
            }],
        },
    },

    # ---- 12. deductions_80c_cce (4 factors) ----
    "deductions_80c_cce": {
        "none": {},
        "partial_under_cap": {
            "PPF": 50_000,
            "ELSS": 30_000,
        },
        "components_sum_exactly_1_5L": {
            "PPF": 80_000,
            "EPF": {"Employee Contribution": {"Deducted from Salary": 40_000}},
            "ELSS": 30_000,
        },
        "over_cap_proportional": {
            "PPF": 100_000,
            "ELSS": 80_000,
            "Pension Scheme Premium": {"Amount": 60_000, "Number of Years Paid": 3},
        },
    },

    # ---- 13. nps (5 factors) ----
    "nps": {
        "none": {},
        "self_only_within_ccd1": {
            "NPS": {"Tier-1 Self Contribution": 30_000},
        },
        "spills_to_ccd1b": {
            "NPS": {"Tier-1 Self Contribution": 200_000},
        },
        "with_employer": {
            "NPS": {
                "Tier-1 Self Contribution": 50_000,
                "Tier-1 Employer Contribution": 50_000,
            },
        },
        "tier2_only_trap": {
            "NPS": {"Tier-2": 1_000},
        },
    },

    # ---- 14. health_insurance_80d (7 factors) ----
    "health_insurance_80d": {
        "none": {"Health Insurance": []},
        "valid_cheque_self": {
            "Health Insurance": [{
                "Payment Purpose": "insurance premium",
                "Number of Years Paid": 1,
                "Beneficiary": "self", "Beneficiary Age": 0,
                "Paid By": "self", "Payment Mode": "cheque", "Amount": 15_000,
            }],
        },
        "cash_premium_excluded": {
            "Health Insurance": [{
                "Payment Purpose": "insurance premium",
                "Number of Years Paid": 1,
                "Beneficiary": "self", "Beneficiary Age": 0,
                "Paid By": "self", "Payment Mode": "cash", "Amount": 25_000,
            }],
        },
        "group_medical_excluded": {
            "Health Insurance": [{
                "Payment Purpose": "insurance premium",
                "Number of Years Paid": 1,
                "Beneficiary": "self", "Beneficiary Age": 0,
                "Paid By": "group medical insurance",
                "Payment Mode": "cheque", "Amount": 25_000,
            }],
        },
        "invalid_beneficiary_sibling": {
            "Health Insurance": [{
                "Payment Purpose": "insurance premium",
                "Number of Years Paid": 1,
                "Beneficiary": "sibling", "Beneficiary Age": 30,
                "Paid By": "self", "Payment Mode": "cheque", "Amount": 20_000,
            }],
        },
        "senior_parent_50k_limit": {
            "Health Insurance": [
                {
                    "Payment Purpose": "insurance premium",
                    "Number of Years Paid": 1,
                    "Beneficiary": "self", "Beneficiary Age": 0,
                    "Paid By": "self", "Payment Mode": "cheque", "Amount": 20_000,
                },
                {
                    "Payment Purpose": "insurance premium",
                    "Number of Years Paid": 1,
                    "Beneficiary": "parents", "Beneficiary Age": 65,
                    "Paid By": "self", "Payment Mode": "cheque", "Amount": 45_000,
                },
            ],
        },
        "preventive_checkup_cap": {
            "Health Insurance": [{
                "Payment Purpose": "preventive health checkup",
                "Beneficiary": "self", "Beneficiary Age": 0,
                "Paid By": "self", "Payment Mode": "cash", "Amount": 8_000,
            }],
        },
    },

    # ---- 15. education_loan_80e (3 factors) ----
    "education_loan_80e": {
        "none": {},
        "within_8yr_window": {
            "Education Loan Interest": {
                "Interest Paid": 80_000, "Year of Repayment": 5,
            },
        },
        "beyond_8yr_trap": {
            "Education Loan Interest": {
                "Interest Paid": 80_000, "Year of Repayment": 9,
            },
        },
    },

    # ---- 16. donations_80g (5 factors) ----
    "donations_80g": {
        "none": {"Donations": []},
        "cash_over_2k_excluded": {
            "Donations": [
                {"Scheme Name": "PM Cares Fund", "Amount": 5_000, "Mode": "cash"},
            ],
        },
        "full_exempt_100pct": {
            "Donations": [
                {"Scheme Name": "PM Cares Fund", "Amount": 10_000, "Mode": "cheque"},
            ],
        },
        "half_exempt_50pct": {
            "Donations": [
                {
                    "Scheme Name": "Prime Minister's Drought Relief Fund",
                    "Amount": 10_000, "Mode": "cheque",
                },
            ],
        },
        "mixed_100_and_50_pct": {
            "Donations": [
                {"Scheme Name": "PM Cares Fund", "Amount": 10_000, "Mode": "cheque"},
                {
                    "Scheme Name": "Prime Minister's Drought Relief Fund",
                    "Amount": 8_000, "Mode": "cheque",
                },
            ],
        },
    },

    # ---- 17. age_and_interest (4 factors) ----
    "age_and_interest": {
        "young_low_interest": {
            "Age": 35,
            "Savings Bank Interest": 5_000,
            "Deposit Interest": 10_000,
        },
        "young_high_interest": {
            "Age": 45,
            "Savings Bank Interest": 25_000,
            "Deposit Interest": 30_000,
            "Other Interest": 5_000,
            "EPF Taxable Interest": 8_000,
        },
        "senior_below_limit": {
            "Age": 62,
            "Savings Bank Interest": 20_000,
            "Deposit Interest": 15_000,
        },
        "senior_above_limit": {
            "Age": 72,
            "Savings Bank Interest": 30_000,
            "Deposit Interest": 40_000,
            "Other Interest": 3_000,
            "EPF Taxable Interest": 5_000,
        },
    },

    # ---- 18. tax_regime (2 factors) ----
    "tax_regime": {
        "new": {"Tax Regime": "new"},
        "old": {"Tax Regime": "old"},
    },

    # ---- 19. tds (3 factors) ----
    "tds": {
        "none": {"_tds_mode": "none"},
        "partial": {"_tds_mode": "partial"},
        "excess_refund": {"_tds_mode": "excess_refund"},
    },
}

PARAM_ORDER = list(PARAMETERS.keys())

# ---------------------------------------------------------------------------
# PROFILES — 10 taxpayer archetypes, each with fixed + varied params
# ---------------------------------------------------------------------------

PROFILES = {
    "P01_mid_salary_private_new_metro": {
        "fixed": {
            "salary_level": "mid",
            "hra_city": "metro_pct_binding",
            "lta": "claim_less_than_salary_lta",
            "employment_type": "private",
            "entertainment_allowance": "high_5k_cap_binding",
            "tax_regime": "new",
            "age_and_interest": "young_low_interest",
            "deductions_80c_cce": "partial_under_cap",
            "tds": "partial",
        },
        "vary": [
            "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "nps", "health_insurance_80d",
            "donations_80g",
        ],
    },

    "P02_high_salary_govt_old_nonmetro": {
        "fixed": {
            "salary_level": "just_above_50L",
            "hra_city": "nonmetro_40pct_binding",
            "employment_type": "government",
            "entertainment_allowance": "high_5k_cap_binding",
            "tax_regime": "old",
            "age_and_interest": "young_high_interest",
            "deductions_80c_cce": "over_cap_proportional",
            "nps": "with_employer",
            "tds": "partial",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "health_insurance_80d",
            "education_loan_80e", "donations_80g",
        ],
    },

    "P03_senior_citizen_old_investment_heavy": {
        "fixed": {
            "salary_level": "low_below_rebate",
            "hra_city": "none",
            "employment_type": "private",
            "entertainment_allowance": "none",
            "tax_regime": "old",
            "age_and_interest": "senior_above_limit",
            "deductions_80c_cce": "components_sum_exactly_1_5L",
            "health_insurance_80d": "senior_parent_50k_limit",
            "tds": "partial",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "nps",
            "education_loan_80e", "donations_80g",
        ],
    },

    "P04_marginal_relief_new_regime": {
        "fixed": {
            "salary_level": "just_above_12L_marginal",
            "hra_city": "metro_rent_10pct_binding",
            "employment_type": "private",
            "entertainment_allowance": "none",
            "tax_regime": "new",
            "age_and_interest": "young_low_interest",
            "tds": "none",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "deductions_80c_cce",
            "nps", "health_insurance_80d", "donations_80g", "education_loan_80e",
        ],
    },

    "P05_surcharge_boundary_old_regime": {
        "fixed": {
            "salary_level": "just_above_1Cr",
            "hra_city": "metro_hra_received_binding",
            "employment_type": "private",
            "entertainment_allowance": "low_amount_binding",
            "tax_regime": "old",
            "age_and_interest": "young_high_interest",
            "deductions_80c_cce": "over_cap_proportional",
            "nps": "with_employer",
            "tds": "partial",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "health_insurance_80d",
            "education_loan_80e", "donations_80g",
        ],
    },

    "P06_zero_salary_capital_gains_only": {
        "fixed": {
            "salary_level": "zero",
            "hra_city": "none",
            "lta": "none",
            "employment_type": "private",
            "entertainment_allowance": "none",
            "age_and_interest": "young_high_interest",
            "tax_regime": "old",
            "tds": "excess_refund",
        },
        "vary": [
            "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "deductions_80c_cce",
            "nps", "health_insurance_80d", "education_loan_80e", "donations_80g",
        ],
    },

    "P07_low_income_old_regime_maxed_deductions": {
        "fixed": {
            "salary_level": "low_below_rebate",
            "hra_city": "metro_rent_10pct_binding",
            "employment_type": "government",
            "entertainment_allowance": "low_amount_binding",
            "tax_regime": "old",
            "age_and_interest": "young_low_interest",
            "deductions_80c_cce": "components_sum_exactly_1_5L",
            "nps": "spills_to_ccd1b",
            "health_insurance_80d": "senior_parent_50k_limit",
            "tds": "none",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "education_loan_80e",
            "donations_80g",
        ],
    },

    "P08_above_2cr_new_regime": {
        "fixed": {
            "salary_level": "above_2Cr",
            "hra_city": "metro_pct_binding",
            "employment_type": "private",
            "entertainment_allowance": "high_5k_cap_binding",
            "tax_regime": "new",
            "age_and_interest": "young_high_interest",
            "nps": "with_employer",
            "tds": "partial",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "deductions_80c_cce",
            "health_insurance_80d", "education_loan_80e", "donations_80g",
        ],
    },

    "P09_govt_new_regime_nps_focus": {
        "fixed": {
            "salary_level": "mid",
            "hra_city": "nonmetro_40pct_binding",
            "employment_type": "government",
            "entertainment_allowance": "high_5k_cap_binding",
            "tax_regime": "new",
            "age_and_interest": "senior_below_limit",
            "deductions_80c_cce": "over_cap_proportional",
            "nps": "with_employer",
            "tds": "partial",
        },
        "vary": [
            "lta", "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "health_insurance_80d",
            "education_loan_80e", "donations_80g",
        ],
    },

    "P10_mixed_income_old_all_active": {
        "fixed": {
            "salary_level": "mid",
            "hra_city": "metro_pct_binding",
            "lta": "claim_less_than_salary_lta",
            "employment_type": "government",
            "entertainment_allowance": "low_amount_binding",
            "tax_regime": "old",
            "age_and_interest": "young_high_interest",
            "deductions_80c_cce": "over_cap_proportional",
            "nps": "with_employer",
            "health_insurance_80d": "senior_parent_50k_limit",
        },
        "vary": [
            "stock_stcg", "stock_ltcg", "equity_mf", "non_equity_mf",
            "capital_loss_carryforward", "other_assets", "education_loan_80e",
            "donations_80g", "tds",
        ],
    },
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def deep_merge(base, overrides):
    """Recursively merge overrides onto a deep copy of base."""
    result = copy.deepcopy(base)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def resolve_cross_dependencies(case, meta):
    """Fix values that depend on other parameters in the same case."""
    age = case.get("Age", 35)
    gs = case.get("Gross Salary", {})
    basic_da = gs.get("Basic Salary", 0) + gs.get("Dearness Allowance", 0)
    hra_received = gs.get("HRA", 0)
    lta_in_salary = gs.get("LTA", 0)
    city = case.get("City", "metro")
    metro_pct = 0.50 if city == "metro" else 0.40

    # --- HRA rent computation ---
    hra_mode = meta.get("_hra_mode")
    if hra_mode == "rent_binding":
        pct_val = metro_pct * basic_da
        target = min(hra_received, pct_val) * 0.5
        case["Actual Rent Paid"] = round(0.10 * basic_da + max(target, 1000))
    elif hra_mode == "pct_binding":
        pct_val = metro_pct * basic_da
        if pct_val > 0:
            if hra_received <= pct_val:
                gs["HRA"] = round(pct_val * 1.5)
            case["Actual Rent Paid"] = round(0.10 * basic_da + pct_val * 2)
        else:
            case["Actual Rent Paid"] = 0
    elif hra_mode == "hra_binding":
        if hra_received > 0:
            case["Actual Rent Paid"] = round(0.10 * basic_da + hra_received * 3)
        else:
            case["Actual Rent Paid"] = 0

    # --- LTA claim ---
    lta_mode = meta.get("_lta_mode")
    if lta_mode == "partial_claim":
        case["LTA Travel Expenses Claimed"] = round(lta_in_salary * 0.5)
    elif lta_mode == "excess_claim":
        case["LTA Travel Expenses Claimed"] = round(lta_in_salary * 1.5)

    # --- Health Insurance beneficiary age ---
    for entry in case.get("Health Insurance", []):
        ben = entry.get("Beneficiary", "").lower()
        if ben in {"self", "spouse", "children"} and entry.get("Beneficiary Age", 0) == 0:
            entry["Beneficiary Age"] = age


# ---------------------------------------------------------------------------
# Build case
# ---------------------------------------------------------------------------

def build_case(combo, profile=None):
    """Build one test case from a combo dict {param_name: factor_name}.

    `profile` is the taxpayer archetype key (e.g. "P01_mid_salary_private_new_metro")
    for profile-mode cases, or None/"pairwise"/"ota" for the other generation modes.
    """
    merged = copy.deepcopy(BASE_INPUT)
    stock_txns = []
    mf_txns = []
    meta = {}

    for param_name in PARAM_ORDER:
        if param_name not in combo:
            continue
        factor_name = combo[param_name]
        factor = PARAMETERS[param_name][factor_name]

        for k, v in factor.items():
            if k == "_stock_txns":
                stock_txns.extend(copy.deepcopy(v))
            elif k == "_mf_txns":
                mf_txns.extend(copy.deepcopy(v))
            elif k.startswith("_"):
                meta[k] = v

        overrides = {k: v for k, v in factor.items() if not k.startswith("_")}
        merged = deep_merge(merged, overrides)

    merged["Stock Sale Transactions"] = stock_txns
    merged["Mutual Fund Transactions"] = mf_txns

    resolve_cross_dependencies(merged, meta)

    # --- TDS: two-pass approach ---
    tds_mode = meta.get("_tds_mode", "none")
    merged["TDS"] = 0
    first_pass = calculate(copy.deepcopy(merged))
    total_tax = first_pass["Tax Computation"]["Total Tax Liability"]

    if tds_mode == "partial":
        merged["TDS"] = round(total_tax * 0.6, 2) if total_tax > 0 else 0
    elif tds_mode == "excess_refund":
        merged["TDS"] = round(max(total_tax * 1.3, 10_000), 2)

    result = calculate(copy.deepcopy(merged))

    desc = "|".join(f"{p}={combo[p]}" for p in PARAM_ORDER if p in combo)
    archetype = profile.split("_")[0] if profile and profile in PROFILES else None
    return {
        "input": merged,
        "_description": desc,
        "_profile": profile,
        "_archetype": archetype,
        "_expected": result,
    }


# ---------------------------------------------------------------------------
# Combination generators
# ---------------------------------------------------------------------------

def generate_pairwise(param_names):
    """Pairwise covering array across given parameters."""
    factor_lists = [list(PARAMETERS[p].keys()) for p in param_names]
    pw_combos = list(AllPairs(factor_lists))
    return [
        {param_names[i]: combo[i] for i in range(len(param_names))}
        for combo in pw_combos
    ]


def generate_ota(param_names):
    """One-at-a-time: baseline + one variation per non-default factor."""
    factor_lists = {p: list(PARAMETERS[p].keys()) for p in param_names}
    baseline = {p: factor_lists[p][0] for p in param_names}
    combos = [dict(baseline)]
    for p in param_names:
        for i in range(1, len(factor_lists[p])):
            combo = dict(baseline)
            combo[p] = factor_lists[p][i]
            combos.append(combo)
    return combos


def generate_profile_cases():
    """Generate ~500 dense cases across 10 taxpayer profiles."""
    all_cases = []
    for profile_name, profile_def in PROFILES.items():
        fixed = profile_def["fixed"]
        vary_params = profile_def["vary"]

        defaults = {}
        for p in PARAM_ORDER:
            if p not in fixed and p not in vary_params:
                defaults[p] = list(PARAMETERS[p].keys())[0]

        base_combo = {**defaults, **fixed}

        factor_lists = [list(PARAMETERS[p].keys()) for p in vary_params]
        pw_combos = list(AllPairs(factor_lists))

        for pw_combo in pw_combos:
            combo = dict(base_combo)
            for i, p in enumerate(vary_params):
                combo[p] = pw_combo[i]
            all_cases.append((profile_name, combo))

        print(f"  {profile_name}: {len(pw_combos)} cases "
              f"(varied: {len(vary_params)} params, "
              f"max factors: {max(len(f) for f in factor_lists)})")

    return all_cases


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_factor_summary():
    print("\nFactor count per parameter:")
    total_full = 1
    for p in PARAM_ORDER:
        n = len(PARAMETERS[p])
        total_full *= n
        print(f"  {p}: {n} factors")
    print(f"\n  Full factorial: {total_full:,} cases")
    print()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "profiles"
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")

    print_factor_summary()

    if mode == "pairwise":
        print(f"Generating pairwise cases across all {len(PARAM_ORDER)} parameters...")
        combos = generate_pairwise(PARAM_ORDER)
        cases = []
        for i, combo in enumerate(combos):
            cases.append((f"pairwise", combo))
        label = "pairwise"

    elif mode == "ota":
        print(f"Generating OTA cases across all {len(PARAM_ORDER)} parameters...")
        combos = generate_ota(PARAM_ORDER)
        cases = []
        for combo in combos:
            cases.append(("ota", combo))
        label = "ota"

    elif mode == "profiles":
        print("Generating profile-based cases (~500 dense cases)...")
        cases = generate_profile_cases()
        label = "profiles"

    else:
        print(f"Unknown mode: {mode}. Use 'pairwise', 'ota', or 'profiles'.")
        sys.exit(1)

    print(f"\nTotal cases to generate: {len(cases)}")

    os.makedirs(out_dir, exist_ok=True)

    # Clear old files in the output directory
    for f in os.listdir(out_dir):
        if f.endswith(".json"):
            os.remove(os.path.join(out_dir, f))

    successes = 0
    failures = 0

    for idx, (profile, combo) in enumerate(cases, 1):
        try:
            case = build_case(combo, profile)
            filename = f"input_{idx:04d}.json"
            filepath = os.path.join(out_dir, filename)

            with open(filepath, "w") as f:
                json.dump(case, f, indent=2)

            successes += 1
            if idx % 50 == 0 or idx == len(cases):
                print(f"  Generated {idx}/{len(cases)} cases...")

        except Exception as e:
            failures += 1
            desc = "|".join(f"{p}={combo[p]}" for p in PARAM_ORDER if p in combo)
            print(f"  FAILED case {idx}: {e}")
            print(f"    combo: {desc[:120]}")

    print(f"\nDone. {successes} cases written to {out_dir}/")
    if failures:
        print(f"  {failures} cases failed.")


if __name__ == "__main__":
    main()
