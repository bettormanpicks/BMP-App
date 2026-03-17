import pandas as pd

# --- Load schedule and match logs ---
schedule = pd.read_csv("data/tt_czech_matchlogs.csv", parse_dates=["date"])
matchlogs = pd.read_csv("data/tt_czech_matchlogs.csv", parse_dates=["date"])

# --- Preprocessing ---
matchlogs = matchlogs.sort_values("date")
matchlogs["four_plus"] = ((matchlogs["sets1"] + matchlogs["sets2"]) >= 4).astype(int)

# Precompute wins for faster strength calculation
matchlogs["is_win_player1"] = matchlogs["sets1"] > matchlogs["sets2"]
matchlogs["is_win_player2"] = matchlogs["sets2"] > matchlogs["sets1"]

# --- Build player index ---
player_index = {}
for player in pd.concat([matchlogs["player1"], matchlogs["player2"]]).unique():
    player_index[player] = matchlogs[
        (matchlogs["player1"] == player) | (matchlogs["player2"] == player)
    ]

# --- Build H2H index ---
h2h_index = {}
for key, df in matchlogs.groupby([matchlogs['player1'], matchlogs['player2']]):
    sorted_key = tuple(sorted(key))
    if sorted_key not in h2h_index:
        h2h_index[sorted_key] = df.copy()
    else:
        h2h_index[sorted_key] = pd.concat([h2h_index[sorted_key], df])

min_h2h_threshold = 10
features = []

# --- Generate features ---
for idx, match in schedule.iterrows():
    player1 = match["player1"]
    player2 = match["player2"]
    match_date = match["date"]
    match_id = match["match_id"]

    # --- H2H matches ---
    key = tuple(sorted([player1, player2]))
    h2h_matches = h2h_index.get(key, pd.DataFrame())
    h2h_matches = h2h_matches[h2h_matches["date"] < match_date]

    last_10 = h2h_matches.head(10)
    last_30 = h2h_matches.head(30)
    last_60 = h2h_matches.head(60)

    h2h_L10 = last_10["four_plus"].mean() if not last_10.empty else 0
    h2h_L30 = last_30["four_plus"].mean() if not last_30.empty else 0
    h2h_L60 = last_60["four_plus"].mean() if not last_60.empty else 0

    h2h_count_L10 = len(last_10)
    h2h_count_L30 = len(last_30)
    h2h_count_L60 = len(last_60)

    # --- Recent form ---
    recent_A = player_index.get(player1, pd.DataFrame()).copy()
    recent_A = recent_A[recent_A["date"] < match_date].copy()

    recent_B = player_index.get(player2, pd.DataFrame()).copy()
    recent_B = recent_B[recent_B["date"] < match_date].copy()

    recent_A_L10 = recent_A["four_plus"].tail(10).mean() if not recent_A.empty else 0.5
    recent_B_L10 = recent_B["four_plus"].tail(10).mean() if not recent_B.empty else 0.5
    recent_A_L30 = recent_A["four_plus"].tail(30).mean() if not recent_A.empty else 0.5
    recent_B_L30 = recent_B["four_plus"].tail(30).mean() if not recent_B.empty else 0.5

    player_A_4plus_rate_last50 = recent_A["four_plus"].tail(50).mean() if not recent_A.empty else 0.5
    player_B_4plus_rate_last50 = recent_B["four_plus"].tail(50).mean() if not recent_B.empty else 0.5

    # --- Weighted H2H ---
    recent_avg = ((recent_A_L10 * 0.6 + recent_A_L30 * 0.4) +
                  (recent_B_L10 * 0.6 + recent_B_L30 * 0.4)) / 2

    h2h_L10_weighted = (min(h2h_count_L10, min_h2h_threshold) / min_h2h_threshold * h2h_L10 +
                        (1 - min(h2h_count_L10, min_h2h_threshold) / min_h2h_threshold) * recent_avg)
    h2h_L30_weighted = (min(h2h_count_L30, min_h2h_threshold) / min_h2h_threshold * h2h_L30 +
                        (1 - min(h2h_count_L30, min_h2h_threshold) / min_h2h_threshold) * recent_avg)
    h2h_L60_weighted = (min(h2h_count_L60, min_h2h_threshold) / min_h2h_threshold * h2h_L60 +
                        (1 - min(h2h_count_L60, min_h2h_threshold) / min_h2h_threshold) * recent_avg)

    # --- Strength and form gaps ---
    recent_A.loc[:, "is_win"] = ((recent_A["player1"] == player1) & recent_A["is_win_player1"]) | \
                                 ((recent_A["player2"] == player1) & recent_A["is_win_player2"])

    recent_B.loc[:, "is_win"] = ((recent_B["player1"] == player2) & recent_B["is_win_player1"]) | \
                                 ((recent_B["player2"] == player2) & recent_B["is_win_player2"])

    win_A_L10 = recent_A.tail(10)["is_win"].mean() if not recent_A.empty else 0.5
    win_B_L10 = recent_B.tail(10)["is_win"].mean() if not recent_B.empty else 0.5

    win_A_L50 = recent_A.tail(50)["is_win"].mean() if not recent_A.empty else 0.5
    win_B_L50 = recent_B.tail(50)["is_win"].mean() if not recent_B.empty else 0.5

    strength_diff_last50 = abs(win_A_L50 - win_B_L50)

    strength_gap_L10 = abs(win_A_L10 - win_B_L10)
    form_gap_L10 = abs(recent_A_L10 - recent_B_L10)
    match_balance_L10 = form_gap_L10 + strength_gap_L10

    # --- Append features ---
    features.append({
        "match_id": match_id,
        "date": match_date,
        "player1": player1,
        "player2": player2,
        "h2h_L10_weighted": h2h_L10_weighted,
        "h2h_L30_weighted": h2h_L30_weighted,
        "h2h_L60_weighted": h2h_L60_weighted,
        "h2h_L10_count": h2h_count_L10,
        "h2h_L30_count": h2h_count_L30,
        "h2h_L60_count": h2h_count_L60,
        "recent_A_L10": recent_A_L10,
        "recent_B_L10": recent_B_L10,
        "recent_A_L30": recent_A_L30,
        "recent_B_L30": recent_B_L30,
        "match_balance_L10": match_balance_L10,
        "player_A_4plus_rate_last50": player_A_4plus_rate_last50,
        "player_B_4plus_rate_last50": player_B_4plus_rate_last50,
        "strength_diff_last50": strength_diff_last50
    })

    # --- Progress log ---
    if idx % 100 == 0:
        print(f"Processed {idx} matches")

# --- Output CSV ---
features_df = pd.DataFrame(features)
features_df.to_csv("data/tt_czech_historical_features_weighted.csv", index=False)
print("Weighted feature CSV generated: tt_czech_historical_features_weighted.csv")