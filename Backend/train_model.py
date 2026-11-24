import os
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
import joblib

DATABASE_URL = "postgresql://postgres:harmonica447@localhost:5432/fireflux"
FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(FOLDER, "fire_model.pkl")


def train_model():
    engine = create_engine(DATABASE_URL)

    query = """
        SELECT temperature, gas_value
        FROM readings
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    engine.dispose()

    X = df[["temperature", "gas_value"]].dropna()
    print(f"Training on {len(X)} readings")

    model = IsolationForest(
        contamination=0.02,
        n_estimators=100,
        random_state=42
    )
    model.fit(X)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")


# Loaded once and reused
_model = None


def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def classify_reading(temperature, gas_value):
    """Returns 'normal' or 'anomaly' for one reading."""
    X = pd.DataFrame([[temperature, gas_value]], columns=["temperature", "gas_value"])
    pred = get_model().predict(X)[0]
    return "normal" if pred == 1 else "anomaly"


if __name__ == "__main__":
    train_model()
    print(classify_reading(28.0, 400.0))
    print(classify_reading(90.0, 2500.0))