import joblib
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
import numpy as np

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATABASE_URL = "postgresql://postgres:harmonica447@localhost:5432/fireflux"
MODEL_PATH = "fire_model.pkl"
THRESHOLD = -0.05

# ─────────────────────────────────────────────
# LOAD MODEL + DATA
# ─────────────────────────────────────────────
model = joblib.load(MODEL_PATH)
engine = create_engine(DATABASE_URL)

query = """
    SELECT 
        r.temperature,
        r.gas_value,
        ra.risk_level
    FROM readings r
    JOIN risk_assessments ra ON r.id = ra.reading_id
    WHERE ra.risk_level IS NOT NULL
    ORDER BY r.timestamp DESC
"""

df = pd.read_sql(text(query), engine.connect())
print(f"Loaded {len(df)} verified predictions\n")

# ─────────────────────────────────────────────
# GET ML SCORES
# ─────────────────────────────────────────────
X = df[['temperature', 'gas_value']].values
scores = model.decision_function(X)

# ─────────────────────────────────────────────
# SYSTEM PREDICTION (ML + IS 2189 + TIER 2)
# Matches the actual backend assess_risk() logic
# ─────────────────────────────────────────────
y_pred = []
for temp, gas, score in zip(df['temperature'], df['gas_value'], scores):
    
    # Layer 1 — ML anomaly detection
    if score > THRESHOLD:
        y_pred.append("safe")
    
    # Layer 2 — IS 2189 danger tier
    elif temp >= 78 or gas >= 2000:
        y_pred.append("danger")
    
    # Tier 2 — physically normal range despite ML flag
    # (catches readings outside model's training distribution but still physically safe)
    elif temp <= 45 and gas <= 1000:
        y_pred.append("safe")
    
    # Tier 3 — elevated but below danger threshold
    else:
        y_pred.append("warning")

# ─────────────────────────────────────────────
# GROUND TRUTH (from verified database labels)
# ─────────────────────────────────────────────
y_true = df['risk_level'].tolist()
labels = ["safe", "warning", "danger"]

# ─────────────────────────────────────────────
# SAMPLE OUTPUT
# ─────────────────────────────────────────────
print("Sample Predictions (first 15):")
print("T(°C)  G(ppm)  Score   Pred      True")
print("─" * 50)
for i in range(min(15, len(df))):
    print(f"{df['temperature'].iloc[i]:5.1f}  {df['gas_value'].iloc[i]:6.1f}  {scores[i]:6.3f}  {y_pred[i]:8s}  {y_true[i]:8s}")

# ─────────────────────────────────────────────
# METRICS FOR CV
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("=== METRICS FOR CV ===")
print("="*60)
print(f"Accuracy:  {accuracy_score(y_true, y_pred):.1%}")
print(f"Precision: {precision_score(y_true, y_pred, labels=labels, average='weighted'):.1%}")
print(f"Recall:    {recall_score(y_true, y_pred, labels=labels, average='weighted'):.1%}")
print(f"F1-Score:  {f1_score(y_true, y_pred, labels=labels, average='weighted'):.1%}")

# ─────────────────────────────────────────────
# DETAILED CLASSIFICATION REPORT
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("=== DETAILED REPORT ===")
print("="*60)
print(classification_report(y_true, y_pred, labels=labels))

# ─────────────────────────────────────────────
# CONFUSION MATRIX
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("=== CONFUSION MATRIX ===")
print("="*60)
cm = confusion_matrix(y_true, y_pred, labels=labels)
cm_df = pd.DataFrame(cm, index=labels, columns=labels)
print(cm_df)

# ─────────────────────────────────────────────
# BINARY EVALUATION (DANGER vs NOT DANGER)
# ─────────────────────────────────────────────
y_true_bin = [1 if x == "danger" else 0 for x in y_true]
y_pred_bin = [1 if x == "danger" else 0 for x in y_pred]

print("\n" + "="*60)
print("=== BINARY (DANGER vs NOT DANGER) ===")
print("="*60)
print(f"Accuracy:  {accuracy_score(y_true_bin, y_pred_bin):.1%}")
print(f"Precision: {precision_score(y_true_bin, y_pred_bin):.1%}")
print(f"Recall:    {recall_score(y_true_bin, y_pred_bin):.1%}")
print(f"F1-Score:  {f1_score(y_true_bin, y_pred_bin):.1%}")

print("\n" + "="*60)
print("=== BINARY CONFUSION MATRIX ===")
print("="*60)
cm_bin = confusion_matrix(y_true_bin, y_pred_bin)
cm_bin_df = pd.DataFrame(
    cm_bin, 
    index=["Not Danger", "Danger"], 
    columns=["Not Danger", "Danger"]
)
print(cm_bin_df)

# ─────────────────────────────────────────────
# CLASS DISTRIBUTION
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("=== CLASS DISTRIBUTION ===")
print("="*60)
for label in labels:
    count = y_true.count(label)
    pct = (count / len(y_true)) * 100
    print(f"{label:8s}: {count:4d} ({pct:5.1f}%)")