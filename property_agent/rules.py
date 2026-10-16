"""Singapore residential property policy parameters.

All numbers here are simplified planning assumptions, not legal or financial
advice. Government policy (IRAS, HDB, MAS, CPF) changes often -- verify every
figure against the official sources before quoting it to a client, and update
this file when cooling measures change.

Sources to check:
  - Stamp duties:   https://www.iras.gov.sg  (BSD / ABSD)
  - HDB / EC rules: https://www.hdb.gov.sg
  - Loan limits:    https://www.mas.gov.sg  (TDSR, MSR, LTV)
"""

POLICY_AS_OF = "2026-10"

# --- Buyer's Stamp Duty (residential), progressive tiers: (tier size, rate) ---
BSD_TIERS = [
    (180_000, 0.01),
    (180_000, 0.02),
    (640_000, 0.03),
    (500_000, 0.04),
    (1_500_000, 0.05),
    (float("inf"), 0.06),
]

# --- Additional Buyer's Stamp Duty, keyed by residency then property count
# after this purchase (1 = first property, 2 = second, 3 = third and beyond).
ABSD_RATES = {
    "SC": {1: 0.00, 2: 0.20, 3: 0.30},
    "PR": {1: 0.05, 2: 0.30, 3: 0.35},
    "FOREIGNER": {1: 0.60, 2: 0.60, 3: 0.60},
}

# --- Loan servicing limits ---
TDSR_LIMIT = 0.55            # Total Debt Servicing Ratio (all property purchases with bank loans)
MSR_LIMIT = 0.30             # Mortgage Servicing Ratio (HDB flats and new ECs from developers)
STRESS_RATE_BANK = 0.04      # Medium-term interest rate floor used for TDSR/MSR on bank loans
HDB_LOAN_RATE = 0.026        # HDB concessionary loan rate

# --- Loan-to-value limits by number of outstanding housing loans (incl. this one) ---
BANK_LTV = {1: 0.75, 2: 0.45, 3: 0.35}
BANK_MIN_CASH_PCT = {1: 0.05, 2: 0.25, 3: 0.25}
HDB_LOAN_LTV = 0.75
HDB_LOAN_MIN_CASH_PCT = 0.0
HDB_LOAN_INCOME_CEILING = 14_000   # household, family nucleus
HDB_LOAN_INCOME_CEILING_SINGLE = 7_000

MAX_TENURE_BANK_PRIVATE = 30
MAX_TENURE_BANK_HDB = 30
MAX_TENURE_HDB_LOAN = 25
LOAN_END_AGE = 65             # full LTV generally needs age + tenure <= 65

# --- Scheme rules ---
EC_INCOME_CEILING = 16_000
HDB_MOP_YEARS = 5             # Minimum Occupation Period for HDB flats and ECs
PRIVATE_TO_HDB_WAIT_MONTHS = 15
PRIVATE_TO_EC_WAIT_MONTHS = 30
HDB_SINGLE_MIN_AGE = 35

# --- Transaction cost assumptions ---
LEGAL_AND_MISC_FEES = 5_000
SELLING_COST_PCT = 0.02       # agent commission + legal on the sale of the current home
ASSUMED_MARKET_RATE = 0.028   # used for "expected monthly instalment" illustrations

# --- Indicative 2026 price bands (SGD). Replace with your own market data. ---
# entry   = cheapest realistic option in the segment
# typical = a mainstream family-sized unit
PRICE_BANDS = {
    "HDB_RESALE": {"entry": 450_000, "typical": 700_000,
                   "note": "3-room from ~$450k; 4-room ~$600k-$900k; 5-room ~$700k-$1.1M"},
    "EC_NEW_LAUNCH": {"entry": 1_300_000, "typical": 1_600_000,
                      "note": "~$1,700-$1,900 psf; 3BR ~$1.5M-$1.7M, 4BR ~$1.9M+"},
    "PRIVATE_RESALE": {"entry": 900_000, "typical": 1_500_000,
                       "note": "OCR 2-3BR ~$1.2M-$1.8M; older/smaller units from ~$900k"},
    "PRIVATE_NEW_LAUNCH": {"entry": 1_200_000, "typical": 1_900_000,
                           "note": "OCR ~$2,200-$2,500 psf; 2BR ~$1.4M, 3BR ~$2.0M+"},
    "LANDED": {"entry": 2_800_000, "typical": 4_000_000,
               "note": "Leasehold terrace from ~$2.8M; freehold terrace ~$3.5M-$5M; semi-D $5M+"},
}
