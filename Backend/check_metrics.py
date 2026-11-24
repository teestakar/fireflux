import joblib
import pandas as pd

model = joblib.load("fire_model.pkl")
X = pd.DataFrame([[29.0, 1358.0]], columns=["temperature", "gas_value"])
print("Score:", model.decision_function(X)[0])
print("Result:", "anomaly" if model.predict(X)[0] == -1 else "normal")