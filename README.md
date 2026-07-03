# BankOps-Lite 🏦
**Retail Banking Data Modernization & Fraud Intelligence Platform**

A complete Proof-of-Concept (PoC) data pipeline demonstrating Data Engineering, Data Governance, Machine Learning, and Business Intelligence for a retail banking scenario.

## Features
- **Data Engineering:** Simulates raw legacy core-banking exports with realistic data quality issues.
- **Data Governance Engine:** Cleanses and validates transactions, tracking quality metrics with an audit log.
- **Data Warehouse:** Stores cleansed data in a highly optimized SQLite Star Schema (`Dim_Customer`, `Dim_Date`, `Fact_Transactions`).
- **Machine Learning:** Uses a Random Forest classifier to detect fraudulent banking transactions.
- **BI Dashboard:** A Flask-based REST API and Chart.js UI visualizing transaction volume, credit risk, and fraud stats.

## How to Run

**Note: Do not double-click `index.html`. You must run the Flask server to see the styled dashboard and load the data.**

1. **Install Requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Full Pipeline (Data Gen ➔ Governance ➔ ML):**
   *(Skip this if you just want to run the dashboard—the SQLite database is already included in this repository).*
   ```bash
   python pipeline/1_generate_legacy_data.py
   python pipeline/2_governance_engine.py
   python pipeline/3_fraud_detector.py
   ```

3. **Launch the Dashboard:**
   ```bash
   python dashboard/app.py
   ```
   **Open your browser and navigate to:** [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Project Structure
- `/pipeline` - Python scripts for ETL, Governance, and ML model training.
- `/dashboard` - Flask app backend, HTML templates, and CSS/JS assets.
- `/raw_data` - Synthetic legacy CSV exports.
- `/logs` - Governance audit logs and ML performance reports.
- `bank_ops.db` - The SQLite data warehouse.
- `THOUGHT_PROCESS.txt` - Complete breakdown of the architecture, design choices, and ML logic.

---
*Built to simulate an Application & Data Modernization (ADMM) consulting engagement.*
