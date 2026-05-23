import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
import joblib

# ─────────────────────────────────────────────
# STEP 1 — Connect to database
# ─────────────────────────────────────────────
DATABASE_URL = "postgresql://postgres:harmonica447@localhost:5432/fireflux"
engine = create_engine(DATABASE_URL)

print("Connecting to database...")

# ─────────────────────────────────────────────
# STEP 2 — Pull clean Room 1 safe readings
#
# Filters applied:
# 1. risk_level = 'safe' — only normal readings
# 2. room_id = 1 — only real ESP32 sensor data
# 3. temperature <= 40 — exclude old Swagger test
#    readings that were wrongly saved as safe
# 4. gas_value <= 1200 — same reason
#
# This gives us clean real sensor data only
# ─────────────────────────────────────────────
query = """
    SELECT 
        r.temperature,
        r.gas_value
    FROM readings r
    JOIN risk_assessments ra ON ra.reading_id = r.id
    WHERE ra.risk_level = 'safe'
    AND r.room_id = 1
    AND r.temperature <= 40
    AND r.gas_value <= 1200
"""

df = pd.read_sql(text(query), engine.connect())
print(f"Loaded {len(df)} clean Room 1 readings from database")

# ─────────────────────────────────────────────
# STEP 3 — Prepare features
# Temperature and gas only.
# Motion removed — caused false warnings.
# ─────────────────────────────────────────────
X = df[['temperature', 'gas_value']]

print(f"\nFeature summary:")
print(X.describe())

# ─────────────────────────────────────────────
# STEP 4 — Train Isolation Forest
# ─────────────────────────────────────────────
print("\nTraining Isolation Forest...")

model = IsolationForest(
    contamination=0.05,
    n_estimators=100,
    random_state=42
)

model.fit(X)
print("Training complete!")

# ─────────────────────────────────────────────
# STEP 5 — Test on sample readings
# ─────────────────────────────────────────────
print("\nTesting model on sample readings:")

test_cases = pd.DataFrame([
    {"temperature": 28.0, "gas_value": 400.0},   # normal
    {"temperature": 35.0, "gas_value": 264.0},   # room 1 borderline
    {"temperature": 42.0, "gas_value": 164.0},   # problem case
    {"temperature": 43.0, "gas_value": 123.0},   # problem case
    {"temperature": 75.0, "gas_value": 1800.0},  # suspicious
    {"temperature": 90.0, "gas_value": 2500.0},  # danger
])

predictions = model.predict(test_cases)
scores = model.decision_function(test_cases)

labels = ["Normal", "Borderline", "Problem case 1", "Problem case 2", "Suspicious", "Danger"]
for label, pred, score in zip(labels, predictions, scores):
    result = "NORMAL" if pred == 1 else "ANOMALY"
    print(f"  {label:20s} → {result}  (score: {score:.4f})")

# ─────────────────────────────────────────────
# STEP 6 — Save model
# ─────────────────────────────────────────────
joblib.dump(model, "fire_model.pkl")
print("\nModel saved as fire_model.pkl")
print("Done! Restart FastAPI to load the new model.")