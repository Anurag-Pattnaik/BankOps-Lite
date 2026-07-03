# =============================================================================
# FILE: pipeline/2_governance_engine.py
#
# PURPOSE:
#   The Data Governance Engine is the most critical step in any Data Migration
#   project. Raw legacy data is almost never ready for analysis. This script:
#     1. Profiles the raw data (counts nulls, duplicates, anomalies)
#     2. Applies validation rules to flag bad records
#     3. Cleans/remediates what can be fixed
#     4. Rejects what cannot be fixed
#     5. Writes a detailed Audit Log (who cleaned what, when, how many rejected)
#     6. Loads clean data into our SQLite Data Warehouse
#
# INTERVIEW ANSWER — "What is Data Governance?":
#   "Data Governance is the set of policies, processes, and rules that ensure
#    data is accurate, consistent, complete, and compliant before it is used
#    for reporting or machine learning. In this project I implemented it as a
#    Python validation pipeline with an audit log — similar to what tools like
#    Azure Data Factory or AWS Glue provide in cloud-native pipelines."
#
# OUTPUT:
#   bank_ops.db  — SQLite database with clean Dim_Customer, Dim_Date,
#                  Fact_Transactions tables
#   logs/governance_audit.txt — Human-readable audit report
# =============================================================================

import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
RAW_DIR    = os.path.join(BASE_DIR, "raw_data")
LOG_DIR    = os.path.join(BASE_DIR, "logs")
DB_PATH    = os.path.join(BASE_DIR, "bank_ops.db")
os.makedirs(LOG_DIR, exist_ok=True)

print("=" * 60)
print("  BankOps-Lite | Step 2: Data Governance Engine")
print("=" * 60)

# ── Audit Log Setup ───────────────────────────────────────────────────────────
# INTERVIEW: "An audit log is non-negotiable in enterprise data pipelines.
#             Regulators (RBI in India, SEC in USA) require you to prove
#             exactly which records were rejected and why."
audit_lines = []
audit_lines.append(f"BankOps-Lite | Data Governance Audit Report")
audit_lines.append(f"Run Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
audit_lines.append("=" * 60)

def log(msg):
    """Writes to both console and audit log simultaneously."""
    print(msg)
    audit_lines.append(msg)

# =============================================================================
# SECTION 1: Load Raw Data
# =============================================================================
log("\n[PHASE 1] Loading raw legacy CSV exports...")
raw_customers = pd.read_csv(os.path.join(RAW_DIR, "raw_customers.csv"))
raw_tx        = pd.read_csv(os.path.join(RAW_DIR, "raw_transactions.csv"))

log(f"  Raw customers loaded : {len(raw_customers):,} rows")
log(f"  Raw transactions loaded : {len(raw_tx):,} rows")

# =============================================================================
# SECTION 2: Data Profiling
# INTERVIEW: "Before cleaning, you profile the data to understand its quality
#             baseline. This is the equivalent of an initial assessment a
#             consultant does before writing a remediation plan."
# =============================================================================
log("\n[PHASE 2] Data Profiling (Quality Assessment)...")

cust_nulls = raw_customers.isnull().sum().sum() + (raw_customers == "").sum().sum()
tx_nulls   = raw_tx.isnull().sum().sum() + (raw_tx == "").sum().sum()
cust_dupes = raw_customers.duplicated().sum()
tx_dupes   = raw_tx.duplicated().sum()

log(f"  Customers — Null/empty fields : {cust_nulls}")
log(f"  Customers — Duplicate rows    : {cust_dupes}")
log(f"  Transactions — Null fields    : {tx_nulls}")
log(f"  Transactions — Duplicate rows : {tx_dupes}")

# =============================================================================
# SECTION 3: Clean Customer Records
# =============================================================================
log("\n[PHASE 3] Cleaning Customer Records...")

original_cust_count = len(raw_customers)
clean_customers      = raw_customers.copy()

# Rule C1: Remove exact duplicate rows
# INTERVIEW: "Duplicate rows happen in legacy systems when a network timeout
#             causes the application to retry the same DB INSERT twice."
before = len(clean_customers)
clean_customers = clean_customers.drop_duplicates()
log(f"  [C1] Removed exact duplicate customers     : {before - len(clean_customers)}")

# Rule C2: Reject rows with invalid age (<18 or >100)
before = len(clean_customers)
clean_customers = clean_customers[
    clean_customers["age"].between(18, 100, inclusive="both")
]
log(f"  [C2] Rejected customers with invalid age   : {before - len(clean_customers)}")

# Rule C3: Fill missing city with "Unknown" (soft remediation, not rejection)
# INTERVIEW: "We don't always reject on missing optional fields. We apply a
#             'soft remediation' — filling with a standard Unknown placeholder
#             so the record can still be used in analysis."
missing_city = clean_customers["city"].isna() | (clean_customers["city"] == "")
clean_customers.loc[missing_city, "city"] = "Unknown"
log(f"  [C3] Filled missing city with 'Unknown'    : {missing_city.sum()}")

# Rule C4: Ensure credit score is within valid CIBIL range (300–900)
before = len(clean_customers)
clean_customers = clean_customers[
    clean_customers["credit_score"].between(300, 900)
]
log(f"  [C4] Rejected customers with invalid score : {before - len(clean_customers)}")

# ── Customer Summary ──────────────────────────────────────────────────────────
rejected_customers = original_cust_count - len(clean_customers)
pass_rate_cust     = (len(clean_customers) / original_cust_count) * 100
log(f"\n  Customer Governance Result:")
log(f"    Input  : {original_cust_count:,} rows")
log(f"    Output : {len(clean_customers):,} rows  ({pass_rate_cust:.1f}% pass rate)")
log(f"    Rejected: {rejected_customers:,} rows")

# =============================================================================
# SECTION 4: Clean Transaction Records
# =============================================================================
log("\n[PHASE 4] Cleaning Transaction Records...")

original_tx_count = len(raw_tx)
clean_tx           = raw_tx.copy()

# Rule T1: Remove exact duplicate rows
before = len(clean_tx)
clean_tx = clean_tx.drop_duplicates()
log(f"  [T1] Removed exact duplicate transactions  : {before - len(clean_tx)}")

# Rule T2: Reject rows where amount is NULL (cannot process without amount)
before = len(clean_tx)
clean_tx = clean_tx.dropna(subset=["amount"])
log(f"  [T2] Rejected NULL amount transactions     : {before - len(clean_tx)}")

# Rule T3: Reject rows where amount <= 0 (impossible transaction)
before = len(clean_tx)
clean_tx = clean_tx[clean_tx["amount"] > 0]
log(f"  [T3] Rejected zero/negative amounts        : {before - len(clean_tx)}")

# Rule T4: Reject rows with malformed dates
# Valid format: YYYY-MM-DD, any other string is rejected
def is_valid_date(date_str):
    """Returns True if date_str matches YYYY-MM-DD and is a real calendar date."""
    try:
        datetime.strptime(str(date_str), "%Y-%m-%d")
        return True
    except ValueError:
        return False

before = len(clean_tx)
clean_tx = clean_tx[clean_tx["transaction_date"].apply(is_valid_date)]
log(f"  [T4] Rejected malformed date transactions  : {before - len(clean_tx)}")

# Rule T5: Remove orphaned transactions (customer_id not in clean customer list)
# INTERVIEW: "Referential integrity — every transaction MUST belong to a known
#             customer. Orphaned records cause incorrect aggregations."
valid_cust_ids = set(clean_customers["customer_id"])
before = len(clean_tx)
clean_tx = clean_tx[clean_tx["customer_id"].isin(valid_cust_ids)]
log(f"  [T5] Removed orphaned transactions         : {before - len(clean_tx)}")

# ── Transaction Summary ───────────────────────────────────────────────────────
rejected_tx    = original_tx_count - len(clean_tx)
pass_rate_tx   = (len(clean_tx) / original_tx_count) * 100
log(f"\n  Transaction Governance Result:")
log(f"    Input   : {original_tx_count:,} rows")
log(f"    Output  : {len(clean_tx):,} rows  ({pass_rate_tx:.1f}% pass rate)")
log(f"    Rejected: {rejected_tx:,} rows")

# =============================================================================
# SECTION 5: Build SQLite Data Warehouse (Star Schema)
# INTERVIEW: "A Star Schema organizes data into Dimension tables (descriptive
#             context: who, when, where) and Fact tables (measurable events:
#             what happened, how much). It is optimized for analytical queries
#             because you can JOIN on integer keys instead of large text fields."
# =============================================================================
log("\n[PHASE 5] Loading clean data into SQLite Data Warehouse (Star Schema)...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ── Drop and recreate tables (idempotent pipeline) ─────────────────────────────
# INTERVIEW: "Idempotent means running the script twice gives the same result
#             as running it once. This is critical for pipeline reliability."
cursor.executescript("""
    DROP TABLE IF EXISTS Fact_Transactions;
    DROP TABLE IF EXISTS Dim_Customer;
    DROP TABLE IF EXISTS Dim_Date;
    DROP TABLE IF EXISTS Governance_Audit;
""")

# ── Dim_Customer: Descriptive attributes of each customer ─────────────────────
cursor.execute("""
    CREATE TABLE Dim_Customer (
        customer_id      TEXT PRIMARY KEY,
        name             TEXT NOT NULL,
        age              INTEGER,
        city             TEXT,
        account_type     TEXT,
        account_age_days INTEGER,
        credit_score     INTEGER,
        branch_id        TEXT
    )
""")

# ── Dim_Date: Date breakdown dimension (enables time-based analysis) ───────────
# INTERVIEW: "A Date Dimension lets us quickly query transactions by month,
#             quarter, or day-of-week without parsing strings each time."
cursor.execute("""
    CREATE TABLE Dim_Date (
        date_id    TEXT PRIMARY KEY,
        full_date  TEXT,
        day        INTEGER,
        month      INTEGER,
        month_name TEXT,
        quarter    INTEGER,
        year       INTEGER,
        day_of_week TEXT
    )
""")

# ── Fact_Transactions: The measurable business events ─────────────────────────
cursor.execute("""
    CREATE TABLE Fact_Transactions (
        transaction_id   TEXT PRIMARY KEY,
        customer_id      TEXT REFERENCES Dim_Customer(customer_id),
        date_id          TEXT REFERENCES Dim_Date(date_id),
        transaction_type TEXT,
        amount           REAL,
        branch_id        TEXT,
        fraud_label      INTEGER DEFAULT 0,
        fraud_predicted  INTEGER DEFAULT -1
    )
""")

# ── Governance_Audit: Stores run-level data quality metrics ───────────────────
cursor.execute("""
    CREATE TABLE Governance_Audit (
        run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_timestamp   TEXT,
        raw_customers   INTEGER,
        clean_customers INTEGER,
        raw_transactions INTEGER,
        clean_transactions INTEGER,
        cust_pass_rate  REAL,
        tx_pass_rate    REAL
    )
""")

# ── Insert Dim_Customer ────────────────────────────────────────────────────────
clean_customers.to_sql("Dim_Customer", conn, if_exists="append", index=False)
log(f"  [OK] Dim_Customer   -> {len(clean_customers):,} rows inserted")

# ── Build and Insert Dim_Date ──────────────────────────────────────────────────
all_dates  = pd.to_datetime(clean_tx["transaction_date"]).dt.date.unique()
month_map  = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
              7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}

date_rows = []
for d in all_dates:
    dt = datetime.combine(d, datetime.min.time())
    date_rows.append({
        "date_id":    d.strftime("%Y-%m-%d"),
        "full_date":  d.strftime("%Y-%m-%d"),
        "day":        d.day,
        "month":      d.month,
        "month_name": month_map[d.month],
        "quarter":    (d.month - 1) // 3 + 1,
        "year":       d.year,
        "day_of_week": dt.strftime("%A")
    })

dim_date_df = pd.DataFrame(date_rows)
dim_date_df.to_sql("Dim_Date", conn, if_exists="append", index=False)
log(f"  [OK] Dim_Date       -> {len(dim_date_df):,} unique dates inserted")

# ── Insert Fact_Transactions ───────────────────────────────────────────────────
# Rename transaction_date -> date_id for FK reference
fact_df = clean_tx.rename(columns={"transaction_date": "date_id"}).copy()
# fraud_predicted starts as -1 (will be updated by Step 3 ML script)
fact_df["fraud_predicted"] = -1
fact_df[["transaction_id","customer_id","date_id","transaction_type",
         "amount","branch_id","fraud_label","fraud_predicted"]].to_sql(
    "Fact_Transactions", conn, if_exists="append", index=False
)
log(f"  [OK] Fact_Transactions -> {len(fact_df):,} rows inserted")

# ── Insert Audit Record ────────────────────────────────────────────────────────
cursor.execute("""
    INSERT INTO Governance_Audit
    (run_timestamp, raw_customers, clean_customers,
     raw_transactions, clean_transactions, cust_pass_rate, tx_pass_rate)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    original_cust_count,
    len(clean_customers),
    original_tx_count,
    len(clean_tx),
    round(pass_rate_cust, 2),
    round(pass_rate_tx, 2)
))

conn.commit()
conn.close()

# =============================================================================
# SECTION 6: Save Audit Log to File
# =============================================================================
audit_path = os.path.join(LOG_DIR, "governance_audit.txt")
with open(audit_path, "w") as f:
    f.write("\n".join(audit_lines))

log(f"\n  Audit log saved -> {audit_path}")
log("\n[DONE] Data Governance Engine complete.")
log(f"       -> SQLite DB ready at: {DB_PATH}")
log("\nNext Step: Run pipeline/3_fraud_detector.py")
