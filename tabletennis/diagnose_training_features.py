import pandas as pd
import random

TRAINING_CSV = "data/tt_czech_training_features.csv"
MATCHLOGS_CSV = "data/tt_czech_matchlogs.csv"

SAMPLE_SIZE = 50   # number of rows to test


print("Loading data...")

train = pd.read_csv(TRAINING_CSV, parse_dates=["date"])
logs = pd.read_csv(MATCHLOGS_CSV, parse_dates=["date"])

print("Rows in training:", len(train))
print("Rows in logs:", len(logs))

print("\nSampling rows for verification...")

samples = train.sample(SAMPLE_SIZE, random_state=42)

errors = 0

for i, row in samples.iterrows():

    match_date = row["date"]
    p1 = row["player1"]
    p2 = row["player2"]

    # Only matches BEFORE this one
    history = logs[logs["date"] < match_date]

    # -------------------------
    # H2H history
    # -------------------------
    h2h = history[
        ((history["player1"] == p1) & (history["player2"] == p2)) |
        ((history["player1"] == p2) & (history["player2"] == p1))
    ]

    # -------------------------
    # Player A history
    # -------------------------
    p1_hist = history[
        (history["player1"] == p1) |
        (history["player2"] == p1)
    ]

    # -------------------------
    # Player B history
    # -------------------------
    p2_hist = history[
        (history["player1"] == p2) |
        (history["player2"] == p2)
    ]

    if len(history) == 0:
        # Early dataset rows should mostly be neutral
        if row["h2h_L30_weighted"] not in [0.5, 0]:
            print("\n⚠ Unexpected early H2H value:")
            print(row)
            errors += 1

    # Print diagnostic summary
    print("\nMatch:", p1, "vs", p2)
    print("Date:", match_date)

    print("Past matches available:", len(history))
    print("H2H matches:", len(h2h))
    print("Player A past matches:", len(p1_hist))
    print("Player B past matches:", len(p2_hist))

print("\nDiagnostic complete.")
print("Potential issues found:", errors)