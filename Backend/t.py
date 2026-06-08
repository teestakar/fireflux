import joblib
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.metrics import confusion_matrix, classification_report

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATABASE_URL = "postgresql://postgres:harmonica447@localhost:5432/fireflux"
MODEL_PATH = "fire_model.pkl"
THRESHOLD = -0.05  # your tuned anomaly threshold

# ─────────────────────────────────────────────
# LOAD MODEL + DATA
# ─────────────────────────────────────────────
model = joblib.load(MODEL_PATH)
engine = create_engine(DATABASE_URL)

query = """
    SELECT 
        r.temperature,
        r.gas_value
    FROM readings r
    WHERE r.room_id = 1
    ORDER BY r.timestamp DESC
    LIMIT 500
"""

df = pd.read_sql(text(query), engine.connect())

print(f"Loaded {len(df)} readings")

# ─────────────────────────────────────────────
# STEP 1 — ML SCORES
# ─────────────────────────────────────────────
X_test = df[['temperature', 'gas_value']].values
scores = model.decision_function(X_test)

# ─────────────────────────────────────────────
# STEP 2 — SYSTEM PREDICTION (ML + IS 2189)
# ─────────────────────────────────────────────
def predict_system(temp, gas, score):
    if score > THRESHOLD:
        return "safe"
    else:
        # anomaly → apply IS 2189
        if temp >= 78 or gas >= 2000:
            return "danger"
        else:
            return "warning"

y_pred = []
for temp, gas, score in zip(df['temperature'], df['gas_value'], scores):
    y_pred.append(predict_system(temp, gas, score))

# ─────────────────────────────────────────────
# STEP 3 — GROUND TRUTH (IS 2189 RULES)
# ─────────────────────────────────────────────
def ground_truth(temp, gas):
    if temp >= 78 or gas >= 2000:
        return "danger"
    elif temp >= 50 or gas >= 1000:
        return "warning"
    else:
        return "safe"

y_true = []
for temp, gas in zip(df['temperature'], df['gas_value']):
    y_true.append(ground_truth(temp, gas))

# ─────────────────────────────────────────────
# STEP 4 — PRINT SAMPLE OUTPUT
# ─────────────────────────────────────────────
print("\nSample Predictions:")
for i in range(10):
    print(f"T={df['temperature'][i]:.1f}, G={df['gas_value'][i]:.1f} → Pred={y_pred[i]}, True={y_true[i]}")

# ─────────────────────────────────────────────
# STEP 5 — 3-CLASS EVALUATION
# ─────────────────────────────────────────────
labels = ["safe", "warning", "danger"]

print("\n=== 3-CLASS CLASSIFICATION REPORT ===")
print(classification_report(y_true, y_pred, labels=labels))

print("\n=== CONFUSION MATRIX (3-class) ===")
cm = confusion_matrix(y_true, y_pred, labels=labels)
print(pd.DataFrame(cm, index=labels, columns=labels))

# ─────────────────────────────────────────────
# STEP 6 — BINARY (DANGER vs NOT DANGER)
# ─────────────────────────────────────────────
y_true_bin = [1 if x == "danger" else 0 for x in y_true]
y_pred_bin = [1 if x == "danger" else 0 for x in y_pred]

print("\n=== BINARY (DANGER vs NOT DANGER) ===")
print(classification_report(y_true_bin, y_pred_bin))

print("\n=== CONFUSION MATRIX (Binary) ===")
cm_bin = confusion_matrix(y_true_bin, y_pred_bin)
print(pd.DataFrame(cm_bin, index=["Not Danger", "Danger"], columns=["Not Danger", "Danger"]))