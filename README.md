# BankOps-Lite: Retail Banking Data Modernization & Fraud Intelligence Platform

> **A Technology Consulting Proof-of-Concept (PoC) simulating an ADMM engagement**  
> Simulates a real-world data pipeline for a retail bank: from dirty legacy exports to a governed data warehouse, ML-powered fraud detection, and an executive BI dashboard.

---

## Problem Statement

**Apex Bank** operates on a legacy core-banking system whose daily data exports suffer from missing fields, duplicate records, and inconsistent date formats. There is no reporting layer for management and no mechanism to detect fraudulent transactions automatically. This project delivers an end-to-end modernization PoC solving all three problems.

---

## What Skills This Project Teaches

| Component | Skill Demonstrated |
|---|---|
| `1_generate_legacy_data.py` | Python programming, Pandas, realistic data simulation |
| `2_governance_engine.py` | Data Governance, SQL schema design, SQLite Star Schema (DBMS) |
| `3_fraud_detector.py` | Machine Learning (scikit-learn Random Forest), feature engineering |
| `dashboard/app.py` | Python Flask REST API, SQL aggregation queries |
| `dashboard/templates/index.html` | HTML5, modern web design |
| `dashboard/static/js/charts.js` | Data Visualization (Chart.js, like Tableau/PowerBI logic) |

---

## Prerequisites

- Python 3.8 or higher
- No database server required (uses local SQLite file)
- Internet for initial `pip install` only

---

## Step-by-Step Setup & Run

### Step 1: Install Python packages
```bash
cd "f:\My Drive\Placement\BankOps-Lite"
pip install -r requirements.txt
```

### Step 2: Generate the legacy dirty data (5,000 transactions)
```bash
python pipeline/1_generate_legacy_data.py
```
**What happens:** Creates `raw_data/raw_customers.csv` and `raw_data/raw_transactions.csv` with deliberate data quality issues (nulls, duplicates, bad dates).

### Step 3: Run the Data Governance Engine
```bash
python pipeline/2_governance_engine.py
```
**What happens:** Validates all records against 9 governance rules, rejects invalid data, and loads clean records into the SQLite Star Schema (`bank_ops.db`). Saves a detailed audit log at `logs/governance_audit.txt`.

### Step 4: Train the ML Fraud Detection Model
```bash
python pipeline/3_fraud_detector.py
```
**What happens:** Trains a Random Forest classifier on transaction features, prints Accuracy/Precision/Recall/F1 scores, shows feature importance, and saves predictions back to the database.

### Step 5: Launch the Executive Dashboard
```bash
python dashboard/app.py
```
Then open your browser and go to: **http://127.0.0.1:5000**

---

## Dashboard Charts

| Chart | Query | Business Insight |
|---|---|---|
| Monthly Transaction Volume | SUM(amount) GROUP BY month | Identifies seasonal banking patterns |
| Account Type Distribution | COUNT(*) GROUP BY account_type | Customer product mix for marketing |
| Credit Score Bands | CASE WHEN credit_score ... THEN band | Risk segmentation of customer base |
| Top Branches by Volume | SUM(amount) GROUP BY branch_id | Infrastructure capacity planning |
| ML Fraud by Transaction Type | fraud_predicted=1 GROUP BY tx_type | Fraud pattern identification |
| Data Governance Score | clean/raw ratio from Governance_Audit | Data quality KPI for management |

---

## Database Schema (Star Schema)

```sql
Dim_Customer      -- WHO: Customer profiles, credit scores, account types
Dim_Date          -- WHEN: Date breakdown (day, month, quarter, year)
Fact_Transactions -- WHAT: Transaction events (amount, type, fraud label & prediction)
Governance_Audit  -- QUALITY: Data quality metrics per pipeline run
```

---

## Interview Q&A Cheatsheet

**Q: Why SQLite and not MySQL/PostgreSQL?**  
*A: SQLite is a file-based, zero-server-setup database. For a local PoC it is ideal — zero infrastructure cost, easy to share (just one .db file), and supports the full SQL standard needed for Star Schema queries. In production, the same schema would migrate to Azure Synapse Analytics or AWS Redshift.*

**Q: Why Random Forest for fraud detection?**  
*A: Fraud datasets are imbalanced (~8% fraud). Random Forest with class_weight='balanced' handles this well. It also provides feature importance — which is required for explainability in regulated banking environments (RBI guidelines).*

**Q: Where does the data come from?**  
*A: I generated a synthetic dataset mirroring a legacy core-banking system export. Real customer data cannot be used for dev/PoC work under PCI-DSS and GDPR regulations.*

**Q: What is a Star Schema?**  
*A: A Star Schema separates data into Fact tables (measurable events like transactions) and Dimension tables (descriptive context like customer profiles and dates). This structure makes analytical SQL queries fast and simple because you JOIN on small integer keys.*

**Q: What is Data Governance?**  
*A: It is the set of policies and automated rules that ensure data is accurate, complete, and consistent before entering the warehouse. My governance engine rejected ~10% of records (nulls, duplicates, invalid ages) and logged every decision in an audit trail.*
