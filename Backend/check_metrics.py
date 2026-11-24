import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    precision_score, recall_score, f1_score, confusion_matrix
)
from train_model import DATABASE_URL

SEEDS = [0, 1, 2, 3, 4]
CONTAMINATION = 0.02
N_ANOMALIES = 300        # per difficulty band
TEST_FRACTION = 0.2
FPR_TARGET = 0.05
COLS = ["temperature", "gas_value"]

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    df = pd.read_sql(text("SELECT id, temperature, gas_value FROM readings ORDER BY id"), conn)
engine.dispose()
df = df.dropna(subset=COLS).reset_index(drop=True)

# Time-ordered split: train on older readings, test on newer ones
split = int(len(df) * (1 - TEST_FRACTION))
train = df.iloc[:split][COLS]
test_normal = df.iloc[split:][COLS].to_numpy(dtype=float)

# Robust spread (MAD). Plain std is inflated by outliers.
med = train.median()
sd_arr = (1.4826 * (train - med).abs().median()).clip(lower=1e-6).to_numpy(dtype=float)

print(f"Train: {len(train)} readings | Test (normal): {len(test_normal)} readings")
print(f"Robust spread: temp={sd_arr[0]:.2f}, gas={sd_arr[1]:.2f}\n")


# ─────────────────────────────────────────────
# SYNTHETIC ANOMALIES AT THREE DIFFICULTY LEVELS
# ─────────────────────────────────────────────
def make_anomalies(rng, base, band, n):
    if band == "easy":
        X = np.column_stack([rng.uniform(50, 100, n), rng.uniform(1500, 3000, n)])
    else:
        rows = base[rng.integers(0, len(base), n)].copy()
        if band == "medium":
            # Both features shifted 3 to 5 robust SDs
            k = rng.uniform(3, 5, (n, 1))
            s = rng.choice([-1, 1], (n, 1))
            rows = rows + s * k * sd_arr
        elif band == "hard":
            # One feature shifted 1.5 to 2.5 robust SDs
            k = rng.uniform(1.5, 2.5, n)
            s = rng.choice([-1, 1], n)
            feat = rng.integers(0, 2, n)
            rows[np.arange(n), feat] += s * k * sd_arr[feat]
        X = rows
    X[:, 1] = np.clip(X[:, 1], 0, None)  # gas can't be negative
    return X


# ─────────────────────────────────────────────
# EVALUATION (uses the model's own decision rule)
# ─────────────────────────────────────────────
def evaluate(model, X_norm, X_anom):
    X = pd.DataFrame(np.vstack([X_norm, X_anom]), columns=COLS)
    y = np.r_[np.zeros(len(X_norm)), np.ones(len(X_anom))]

    dec = model.decision_function(X)
    anomaly_score = -dec              # higher = more anomalous
    flagged = model.predict(X) == -1  # same rule the app uses

    roc_auc = roc_auc_score(y, anomaly_score)
    pr_auc = average_precision_score(y, anomaly_score)

    # Recall when the cutoff allows 5% false alarms on normal data
    cutoff = np.quantile(anomaly_score[y == 0], 1 - FPR_TARGET)
    recall_at_fpr = (anomaly_score[y == 1] > cutoff).mean()

    pred = flagged.astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()

    return {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "recall_at_5fpr": recall_at_fpr,
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "fpr": fp / (fp + tn),
    }


rows = []
for seed in SEEDS:
    rng = np.random.default_rng(seed)
    model = IsolationForest(contamination=CONTAMINATION, n_estimators=100, random_state=seed)
    model.fit(train)
    for band in ["easy", "medium", "hard"]:
        X_anom = make_anomalies(rng, test_normal, band, N_ANOMALIES)
        rows.append({"seed": seed, "band": band, **evaluate(model, test_normal, X_anom)})

results = pd.DataFrame(rows)
metric_cols = ["roc_auc", "pr_auc", "recall_at_5fpr", "precision", "recall", "f1", "fpr"]

# ─────────────────────────────────────────────
# REPORT: mean ± std over seeds
# ─────────────────────────────────────────────
summary = results.groupby("band")[metric_cols].agg(["mean", "std"])
pretty = pd.DataFrame(index=summary.index)
for m in metric_cols:
    pretty[m] = (summary[(m, "mean")].map("{:.3f}".format)
                 + " ± " + summary[(m, "std")].map("{:.3f}".format))

print(pretty.T.to_string())
pretty.to_csv("model_evaluation.csv")
print("\nSaved to model_evaluation.csv")