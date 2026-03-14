import pandas as pd

# --- Load your schedule and match logs ---
schedule = pd.read_csv("data/tt_elite_schedule.csv", parse_dates=["date"])
matchlogs = pd.read_csv("data/tt_elite_matchlogs.csv", parse_dates=["date"])

min_h2h_threshold = 10

# Container for final features
features = []

for idx, match in schedule.iterrows():
    player1 = match["player1"]
    player2 = match["player2"]
    match_date = match["date"]
    match_id = match["match_id"]

    # Filter past matches before this match date
    past_matches = matchlogs[matchlogs["date"] < match_date].copy()

    # --- Dynamically add four_plus column ---
    past_matches["four_plus"] = (past_matches["sets1"] + past_matches["sets2"] >= 4).astype(int)

    # --- H2H matches between these two players ---
    h2h_matches = past_matches[
        ((past_matches["player1"] == player1) & (past_matches["player2"] == player2)) |
        ((past_matches["player1"] == player2) & (past_matches["player2"] == player1))
    ].sort_values("date", ascending=False)

    # Take last 10 and last 30
    last_10 = h2h_matches.head(10)
    last_30 = h2h_matches.head(30)

    # Compute raw H2H values using four_plus
    h2h_L10 = last_10["four_plus"].mean() if not last_10.empty else 0.5
    h2h_L30 = last_30["four_plus"].mean() if not last_30.empty else 0.5

    # Track counts
    h2h_count_L10 = len(last_10)
    h2h_count_L30 = len(last_30)

    # --- Recent form for each player ---
    recent_A = past_matches[
        (past_matches["player1"] == player1) |
        (past_matches["player2"] == player1)
    ].sort_values("date")

    recent_B = past_matches[
        (past_matches["player1"] == player2) |
        (past_matches["player2"] == player2)
    ].sort_values("date")

    recent_A_L10 = recent_A["four_plus"].tail(10).mean() if not recent_A.empty else 0.5
    recent_B_L10 = recent_B["four_plus"].tail(10).mean() if not recent_B.empty else 0.5
    recent_A_L30 = recent_A["four_plus"].tail(30).mean() if not recent_A.empty else 0.5
    recent_B_L30 = recent_B["four_plus"].tail(30).mean() if not recent_B.empty else 0.5

    # --- Weighted H2H ---
    recent_avg = (recent_A_L10 + recent_B_L10) / 2
    h2h_L10_weighted = (min(h2h_count_L10, min_h2h_threshold)/min_h2h_threshold * h2h_L10 +
                        (1 - min(h2h_count_L10, min_h2h_threshold)/min_h2h_threshold) * recent_avg)
    h2h_L30_weighted = (min(h2h_count_L30, min_h2h_threshold)/min_h2h_threshold * h2h_L30 +
                        (1 - min(h2h_count_L30, min_h2h_threshold)/min_h2h_threshold) * recent_avg)

    # --- Store features ---
    features.append({
        "match_id": match_id,
        "date": match_date,
        "player1": player1,
        "player2": player2,
        "h2h_L10_weighted": h2h_L10_weighted,
        "h2h_L30_weighted": h2h_L30_weighted,
        "h2h_L10_count": h2h_count_L10,
        "h2h_L30_count": h2h_count_L30,
        "recent_A_L10": recent_A_L10,
        "recent_B_L10": recent_B_L10,
        "recent_A_L30": recent_A_L30,
        "recent_B_L30": recent_B_L30
    })

# --- Output final CSV ---
features_df = pd.DataFrame(features)
features_df.to_csv("data/tt_elite_features_weighted.csv", index=False)
print("Weighted feature CSV generated: tt_czech_schedule_features_weighted.csv")