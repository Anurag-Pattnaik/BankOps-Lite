# =============================================================================
# FILE: pipeline/3_fraud_detector.py
#
# PURPOSE:
#   Trains a Machine Learning model (Random Forest Classifier) to detect
#   fraudulent banking transactions based on behavioral and financial features.
#   Predictions are written back into the SQLite database's Fact_Transactions
#   table so the dashboard can visualize both ground truth and predictions.
#
# INTERVIEW ANSWER — "Why Random Forest?":
#   "Random Forest is an ensemble model — it builds multiple decision trees
#    and averages their predictions. For fraud detection it works well because:
#    1. It handles imbalanced classes well (fraud is rare — ~8% of data).
#    2. It provides feature importance scores, telling us which attributes
#       matter most (e.g., account_age_days was the strongest predictor).
#    3. It does not require data normalization/scaling like SVM or Neural Nets.
#    4. It is interpretable — critical in banking where regulators need to
#       understand why a transaction was flagged (explainable AI)."
#
# INTERVIEW ANSWER — "Why not deep learning?":
#   "Deep learning requires hundreds of thousands of samples and a GPU to
#    train effectively. For 5,000 records, Random Forest achieves equivalent
#    accuracy with far less compute cost and is fully explainable — which is
#    a regulatory requirement in financial services (RBI guidelines)."
#
# OUTPUT:
#   bank_ops.db -> Fact_Transactions.fraud_predicted column updated
#   logs/ml_report.txt -> Model performance metrics
# =============================================================================

import pandas as pd
import sqlite3
import os
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score,
                              recall_score, f1_score, confusion_matrix)
from sklearn.preprocessing import LabelEncoder

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DB_PATH  = os.path.join(BASE_DIR, "bank_ops.db")
LOG_DIR  = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

print("=" * 60)
print("  BankOps-Lite | Step 3: ML Fraud Detection Model")
print("=" * 60)

report_lines = []
report_lines.append("BankOps-Lite | ML Fraud Detection Report")
report_lines.append(f"Run Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append("=" * 60)

def log(msg):
    print(msg)
    report_lines.append(msg)

# =============================================================================
# STEP 1: Load and Join Data from SQLite
# =============================================================================
log("\n[1/5] Loading data from SQLite warehouse...")

conn = sqlite3.connect(DB_PATH)

# JOIN Fact_Transactions with Dim_Customer to bring in behavioral features
# INTERVIEW: "Feature engineering — joining the customer profile to transactions
#             gives the model richer signal. A high-amount transaction from a
#             new-account customer is far more suspicious than the same amount
#             from a 5-year-old account. Without the JOIN, the model cannot
#             learn this pattern."
query = """
    SELECT
        ft.transaction_id,
        ft.transaction_type,
        ft.amount,
        ft.fraud_label,
        dc.account_age_days,
        dc.credit_score,
        dc.account_type,
        dd.month,
        dd.day_of_week
    FROM Fact_Transactions ft
    JOIN Dim_Customer dc ON ft.customer_id = dc.customer_id
    JOIN Dim_Date     dd ON ft.date_id     = dd.date_id
"""

df = pd.read_sql_query(query, conn)
log(f"  Loaded {len(df):,} transactions from warehouse")
log(f"  Fraud rate in dataset: {df['fraud_label'].mean()*100:.2f}%")

# =============================================================================
# STEP 2: Feature Engineering
# INTERVIEW: "Feature engineering is transforming raw data columns into signals
#             the model can learn from. We convert categorical text fields
#             (like 'Savings', 'Withdrawal') into numerical codes because ML
#             models only understand numbers."
# =============================================================================
log("\n[2/5] Engineering features for ML model...")

# Encode categorical columns → numeric using LabelEncoder
le_tx_type    = LabelEncoder()
le_acct_type  = LabelEncoder()
le_day        = LabelEncoder()

df["tx_type_enc"]   = le_tx_type.fit_transform(df["transaction_type"])
df["acct_type_enc"] = le_acct_type.fit_transform(df["account_type"])
df["day_enc"]       = le_day.fit_transform(df["day_of_week"])

# Derived feature: flag for high-value transaction (>100,000 INR)
# INTERVIEW: "Domain-derived binary flags are a simple but powerful form of
#             feature engineering. The model finds it easier to learn from
#             a 0/1 flag than from raw continuous amounts."
df["is_high_amount"] = (df["amount"] > 100000).astype(int)

# Final feature list for training
FEATURE_COLS = [
    "amount",           # Transaction value
    "account_age_days", # How old the customer's account is
    "credit_score",     # Customer's financial trustworthiness
    "tx_type_enc",      # Type: Deposit/Withdrawal/Transfer/Bill Payment
    "acct_type_enc",    # Savings / Current / Loan
    "day_enc",          # Day of week (weekend fraud spikes are common)
    "month",            # Month (end-of-month fraud spikes)
    "is_high_amount",   # Derived binary feature
]

TARGET_COL = "fraud_label"

X = df[FEATURE_COLS]
y = df[TARGET_COL]

log(f"  Feature columns : {FEATURE_COLS}")
log(f"  Target column   : {TARGET_COL}")

# =============================================================================
# STEP 3: Train / Test Split
# INTERVIEW: "We split data 80/20. The model trains on 80% and is tested on
#             the 20% it has never seen — simulating real-world deployment.
#             stratify=y ensures both splits have the same fraud percentage,
#             which is critical for imbalanced datasets like fraud."
# =============================================================================
log("\n[3/5] Splitting dataset (80% train / 20% test)...")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

log(f"  Training samples : {len(X_train):,}")
log(f"  Testing  samples : {len(X_test):,}")
log(f"  Fraud in train   : {y_train.sum():,} ({y_train.mean()*100:.1f}%)")
log(f"  Fraud in test    : {y_test.sum():,}  ({y_test.mean()*100:.1f}%)")

# =============================================================================
# STEP 4: Train Random Forest Model
# INTERVIEW: "n_estimators=100 means we build 100 decision trees and majority
#             vote on the final prediction. class_weight='balanced' tells the
#             model to penalize missing a fraud case (False Negative) more
#             than incorrectly flagging a legitimate one (False Positive) —
#             because missing real fraud is far more costly to the bank."
# =============================================================================
log("\n[4/5] Training Random Forest Classifier...")

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    class_weight="balanced",  # Critical for imbalanced fraud dataset
    random_state=42,
    n_jobs=-1                 # Use all CPU cores for speed
)
model.fit(X_train, y_train)

# Generate predictions on unseen test data
y_pred = model.predict(X_test)

# ── Performance Metrics ────────────────────────────────────────────────────────
# INTERVIEW: "For fraud detection, Recall is more important than Accuracy.
#             Recall = how many actual fraud cases we caught. A model can
#             achieve 92% accuracy by predicting EVERYTHING as not-fraud —
#             useless! Precision-Recall tradeoff is the key metric here."
acc  = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, zero_division=0)
rec  = recall_score(y_test, y_pred, zero_division=0)
f1   = f1_score(y_test, y_pred, zero_division=0)
cm   = confusion_matrix(y_test, y_pred)

log(f"\n  -- Model Performance on Test Set --")
log(f"  Accuracy  : {acc*100:.2f}%  (overall correct predictions)")
log(f"  Precision : {prec*100:.2f}%  (of flagged fraud, how many were real)")
log(f"  Recall    : {rec*100:.2f}%  (of real fraud, how many did we catch)")
log(f"  F1 Score  : {f1*100:.2f}%  (balance of Precision and Recall)")
log(f"\n  Confusion Matrix:")
log(f"               Predicted: OK  Predicted: Fraud")
log(f"  Actual: OK   {cm[0][0]:^15} {cm[0][1]:^16}")
log(f"  Actual: Fraud{cm[1][0]:^15} {cm[1][1]:^16}")

# ── Feature Importance ─────────────────────────────────────────────────────────
importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
importances = importances.sort_values(ascending=False)
log(f"\n  -- Feature Importance (what the model found most useful) --")
for feat, imp in importances.items():
    bar = "|" * int(imp * 40)
    log(f"  {feat:<20} {imp:.4f}  {bar}")

# =============================================================================
# STEP 5: Write Predictions Back to SQLite
# INTERVIEW: "Writing predictions back to the database closes the loop —
#             the dashboard can now query fraud_predicted alongside the
#             ground truth fraud_label to show model performance visually."
# =============================================================================
log("\n[5/5] Saving predictions back to SQLite Fact_Transactions...")

# Predict on ALL transactions (not just test set) for dashboard display
all_predictions = model.predict(X)

# Map transaction_id -> prediction
pred_df = df[["transaction_id"]].copy()
pred_df["fraud_predicted"] = all_predictions

# Update each row in SQLite
cursor = conn.cursor()
for _, row in pred_df.iterrows():
    cursor.execute(
        "UPDATE Fact_Transactions SET fraud_predicted = ? WHERE transaction_id = ?",
        (int(row["fraud_predicted"]), row["transaction_id"])
    )
conn.commit()
conn.close()

log(f"  Updated {len(pred_df):,} rows in Fact_Transactions.fraud_predicted")

# ── Save Report ────────────────────────────────────────────────────────────────
report_path = os.path.join(LOG_DIR, "ml_report.txt")
with open(report_path, "w") as f:
    f.write("\n".join(report_lines))

log(f"\n  ML report saved -> {report_path}")
log("\n[DONE] ML Fraud Detection complete.")
log("\nNext Step: Run python dashboard/app.py")
log("           Then open http://127.0.0.1:5000 in your browser")
