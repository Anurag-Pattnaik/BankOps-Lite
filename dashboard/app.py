from flask import Flask, render_template, jsonify
import sqlite3
import os

# =============================================================================
# FILE: dashboard/app.py
#
# PURPOSE:
#   Flask web server that acts as the API layer between the SQLite data
#   warehouse and the HTML/Chart.js dashboard.
#   Each route runs a specific SQL query and returns JSON data to the frontend.
#
# INTERVIEW ANSWER — "Why Flask?":
#   "Flask is a lightweight Python micro-framework. In consulting PoCs we need
#    to demonstrate a working product quickly without heavy infrastructure.
#    Flask lets us serve a REST API and HTML dashboard in under 30 lines of
#    code, which is perfect for an internal BI prototype before handing off
#    to a full-stack team for production deployment on Azure App Service or
#    AWS Elastic Beanstalk."
# =============================================================================

app = Flask(__name__)

# Path to our SQLite database (one directory up from this file)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bank_ops.db")


def query_db(sql, args=()):
    """
    Helper function: Opens a connection, runs a query, returns results as
    a list of dictionaries (column_name → value). This is the safest way to
    handle SQLite connections in Flask — open, query, close per request.
    INTERVIEW: "We use row_factory = sqlite3.Row to get dictionary-like rows
                so the JSON output has named keys instead of positional indices."
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # Returns dict-like rows
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Route 1: Serve the dashboard HTML page ────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Route 2: Governance Audit Metrics ─────────────────────────────────────────
@app.route("/api/governance")
def api_governance():
    """Returns the latest data quality audit run from the Governance_Audit table."""
    rows = query_db("""
        SELECT raw_customers, clean_customers,
               raw_transactions, clean_transactions,
               ROUND(cust_pass_rate, 1)  AS cust_pass_rate,
               ROUND(tx_pass_rate, 1)    AS tx_pass_rate,
               run_timestamp
        FROM   Governance_Audit
        ORDER  BY run_id DESC
        LIMIT  1
    """)
    return jsonify(rows[0] if rows else {})


# ── Route 3: Monthly Transaction Volumes ──────────────────────────────────────
@app.route("/api/monthly_volume")
def api_monthly_volume():
    """
    Returns total deposits and withdrawals per month for the bar chart.
    INTERVIEW: "This query uses a CASE WHEN expression to pivot transaction_type
                into separate deposit/withdrawal columns — equivalent to a
                conditional aggregation, same as SUMIF in Excel."
    """
    rows = query_db("""
        SELECT
            dd.year || '-' || PRINTF('%02d', dd.month) AS month_label,
            ROUND(SUM(CASE WHEN ft.transaction_type = 'Deposit'    THEN ft.amount ELSE 0 END), 2) AS deposits,
            ROUND(SUM(CASE WHEN ft.transaction_type = 'Withdrawal' THEN ft.amount ELSE 0 END), 2) AS withdrawals
        FROM   Fact_Transactions ft
        JOIN   Dim_Date dd ON ft.date_id = dd.date_id
        GROUP  BY dd.year, dd.month
        ORDER  BY dd.year, dd.month
    """)
    return jsonify(rows)


# ── Route 4: Account Type Distribution ────────────────────────────────────────
@app.route("/api/account_distribution")
def api_account_distribution():
    """Returns the count of customers per account type for the donut chart."""
    rows = query_db("""
        SELECT account_type, COUNT(*) AS count
        FROM   Dim_Customer
        GROUP  BY account_type
        ORDER  BY count DESC
    """)
    return jsonify(rows)


# ── Route 5: Top Branches by Transaction Volume ────────────────────────────────
@app.route("/api/top_branches")
def api_top_branches():
    """Returns top 10 branches by total transaction amount for the horizontal bar chart."""
    rows = query_db("""
        SELECT
            ft.branch_id,
            COUNT(*)                    AS tx_count,
            ROUND(SUM(ft.amount), 2)   AS total_volume
        FROM   Fact_Transactions ft
        GROUP  BY ft.branch_id
        ORDER  BY total_volume DESC
        LIMIT  10
    """)
    return jsonify(rows)


# ── Route 6: Fraud Analytics ───────────────────────────────────────────────────
@app.route("/api/fraud_stats")
def api_fraud_stats():
    """
    Returns fraud statistics comparing ground truth labels vs ML predictions.
    INTERVIEW: "Comparing fraud_label (ground truth) vs fraud_predicted (model)
                visually shows the model's effectiveness. If the two numbers are
                close, the model has high recall — it catches most real fraud."
    """
    rows = query_db("""
        SELECT
            SUM(fraud_label)                            AS actual_fraud,
            SUM(CASE WHEN fraud_predicted = 1 THEN 1 ELSE 0 END) AS predicted_fraud,
            COUNT(*)                                    AS total_transactions,
            ROUND(AVG(fraud_label) * 100, 2)            AS fraud_rate_pct
        FROM Fact_Transactions
        WHERE fraud_predicted != -1
    """)
    return jsonify(rows[0] if rows else {})


# ── Route 7: Fraud by Transaction Type ────────────────────────────────────────
@app.route("/api/fraud_by_type")
def api_fraud_by_type():
    """Returns predicted fraud count broken down by transaction type for pie chart."""
    rows = query_db("""
        SELECT
            transaction_type,
            SUM(CASE WHEN fraud_predicted = 1 THEN 1 ELSE 0 END) AS predicted_fraud
        FROM   Fact_Transactions
        WHERE  fraud_predicted != -1
        GROUP  BY transaction_type
        ORDER  BY predicted_fraud DESC
    """)
    return jsonify(rows)


# ── Route 8: Credit Score Distribution ────────────────────────────────────────
@app.route("/api/credit_distribution")
def api_credit_distribution():
    """
    Buckets customers into credit score bands for the histogram.
    INTERVIEW: "Credit score banding is standard practice in banking risk —
                RBI guidelines categorize CIBIL scores into risk tiers."
    """
    rows = query_db("""
        SELECT
            CASE
                WHEN credit_score BETWEEN 300 AND 499 THEN 'Poor (300–499)'
                WHEN credit_score BETWEEN 500 AND 649 THEN 'Fair (500–649)'
                WHEN credit_score BETWEEN 650 AND 749 THEN 'Good (650–749)'
                WHEN credit_score BETWEEN 750 AND 900 THEN 'Excellent (750–900)'
                ELSE 'Unknown'
            END AS score_band,
            COUNT(*) AS customer_count
        FROM  Dim_Customer
        GROUP BY score_band
        ORDER BY MIN(credit_score)
    """)
    return jsonify(rows)


# =============================================================================
# Run the Flask development server
# =============================================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  BankOps-Lite | Analytics Dashboard")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
