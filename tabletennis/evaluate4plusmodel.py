import pandas as pd

pred = pd.read_csv("data/tt_czech_historical_4plus_predictions.csv")
logs = pd.read_csv("data/tt_czech_matchlogs.csv")

# create actual 4+ result
logs["actual_4plus"] = (logs["sets1"] + logs["sets2"] >= 4).astype(int)

# merge predictions with actual results
df = pred.merge(
    logs[["match_id", "sets1", "sets2", "actual_4plus"]],
    on="match_id",
    how="inner"
)

print("Merged matches:", len(df))

#predict 4+ if probability ≥ 0.5

df["predicted_4plus"] = (df["P_4plus"] >= 0.5).astype(int)

accuracy = (df["predicted_4plus"] == df["actual_4plus"]).mean()

print("Accuracy:", accuracy)

df["bucket"] = pd.cut(df["P_4plus"], bins=5)

print(df.groupby("bucket")["actual_4plus"].mean())

high_conf = df[df["P_4plus"] > 0.65]

print("High confidence sample:", len(high_conf))
print("Actual success rate:", high_conf["actual_4plus"].mean())

print(df["P_4plus"].describe())

print("\nFeature correlation with actual result:\n")

cols = [
    "h2h_L10_weighted",
    "h2h_L30_weighted",
    "h2h_L60_weighted",
    "recent_A_L10",
    "recent_B_L10",
    "recent_A_L30",
    "recent_B_L30",
    "match_balance_L10"
]

for c in cols:
    print(c, df[c].corr(df["actual_4plus"]))

print(df["actual_4plus"].mean())

print(df.nsmallest(20, "P_4plus")[["player1","player2","P_4plus","actual_4plus"]])

print(df.nlargest(20, "P_4plus")[["player1","player2","P_4plus","actual_4plus"]])

print(len(pd.concat([logs["player1"], logs["player2"]]).unique()))

import pandas as pd
import numpy as np
from itertools import product

# --- Load data ---
pred = pd.read_csv("data/tt_czech_4plus_predictions.csv")
logs = pd.read_csv("data/tt_czech_historical.csv")

logs["actual_4plus"] = (logs["sets1"] + logs["sets2"] >= 4).astype(int)

df = pred.merge(
    logs[["match_id", "sets1", "sets2", "actual_4plus"]],
    on="match_id",
    how="inner"
)

# Create recent form difference
df['recent_diff'] = df['recent_A_L30'] - df['recent_B_L30']

# Weight grid
w_values = np.arange(0.0, 1.05, 0.1)

best_acc = 0
best_bucket_error = float('inf')
best_weights = None

for w10, w30, w60, w_recent in product(w_values, repeat=4):
    if w10 + w30 + w60 + w_recent == 0:
        continue

    # Normalize weights
    total = w10 + w30 + w60 + w_recent
    w10_n, w30_n, w60_n, w_recent_n = w10/total, w30/total, w60/total, w_recent/total

    # Compute weighted P_4plus
    df['P_4plus_weighted'] = (
        w10_n * df['h2h_L10_weighted'] +
        w30_n * df['h2h_L30_weighted'] +
        w60_n * df['h2h_L60_weighted'] +
        w_recent_n * df['recent_diff']
    ).clip(0, 1)

    # Predict
    df['predicted_4plus'] = (df['P_4plus_weighted'] >= 0.5).astype(int)

    # Overall accuracy
    acc = (df['predicted_4plus'] == df['actual_4plus']).mean()

    # Bucket calibration
    df['bucket'] = pd.cut(df['P_4plus_weighted'], bins=5)
    bucket_means = df.groupby('bucket', observed=True)['actual_4plus'].mean()
    # Compute total squared error from ideal calibration
    bucket_error = ((bucket_means - [0.1, 0.3, 0.5, 0.7, 0.9])**2).sum()

    # Track best: prioritize accuracy, then calibration
    if acc > best_acc or (acc == best_acc and bucket_error < best_bucket_error):
        best_acc = acc
        best_bucket_error = bucket_error
        best_weights = (w10_n, w30_n, w60_n, w_recent_n)
        best_bucket_means = bucket_means.copy()

print("Best weighted accuracy:", best_acc)
print("Best weights (h2h_L10, h2h_L30, h2h_L60, recent_diff):", best_weights)
print("\nBucket calibration (actual 4+ mean per bucket):\n", best_bucket_means)