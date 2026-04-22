These are sections of the income tax calculator as shown in the [https://eportal.incometax.gov.in/iec/foservices//dashboard/estimator](https://eportal.incometax.gov.in/iec/foservices/#/dashboard/estimator) 

Parameters about person in model: 

1. Age of employee: (three buckets) 60, 60-80, 80
2. Type of employment: Private, government

Design  

1. Section as per image
  1. Meaning
  2. Limit
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. 1
  4. Source of information

Modes of payment wherever applicable 

1. Cash
2. Cheque
3. UPI
4. credit card
5. net banking

Under head: Salaries: 

1. Gross salary 
  1. Meaning: net cost to company (CTC), both monetary and non-monetary
    CTC (Cost to Company) is the total amount your employer spends on you.   
     It includes components like your gross salary, employer's provident fund (EPF) contributions, gratuity, bonuses, and other benefits like health insurance, food coupons, etc
  2. Limit: None
  3. Parameters in data model:
    1. Fixed Components
      These components remain constant every month unless revised by the employer:
      1. Basic Salary – The core salary component and the basis for other salary calculations.
      2. Dearness Allowance (DA) – Given to government employees and PSU workers to offset inflation.
      3. House Rent Allowance (HRA) – Provided for rental expenses; can be claimed for tax exemption.
      4. Conveyance Allowance – Given to cover transportation costs for commuting.
      5. Medical Allowance – Fixed medical reimbursement for healthcare expenses.
    2. Variable Components
      These components may change based on performance, company policies, or external factors:
      1. Bonuses and Incentives – Performance-based extra pay.
      2. Overtime Pay – Paid for extra hours worked beyond standard working hours.
      3. Leave Travel Allowance (LTA) – Covers travel expenses during leave, subject to tax exemptions.
      4. Special Allowance – Additional payments made by employers for various purposes.
  4. Source of information: Parameters: [https://www.5paisa.com/stock-market-guide/tax/gross-salary](https://www.5paisa.com/stock-market-guide/tax/gross-salary)
    Definition: [https://cleartax.in/s/gross-salary-ctc](https://cleartax.in/s/gross-salary-ctc)
2. Section 10: (**ONLY UNDER OLD REGIME  the ones mentioned here)**
  1. Meaning
  2. Limit  different for each parameter 
  3. Parameters in data model:
    1. Exemption on (HRA) House Rent Allowance  Section 10(13A)
      least of the following amounts:
      1. Actual HRA received
      2. 50% of basic salary  DA for those living in Delhi, Mumbai, Chennai, Kolkata or
      3. 40% of basic salary  DA for those living in other cities
      4. Actual rent paid (-) 10% of basic salary  DA
    2. Leave Travel Allowance Exemption  Section 10(5) [source](https://cleartax.in/s/lta-leave-travel-allowance)
      Section 10(5), or leave travel allowance exemption, is applicable for individual taxpayers. The **LTA exemption applies only to the domestic travel expenses, such as airfare, train or bus fare,** incurred by the employee. Other expenses, such as transportation within the destination, sightseeing, hotels, and food, are not covered. Additionally, the exemption is limited to LTA provided in your CTC by the employer.
      1. Exemption **can be claimed for 2 out of 4 block years**. The current block year is 2022-25.
      2. limit can be summarized as the lower of the following:
        1. Amount provided by the employer as leave travel concession
          1. Expenses can be claimed for self and family. Family includes the following:
            1. Spouse
            2. Children  upto 2
            3. Dependent siblings and parents.
        2. Fare of economy class of flight, 1st class A/C rail fare, 1st Class Deluxe bus fare, as applicable.
      3. For example, if an employee is given LTA of Rs 30,000 and incurs travel expenses of Rs 20,000, only the amount actually spent on travel would be exempt from taxes and the remaining Rs 10,000 would be included as taxable income.
  4. Source of information:
    1. [https://cleartax.in/s/section-10-of-income-tax-act](https://cleartax.in/s/section-10-of-income-tax-act)
    2. [https://cleartax.in/s/special-allowance-india](https://cleartax.in/s/special-allowance-india)
3. (Deduction under) Section 16(ia):
  1. Meaning: standard deduction without proofs
  2. Limit:
    1. Old regime: 50k or gross income whichever lower
    2. New regime: 75k or gross income whichever lower
  3. Parameters in data model: None  fixed in calculator
  4. Source of information: [https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html](https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html)
4. (Deduction under) Section 16(ii): Entertainment allowance
  1. Meaning: available to **government employees only**
  2. Limit: Lower of the following (doesn’t consider actual entertainment expense)
    1. ₹5,000
    2. 20% of basic salary
    3. Total amount received as entertainment allowance in a financial year
  3. Parameters in data model: just consider if government employee
  4. Source of information: [https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html](https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html)
5. (Deduction under) Section 16(iii): Professional tax
  1. Meaning: A certain state level tax levied from salaried people that can be deducted from the gross income
  2. Limit: max 2,500
  3. Parameters in data model:
    1. Only some states levy it :- list of the states (but we can ignore this for now)
  4. Source of information: [https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html](https://www.tataaia.com/blogs/tax-savings/the-detailed-guide-on-section-16-of-the-income-tax-act.html)

[https://www.perplexity.ai/search/in-the-income-tax-filing-porta-scixpKFaRcyQQ9uxqJlIgg](https://www.perplexity.ai/search/in-the-income-tax-filing-porta-scixpKFaRcyQQ9uxqJlIgg)  taxliability won’t differ if we enter all the gains into 1 quarter

1. Short Term Capital Gains (other than covered under section 111A)
  1. Meaning: categories other than equity and equity oriented MF
  2. Limit: (no tax on privately owned vehicles), taxed at slab rate
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. Type: (any one of these)
      1. Privately owned Vehicles
      2. Bonds
      3. Debentures
      4. G‑Secs
      5. Debt / hybrid‑debt MFs
    2. Amount:
  4. Source of information:
2. Short Term Capital Gains (under section 111A)
  1. Meaning: for stocks, equity oriented Mutual funds, units of business trust
    1. Short term determined by example:
      If you buy shares on April 4, 2025, the holding period starts that day. STCG applies to sales up to and including April 3, 2026 (exactly 12 months later); any sale on or after April 4, 2026, qualifies as long-term capital gains (LTCG)
    2. Applicable only to:
      1. Listen Equity shared
      2. Equity oriented MFs
  2. Limit: taxed at 20%
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. Same as Section 112A
  4. Source of information: [https://cleartax.in/s/short-term-capital-gain-on-shares](https://cleartax.in/s/short-term-capital-gain-on-shares)
3. Long Term Capital Gains (other than covered under section 112 @ 12.5%
  1. Meaning: multiple headers
  2. Limit: no limit
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. Bonds
    2. Debentures
    3. G‑Secs
    4. Debt / hybrid‑debt MFs  and other Mfs see below
  4. Source of information: [https://www.perplexity.ai/search/misc-ltcg-and-stcg-rates-and-c-IH8acksiTjCyJa8CRRpDVg](https://www.perplexity.ai/search/misc-ltcg-and-stcg-rates-and-c-IH8acksiTjCyJa8CRRpDVg)
4. Long Term Capital Gains (other than covered under section 112 @ 20%
  1. Meaning
  2. Limit
  3. Parameters to adjust in model: (with caveats for each parameter)
  4. Source of information
5. Long Term Capital Gains (under section 112A)
  1. Meaning: for stocks, equity oriented Mutual funds, units of business trust
    1. The tax can be written off against the long term capital loss from upto 8 years back
    2. Grandfathering clause: The capital gains are only considered after 31/1/2018
      1. For cost of acquisition its higher of the two (cost price , FMV)
      2. For gains sale price brokerage/commission/other transfer costs (excluding STT) lower(cost of acquisition, sales price)
  2. Limit: taxed above 1.25L at 12.5%
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. Long term capital losses
      1. Financial year:
      2. Loss:
    2. Sale of long term stock:
      1. Sale price:
      2. Cost price:
      3. Quantity:
      4. Brokerage:
      5. Securities Transaction Tax:
      6. Purchase date:
      7. Sale date:
      8. FMV of stock as of 31/1/2018:
  4. Source of information: [https://cleartax.in/s/long-term-capital-gains-on-shares](https://cleartax.in/s/long-term-capital-gains-on-shares)



1. Interest from Saving’s bank account:
2. Interest from deposit (bank/postoffice/co operative Society):
3. Other interest income:
  1. Interest on securities:
  2. Interest other than ‘interest on security’
    1. PPF interest
4. Any other income:
  1. Commission, price etc on sale of lottery tickets
  2. Commission or brokerage:
  3. Other income

  
  
Deductions

1. 80CCE  **Older regime only**
  1. Meaning: **Combined limit for 80C, 80CCC & 80CCD(1)**
  2. Limit: **Rs 1,50,000**
2. 80C  **Applicable under Older Regime only**
  1. Meaning
  2. Limit: The **maximum deduction available under Section 80C is Rs. 1,50,000 per financial year**. This limit is applicable to the total combined amount invested across all eligible instruments and expenses.
  3. Parameters to adjust in model: (with caveats for each parameter)
    1. Public Provident Fund (PPF)
      1. Is EEE  3 exemptions  EEE (Exempt–Exempt–Exempt) means that at all three stages—contribution, earnings, and withdrawal—the investment is fully tax‑exempt
      2. No tax on interest or contribution
    2. Employee Provident Fund (EPF) contributions
      1. Meaning: generally is
      2. Limit: If the employee’s contribution (from both components)
        1. For non-government employees: 2.5L
        2. For government employees: 5L
      3. Parameters to adjust in model: (with caveats for each parameter)
        1. Employee’s contribution:
          1. Deducted from salary
          2. Voluntary contribution
        2. Employer’s contribution
      4. Source of information: [https://cleartax.in/s/epf-interest-taxation-exceeding-2-5-lakh](https://cleartax.in/s/epf-interest-taxation-exceeding-2-5-lakh)
    3. Equity Linked Savings Scheme (ELSS) mutual funds  see under new mutual fund investments
    4. National Savings Certificate (NSC)
    5. Sukanya Samriddhi Yojana (SSY)
    6. Senior Citizen Savings Scheme (SCSS)
  4. Source of information:
    1. [Section 80C of Income Tax Act  80C Deduction List](https://cleartax.in/s/80c-80-deductions)
    2. [Tax Benefits on Children Education Allowance, Tuition Fees and School Fees](https://cleartax.in/s/tuition-fees-deduction-under-section-80c)(Both 80C deduction and exemption  u/s 10(14))
  5. Example: if a taxpayer invests:
    1. Rs. 60,000 in PPF
    2. Rs. 50,000 in ELSS
    3. Rs. 60,000 in life insurance premiums
      e total deduction allowed will be Rs. 1.5 lakh, which is the maximum allowed under Section 80C and not he actual Rs. 1.7 lakh invested.

3. 80CCC
  1. Meaning: exemption for investing in pension scheme
    1. The deductions are applicable for the premium/sum paid for the preceding Assessment Year only. For instance, **if an individual pays the sum for 2-3 years together, then a deduction can only be claimed for the amount that pertains to the preceding year**. The remaining deductions will be available in the respective year.
  2. Limit: 80C, 80 CCC, and 80 CCD(1)  all have combines limit of 1.5L  80 CCE
  3. Parameter to adjust in model:
    1. Premium amount paid for pension:
    2. Number of years paid for:
  4. Source of info:
    1. [https://cleartax.in/s/section-80ccc](https://cleartax.in/s/section-80ccc)
    2. [https://www.bajajfinserv.in/investments/section-80ccc-of-income-tax-act](https://www.bajajfinserv.in/investments/section-80ccc-of-income-tax-act)  for pension plan of insurance companies only
  5. Example: if 60,000 if premium paid for 3 years  then deductible amount  is only 20,000
4. 80CCD  tax deduction for contributions to National Pension Scheme ([example](https://www.perplexity.ai/search/what-is-limit-of-tier-1-accoun-RLcYFuk4ReeLLIzCW.0dmg#2))
  1. Parameters in model:
    1. Tier-1 account
      1. Self contribution
      2. Employer contribution
    2. Tier-2 account:
      (no tax exemption & amount can only be present if tier1 account contribution is nonzero)
  2. Source of information: [https://cleartax.in/s/section-80ccd](https://cleartax.in/s/section-80ccd)
  3. 80CCD(1):
    1. Meaning:
    2. Limit: combined with 80C and 80 CCC  1.5L
      **Lower of 10% of basic DA or 1.5L**
  4. 80CCD(1B):
    1. Meaning:
    2. Limit: 50k above if 80C+80CCC+80CCD(1) limit exceeds 1.5L
    3. Source of info:[https://cleartax.in/s/section-80-ccd-1b](https://cleartax.in/s/section-80-ccd-1b)
  5. 80CCD(2):
    1. Meaning: for employer’s contribution to NPS
    2. Limit: (seen in screenshot below)


| Regime | Government employer      | Other employer           |
| ------ | ------------------------ | ------------------------ |
| New    | 14% of salary (basic DA) | 14% of salary (basic DA) |
| Old    | 14% of salary (basic DA) | 10% of salary (basic DA) |


1. 80D 
  1. Meaning:
  2. Limit:
    1. Cash is only an accepted mode for preventive health checkup


| Policy for                                              | Deduction for Self & Family | Deduction for Parents | Preventive Health Check-up | Maximum Deduction |
| ------------------------------------------------------- | --------------------------- | --------------------- | -------------------------- | ----------------- |
| Self & Family (below 60 years)                          | 25,000                      |                       | 5,000                      | 25,000            |
| Self & Family Parents (all of them below 60 years)      | 25,000                      | 25,000                | 5,000                      | 50,000            |
| Self & Family (below 60 years) Parents (above 60 years) | 25,000                      | 50,000                | 5,000                      | 75,000            |
| Self & Family Parents (Both above 60 years)             | 50,000                      | 50,000                | 5,000                      | 1,00,000          |


1. 80G  Donations
  1. Meaning: donations to certain campaigns and causes
  2. Limit: some have 100% exemption, some have 50 % exemption  unconditional and conditional (conditional yet to be included based on adjusted total income)
    1. For cash and kind donations: above 2000 not exempt 
  3. Parameters in model(for now only use the ones listed below) different scheme names see here: [https://www.incometaxindia.gov.in/w/section-80g-56](https://www.incometaxindia.gov.in/w/section-80g-56)
    1. For each donation: format
      1. Scheme name:
        1. Donation amount:
        2. Donation mode: check modes of payment on top
    2. Schemes and their exemption amounts:
      1. 100% amount exempt:
        1. National defence fund
        2. PM Cares Fund
        3. National Sports Fund
        4. National Cultural Fund
      2. 50% amount exempt:
        1. Prime Minister’s Drought Relief Fund
  4. Source of info: [https://cleartax.in/s/donation-under-section-80g-and-80ggah6](https://cleartax.in/s/donation-under-section-80g-and-80gga#h6)
2. 80E:
  1. Meaning: interest paid on education loan(higher educationafter 12th) can be claimed here, up till 8 years of repayment
  2. Limit: No upper limit but max up till 8 years of repayment
  3. Parameter in model:
    1. Interest paid
    2. Year of repayment:
  4. Source of info: [https://cleartax.in/s/section-80e-deduction-interest-education-loan](https://cleartax.in/s/section-80e-deduction-interest-education-loan)
3. 80TTA
  1. Meaning: deduction of interest earned on Interest from account
  2. Limit: Lower of the (total interest income, 10,000)
    1. Applicable for:
      1. From a savings account with a bank
      2. From a savings account with a co-operative society carrying on the business of banking
      3. From a savings account with a post office
    2. Not applicable for:
      1. Interest from fixed deposits
      2. Interest from recurring deposits
      3. Interest  earned on corporate bonds and debentures.
      4. Interest from Provident fund deposits
      5. Interest from lending business
  3. Parameter in model:
    1. Interest in saving’s bank account
  4. Source of info: [https://cleartax.in/s/claiming-deduction-on-interest-under-section-80tta](https://cleartax.in/s/claiming-deduction-on-interest-under-section-80tta)
4. 80TTB
  1. Meaning: **special tax benefit available to senior citizens** (aged 60 years or above) that allows them to claim a deduction of up to Rs.50,000 on interest income earned
  2. Limit: Only for people **older than 60 Years**,  *lower(50,000, {interest income from relevant sources})*
  3. Applicable on
    1. Interest on bank deposits (savings or fixed)
    2. Interest on deposits held in a co-operative society engaged in the business of banking, including a co-operative land mortgage bank or a co-operative land development bank
    3. Interest on post office deposits
  4. Parameter in model:
  5. Source of info:
5. 80P
  1. Meaning:
  2. Limit:
  3. Parameter in model:
    1. A
  4. Source of info:

The sections below are automatically calculated by the income tax calculator: (notes just for understanding)  


1. Total tax before rebate:
2. Less: tax rebate under section 87A
  1. Meaning: under a certain income threshold(total taxable income) the tax is zeroed out:
    1. Older regime: under 5L income  so tax before rebate = 12500
    2. New Regime: under 12L income  so tax before rebate = 60000
  2. Limit: Doesn’t applied to income taxed under special brackets(LTCG, STCG, earning from lotteries, gameshows, etc)
  3. Marginal relief under new tax regime:
    1. Example:
      The income from special sources (LTCG & STCG) is 20,000  that has a separate tax of 4,000 that will be charged  
       If income from special sources is 20k, taxable income is 12,25,000  
        so as we can see the tax at normal rates is more than income above 12L itself(6375025000)  
       And so tax payable is (tax at normal rates+special tax) should be (25,000 4,000 )and thus the rebate under 87A is (67750-25000-4000)  28750
  4. Source of information: [https://cleartax.in/s/income-tax-rebate-us-87a](https://cleartax.in/s/income-tax-rebate-us-87a)
3. Surcharge:
  1. Meaning: for certain income thresholds 50L, the table below shows the same


| Total Taxable Income | Old Tax Regime Surcharge Rates | New Tax Regime Surcharge Rates |
| -------------------- | ------------------------------ | ------------------------------ |
| Up to 50L            | 0                              | 0                              |
| Above 50L up to 1Cr  | 10%                            | 10%                            |
| Above 1Cr up to 2Cr  | 15%                            | 15%                            |
| Above 2Cr up to 5Cr  | 25%                            | 25%                            |
| Above 5Cr            | 37%                            | 25% (capped)                   |


1. Health and Education Cess
  1. Meaning: on the sum of the surcharge  net tax after rebate, a 4% additional charge is applied
  2. Limit: 4% on tax  surcharge calculated up until that point
  3. Source of information: All types of cess explained: [https://cleartax.in/s/cess-on-income-tax](https://cleartax.in/s/cess-on-income-tax)

Contributions touching multiple sections:

1. EPF:
  1. Deduction under 80C mentioned above
  2. The ₹7.5 lakh combined employer contribution cap (Section 17  see perplexity thread  [here](https://www.perplexity.ai/search/section-10-11-of-income-tax-ac-w.rgprWvRsey70_DMXL9HA#4)
  3. How to Calculate the Taxable Portion of EPF interest?
    for calculating taxable interest, the PF department shall maintain separate accounts, one with taxable contribution and another with non-taxable contribution, for all the subscribers starting from the financial year 2021-22 and onwards.  
     The taxpayer shall be liable to pay tax on the interest accrued in the taxable contribution account. The EPFO shall deduct TDS on such interest.   
     Under what Circumstances will TDS on interest be deducted?  
     TDS will be deducted at **10% on taxable interest income accrued above the threshold limit** during the year as per Section 194A of the IT Act.   
     What is the Threshold Limit on Interest income above which TDS will be deducted?  
     For resident Indians, TDS is deductible if the **interest accrued in the PF account for the financial year exceeds Rs 5,000.** 
     Do Employees need to Pay tax if TDS is deducted?
     The employee **shall pay tax on the interest accrued on the taxable portion of the PF contribution. The amount of taxable PF interest should be added as income under the head ‘income from other sources’** on which tax shall be calculated as per the applicable income tax slab rates. The **employee can claim a tax credit for the TDS deducted from the interest income.**
  4. Source of info: [https://cleartax.in/s/epf-interest-taxation-exceeding-2-5-lakh](https://cleartax.in/s/epf-interest-taxation-exceeding-2-5-lakh)
2. Mutual Funds
  1. Meaning:
    1. There are different types of Mutual funds (based on diff parameters  for tax our parameter is the asset (equity/debt split) composition): [https://groww.in/p/types-of-mutual-funds](https://groww.in/p/types-of-mutual-funds)
  2. Limit:
    1. Equity oriented mutual funds:


| Category                                    | STCG (Short-Term)                | LTCG (Long-Term)                                           |
| ------------------------------------------- | -------------------------------- | ---------------------------------------------------------- |
| Equity Funds (≥65% equity)                  | 20% (flat)                       | 12.5% on gains above ₹1.25 lakh (no indexation)            |
| Hybrid Funds (Equity-oriented, ≥65% equity) | 20% (flat)                       | 12.5% on gains above ₹1.25 lakh (no indexation)            |
| Debt / Specified Funds (Post 1 Apr 2023     | Taxed at slab rates (any period) | No LTCG benefit – taxed at slab rates                      |
| Debt Funds (Pre-1 Apr 2023                  | ≤ 24 months: Taxed at slab rates | 24 months: 12.5% (no indexation)                           |
| ELSS Funds                                  | Not applicable (3-year lock-in)  | 36 months: 12.5% on gains above ₹1.25 lakh (no indexation) |
| Gold ETFs / Silver ETFs (Listed)            | ≤ 12 months: Taxed at slab rates | 12 months: 12.5% (no indexation)                           |
| Gold Mutual Funds / Gold FoFs               | ≤ 24 months: Taxed at slab rates | 24 months: 12.5% (no indexation)                           |
| International Funds / FoFs                  | ≤ 24 months: Taxed at slab rates | 24 months: 12.5% (no indexation)                           |


```
  2. Debt Oriented mutual funds:  
     1. (Indexation) Adjusted cost if bought before 1st April 2023 \= Original cost price \* (CII of current year/ CII of Year of purchase)  
          
```

1. Parameters in the model:     
  1. Mutual fund:
    1. Type: Equity/debt/ Hybrid-equity/ ELSS/ Gold ETFs / silver ETFs/ Gold Mutual Funds / Gold FoFs/ International Funds / FoFs
    2. Date of purchase:
    3. CII in year of purchase:
    4. Value at purchase:
    5. Values at sale:
2. Source of information:  
  1. [https://cleartax.in/s/different-mutual-funds-taxed](https://cleartax.in/s/different-mutual-funds-taxed)
  2. [https://www.perplexity.ai/search/mutual-funds-tax-12XvRQSMREKGNtmLhmwrGg2](https://www.perplexity.ai/search/mutual-funds-tax-12XvRQSMREKGNtmLhmwrGg#2)


| Fund Type                                   | STCG (Holding Threshold)                                                                                                                                  | LTCG (Holding Threshold)                                                                                                                  | Notes                                                               |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Equity Schemes**                          | 20%                                                                                                                                                       | 12.5% on gains ₹1.25 lakh (no indexation) [anandrathiwealth](https://www.anandrathiwealth.in/blog/income-tax-filing-for-mutual-funds.php) | Threshold: 1 year                                                   |
| **Debt Schemes**                            | Slab rates                                                                                                                                                | Slab rates (post Apr 2023); 12.5% pre-Apr 2023 if 2/3 years anandrathiwealth+1                                                            | No indexation post-2023; threshold 2-3 years pre-change             |
| **Hybrid Schemes**                          | Depends on equity %: Equity-like if ≥65%; else debt-like                                                                                                  | Same as above [gripinvest](https://www.gripinvest.in/blog/hybrid-mutual-funds-taxation)                                                   | E.g., aggressive hybrid (equity) vs conservative (debt)             |
| **Solution-Oriented (Retirement/Children)** | Follows underlying (often hybrid/equity); children's income clubbed with parent [angelone](https://www.angelone.in/mutual-funds/category/childrens-funds) | Same; ₹1,500 exemption/child/year [angelone](https://www.angelone.in/mutual-funds/category/childrens-funds)                               | 5-year lock-in common; ELSS variant for retirement has 80C benefits |
| **Other (Index/ETFs/FoFs)**                 | Equity-like if ≥65% equity/domestic; else debt-like [anandrathiwealth](https://www.anandrathiwealth.in/blog/income-tax-filing-for-mutual-funds.php)       | Same as equity/debt [anandrathiwealth](https://www.anandrathiwealth.in/blog/income-tax-filing-for-mutual-funds.php)                       | ETFs often equity; FoFs taxed per underlying                        |


