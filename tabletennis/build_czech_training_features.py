import pandas as pd

# -------------------------
# Load matchlogs
# -------------------------
matchlogs = pd.read_csv(
    "data/tt_czech_matchlogs.csv",
    parse_dates=["date"]
)

# Ensure chronological order
matchlogs = matchlogs.sort_values("date").reset_index(drop=True)

min_h2h_threshold = 10

features = []

# -------------------------
# Iterate through matches
# -------------------------
for idx, match in matchlogs.iterrows():

    player1 = match["player1"]
    player2 = match["player2"]
    match_date = match["date"]

    # Only matches BEFORE this match
    past_matches = matchlogs.iloc[:idx]

    if len(past_matches) < 30:
        continue  # skip early rows with almost no history

    # -------------------------
    # H2H
    # -------------------------
    h2h_matches = past_matches[
        ((past_matches["player1"] == player1) & (past_matches["player2"] == player2)) |
        ((past_matches["player1"] == player2) & (past_matches["player2"] == player1))
    ].sort_values("date", ascending=False)

    last_10 = h2h_matches.head(10)
    last_30 = h2h_matches.head(30)

    h2h_L10 = last_10["four_plus"].mean() if not last_10.empty else 0.5
    h2h_L30 = last_30["four_plus"].mean() if not last_30.empty else 0.5

    h2h_count_L10 = len(last_10)
    h2h_count_L30 = len(last_30)

    # -------------------------
    # Recent form
    # -------------------------
    recent_A = past_matches[
        (past_matches["player1"] == player1) |
        (past_matches["player2"] == player1)
    ]

    recent_B = past_matches[
        (past_matches["player1"] == player2) |
        (past_matches["player2"] == player2)
    ]

    recent_A_L10 = recent_A.tail(10)["four_plus"].mean() if not recent_A.empty else 0.5
    recent_B_L10 = recent_B.tail(10)["four_plus"].mean() if not recent_B.empty else 0.5

    recent_A_L30 = recent_A.tail(30)["four_plus"].mean() if not recent_A.empty else 0.5
    recent_B_L30 = recent_B.tail(30)["four_plus"].mean() if not recent_B.empty else 0.5

    # -------------------------
    # Weighted H2H
    # -------------------------
    recent_avg = (recent_A_L10 + recent_B_L10) / 2

    weight_L10 = min(h2h_count_L10, min_h2h_threshold) / min_h2h_threshold
    weight_L30 = min(h2h_count_L30, min_h2h_threshold) / min_h2h_threshold

    h2h_L10_weighted = weight_L10 * h2h_L10 + (1 - weight_L10) * recent_avg
    h2h_L30_weighted = weight_L30 * h2h_L30 + (1 - weight_L30) * recent_avg

    # -------------------------
    # Store training row
    # -------------------------
    features.append({
        "match_id": match["match_id"],
        "date": match_date,
        "player1": player1,
        "player2": player2,
        "h2h_L10_weighted": h2h_L10_weighted,
        "h2h_L30_weighted": h2h_L30_weighted,
        "recent_A_L10": recent_A_L10,
        "recent_B_L10": recent_B_L10,
        "recent_A_L30": recent_A_L30,
        "recent_B_L30": recent_B_L30,
        "four_plus": match["four_plus"]
    })

# -------------------------
# Save dataset
# -------------------------
training_df = pd.DataFrame(features)

training_df.to_csv(
    "data/tt_czech_training_features.csv",
    index=False
)

print("Training dataset created:")
print("data/tt_czech_training_features.csv")
print("Rows:", len(training_df))