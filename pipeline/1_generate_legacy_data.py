# =============================================================================
# FILE: pipeline/1_generate_legacy_data.py
#
# PURPOSE:
#   Simulates a legacy bank core-system's raw data export.
#   In a real consulting engagement, this is the data you receive from a
#   client's on-premise RDBMS (Oracle, MS SQL Server) as a CSV dump.
#   Since we cannot use real production banking data (due to GDPR, PCI-DSS
#   compliance), we generate a synthetic dataset that mirrors real-world
#   banking patterns — including deliberate data quality issues (dirty data)
#   that our governance engine will clean in the next step.
#
# INTERVIEW ANSWER — "Where does the data come from?":
#   "I engineered a synthetic banking dataset that mirrors a legacy core-
#    banking system export. Real customer data cannot be used for PoC/dev
#    work under PCI-DSS and GDPR. The generator introduces realistic dirty-
#    data patterns (nulls, duplicates, format errors) identical to what you
#    find in actual legacy system migrations."
#
# OUTPUT:
#   raw_data/raw_transactions.csv  — Raw, dirty transaction records
#   raw_data/raw_customers.csv     — Raw customer profiles
# =============================================================================

import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

# Fix random seed so results are reproducible every run
# INTERVIEW: "Reproducibility is critical in data pipelines — same seed = same
#             output every time, which allows debugging and auditing."
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ── Configuration ────────────────────────────────────────────────────────────
NUM_CUSTOMERS    = 500    # Number of unique bank customers
NUM_TRANSACTIONS = 5000   # Total transaction records
FRAUD_RATE       = 0.08   # 8% of transactions are fraudulent (realistic banking figure)
OUTPUT_DIR       = os.path.join(os.path.dirname(__file__), "..", "raw_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Reference Data ───────────────────────────────────────────────────────────
CITIES        = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad",
                 "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow"]
BRANCHES      = ["MU-001", "DL-002", "BLR-003", "CHN-004", "HYD-005",
                 "PUN-006", "KOL-007", "AHM-008", "JAI-009", "LKN-010"]
ACCOUNT_TYPES = ["Savings", "Current", "Loan"]
TX_TYPES      = ["Deposit", "Withdrawal", "Transfer", "Bill Payment"]

# ── First & Last name pools (Indian names for realism) ───────────────────────
FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh",
               "Ayaan", "Atharva", "Krishna", "Ishaan", "Ananya", "Diya",
               "Saanvi", "Priya", "Kavya", "Shreya", "Aisha", "Meera",
               "Riya", "Pooja", "Rahul", "Rohan", "Siddharth", "Karan"]
LAST_NAMES  = ["Sharma", "Verma", "Patel", "Singh", "Kumar", "Mehta",
               "Joshi", "Gupta", "Nair", "Reddy", "Rao", "Shah",
               "Bose", "Iyer", "Kapoor", "Malhotra", "Saxena", "Tiwari"]

# =============================================================================
# STEP 1: Generate Customer Master Records
# =============================================================================
print("=" * 60)
print("  BankOps-Lite | Step 1: Generating Legacy Data")
print("=" * 60)

print("\n[1/3] Generating customer master records...")
customers = []
for i in range(1, NUM_CUSTOMERS + 1):
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    name  = f"{first} {last}"

    # account_age_days: how long the customer has had their account
    # New accounts (<30 days) are a major fraud risk signal
    account_age_days = int(np.random.exponential(scale=600))  # Most accounts are older
    account_age_days = max(1, min(account_age_days, 3650))    # Cap between 1 day and 10 years

    customers.append({
        "customer_id":      f"CUST{i:04d}",
        "name":             name,
        "age":              random.randint(21, 65),
        "city":             random.choice(CITIES),
        "account_type":     random.choice(ACCOUNT_TYPES),
        "account_age_days": account_age_days,
        # Credit score: 300–900 scale (like CIBIL in India)
        # INTERVIEW: "CIBIL scores are India's equivalent of FICO scores in the US.
        #             Low scores (<600) often correlate with high-risk behavior."
        "credit_score":     random.randint(300, 900),
        "branch_id":        random.choice(BRANCHES),
    })

customers_df = pd.DataFrame(customers)

# ── Introduce Dirty Data in Customers ───────────────────────────────────────
# INTERVIEW: "Dirty data in legacy systems is very common. Here I simulate
#             3 types of real-world quality issues."

# Issue 1: 5% of customers have missing city (NULL-like empty string)
null_city_idx = customers_df.sample(frac=0.05, random_state=1).index
customers_df.loc[null_city_idx, "city"] = ""

# Issue 2: 3% of customers have invalid age (e.g., -1 or 999 from bad RDBMS inserts)
bad_age_idx = customers_df.sample(frac=0.03, random_state=2).index
customers_df.loc[bad_age_idx, "age"] = random.choice([-1, 0, 999])

# Issue 3: Duplicate 2% of customer rows (system re-inserts on retry)
dupes = customers_df.sample(frac=0.02, random_state=3)
customers_df = pd.concat([customers_df, dupes], ignore_index=True)

print(f"    Generated {len(customers_df)} customer records "
      f"(including {len(dupes)} duplicates, nulls, bad ages)")

# =============================================================================
# STEP 2: Generate Transaction Records
# =============================================================================
print("\n[2/3] Generating transaction records...")

# Date range: last 12 months of transactions
END_DATE   = datetime(2024, 6, 30)
START_DATE = datetime(2023, 7, 1)
date_range = (END_DATE - START_DATE).days

# Customer IDs (from clean, deduplicated set for FK integrity)
valid_customer_ids = [c["customer_id"] for c in customers[:NUM_CUSTOMERS]]

transactions = []
used_tx_ids  = set()   # To detect duplicates later

for i in range(NUM_TRANSACTIONS):
    tx_date       = START_DATE + timedelta(days=random.randint(0, date_range))
    customer_id   = random.choice(valid_customer_ids)
    tx_type       = random.choice(TX_TYPES)
    branch        = random.choice(BRANCHES)

    # Amount distribution: Most transactions are small (log-normal distribution
    # matches real-world transaction patterns: many small, few large)
    amount = round(np.random.lognormal(mean=8.5, sigma=1.2), 2)
    amount = max(10.0, min(amount, 500000.0))

    # Generate a unique transaction ID
    tx_id = f"TXN{i+1:06d}"
    used_tx_ids.add(tx_id)

    # ── Fraud Label Generation ────────────────────────────────────────────────
    # INTERVIEW: "I designed fraud labels using domain-known risk rules that
    #             approximate real banking fraud detection heuristics. This
    #             gives the ML model meaningful signal to learn from."
    #
    # Fraud is TRUE when ANY of these risk conditions combine:
    # Rule 1: Very high amount (>150,000) AND customer account is new (<60 days)
    # Rule 2: Transaction amount > 200,000 (large outlier regardless of age)
    # Rule 3: Withdrawal from a Loan account (unusual, policy violation)
    # Baseline: 3% random fraud to represent unseen patterns
    #
    # Get this customer's account age for the fraud rule
    cust_data = next((c for c in customers if c["customer_id"] == customer_id), None)
    acct_age  = cust_data["account_age_days"] if cust_data else 365

    rule1 = (amount > 150000 and acct_age < 60)
    rule2 = (amount > 200000)
    rule3 = (tx_type == "Withdrawal" and
             cust_data and cust_data["account_type"] == "Loan")
    baseline_fraud = (random.random() < 0.03)

    is_fraud = int(rule1 or rule2 or rule3 or baseline_fraud)

    transactions.append({
        "transaction_id":   tx_id,
        "customer_id":      customer_id,
        "transaction_date": tx_date.strftime("%Y-%m-%d"),
        "transaction_type": tx_type,
        "amount":           amount,
        "branch_id":        branch,
        "fraud_label":      is_fraud,   # Ground truth label for ML training
    })

transactions_df = pd.DataFrame(transactions)

# ── Introduce Dirty Data in Transactions ─────────────────────────────────────
# Issue 1: 4% of transactions have missing amount (NULL)
null_amt_idx = transactions_df.sample(frac=0.04, random_state=4).index
transactions_df.loc[null_amt_idx, "amount"] = None

# Issue 2: 3% have malformed date strings (legacy system date format bug)
bad_date_idx = transactions_df.sample(frac=0.03, random_state=5).index
transactions_df.loc[bad_date_idx, "transaction_date"] = "00/00/0000"

# Issue 3: Duplicate 2% of transactions (network retry duplicates)
dupes_tx = transactions_df.sample(frac=0.02, random_state=6)
transactions_df = pd.concat([transactions_df, dupes_tx], ignore_index=True)

print(f"    Generated {len(transactions_df)} transaction records "
      f"(including duplicates, nulls, bad dates)")
print(f"    Fraud transactions: {transactions_df['fraud_label'].sum()} "
      f"({transactions_df['fraud_label'].mean()*100:.1f}%)")

# =============================================================================
# STEP 3: Save Raw CSVs (Legacy Export Simulation)
# =============================================================================
print("\n[3/3] Saving raw legacy CSV files...")

cust_path = os.path.join(OUTPUT_DIR, "raw_customers.csv")
tx_path   = os.path.join(OUTPUT_DIR, "raw_transactions.csv")

customers_df.to_csv(cust_path, index=False)
transactions_df.to_csv(tx_path, index=False)

print(f"    Saved: {cust_path}")
print(f"    Saved: {tx_path}")

print("\n[DONE] Legacy data generation complete.")
print(f"       -> {len(customers_df)} customer rows (with dirty data)")
print(f"       -> {len(transactions_df)} transaction rows (with dirty data)")
print("\nNext Step: Run pipeline/2_governance_engine.py")
