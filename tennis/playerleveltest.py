import pandas as pd
import numpy as np

# -------------------------
# LOAD DATA
# -------------------------
df = pd.read_csv("data/atp_match_logs.csv")

# Match ID
df["match_id"] = df.index

# Convert date
df["Date"] = pd.to_datetime(df["Date"])

# -------------------------
# STEP 1: Compute total games per match
# -------------------------
set_cols = [("W1","L1"), ("W2","L2"), ("W3","L3"), ("W4","L4"), ("W5","L5")]

def compute_games(row):
    w_games, l_games = 0, 0
    for w, l in set_cols:
        if pd.notna(row[w]) and pd.notna(row[l]):
            w_games += int(row[w])
            l_games += int(row[l])
    return pd.Series([w_games, l_games])

df[["W_games", "L_games"]] = df.apply(compute_games, axis=1)

# Total games
df["total_games"] = df["W_games"] + df["L_games"]

def compute_close_sets(row):
    close_sets = 0
    total_sets = 0
    
    for w, l in set_cols:
        if pd.notna(row[w]) and pd.notna(row[l]):
            total_sets += 1
            if abs(int(row[w]) - int(row[l])) <= 2:
                close_sets += 1
    
    return pd.Series([close_sets, total_sets])

df[["close_sets", "total_sets"]] = df.apply(compute_close_sets, axis=1)

# -------------------------
# SANITY CHECK 1
# -------------------------
print("\n=== SANITY CHECK: RAW MATCH TOTALS ===")
print(df[[
    "Winner","Loser","W_games","L_games","total_games"
]].head(10))

# -------------------------
# STEP 2: Convert to player rows
# -------------------------
winner_df = pd.DataFrame({
    "match_id": df["match_id"],
    "date": df["Date"],
    "player": df["Winner"],
    "opponent": df["Loser"],
    "surface": df["Surface"],
    "games_won": df["W_games"],
    "games_lost": df["L_games"],
    "sets_won": df["Wsets"],
    "sets_lost": df["Lsets"],
    "close_sets": df["close_sets"],
    "total_sets": df["total_sets"],
    "won": 1
})

loser_df = pd.DataFrame({
    "match_id": df["match_id"],
    "date": df["Date"],
    "player": df["Loser"],
    "opponent": df["Winner"],
    "surface": df["Surface"],
    "games_won": df["L_games"],
    "games_lost": df["W_games"],
    "sets_won": df["Lsets"],
    "sets_lost": df["Wsets"],
    "close_sets": df["close_sets"],
    "total_sets": df["total_sets"],
    "won": 0
})

matches = pd.concat([winner_df, loser_df])\
    .sort_values(["date", "match_id"])

# -------------------------
# STEP 3: Derived stats
# -------------------------
matches["game_diff"] = matches["games_won"] - matches["games_lost"]
matches["total_games"] = matches["games_won"] + matches["games_lost"]
matches["is_3set"] = ((matches["sets_won"] + matches["sets_lost"]) == 3).astype(int)

# -------------------------
# SANITY CHECK 2
# -------------------------
print("\n=== SANITY CHECK: PLAYER ROWS ===")
print(matches.head(10))

# -------------------------
# STEP 4: Rolling stats (surface-specific)
# -------------------------
def compute_rolling(group, window=10):
    group = group.sort_values("date")
    
    group["avg_game_diff"] = group["game_diff"].rolling(window).mean()
    group["avg_total_games"] = group["total_games"].rolling(window).mean()
    group["three_set_rate"] = group["is_3set"].rolling(window).mean()

    group["close_set_rate"] = (
        group["close_sets"] / group["total_sets"]
    ).rolling(window).mean()
    
    return group

matches = matches.groupby(["player", "surface"], group_keys=False)\
                 .apply(compute_rolling)

# Shift so we don't use current match
rolling_cols = ["avg_game_diff", "avg_total_games", "three_set_rate"]

matches[rolling_cols] = matches.groupby(["player", "surface"])[rolling_cols].shift(1)

# -------------------------
# SANITY CHECK 3 (CRITICAL)
# -------------------------
print("\n=== SANITY CHECK: ROLLING STATS ===")

sample_player = matches["player"].iloc[0]

print(f"\nSample player: {sample_player}\n")

print(matches[matches["player"] == sample_player][[
    "date",
    "surface",
    "game_diff",
    "avg_game_diff",
    "total_games",
    "avg_total_games",
    "is_3set",
    "three_set_rate"
]].head(15))

# -------------------------
# STEP 5: Matchup reconstruction
# -------------------------
# Merge players back into matches

matchups = matches.merge(
    matches,
    on="match_id",
    suffixes=("_A", "_B")
)

# Remove self joins
matchups = matchups[matchups["player_A"] != matchups["player_B"]]

# Keep only one row per match
matchups = matchups[matchups["won_A"] == 1]

matchups["date"] = matchups["date_A"]

# -------------------------
# STEP 6: Match-level metrics
# -------------------------
matchups["game_diff_diff"] = (
    matchups["avg_game_diff_A"] - matchups["avg_game_diff_B"]
)

matchups["combined_total_games"] = (
    matchups["avg_total_games_A"] + matchups["avg_total_games_B"]
) / 2

matchups["combined_3set_rate"] = (
    matchups["three_set_rate_A"] + matchups["three_set_rate_B"]
) / 2

matchups["combined_close_set_rate"] = (
    matchups["close_set_rate_A"] + matchups["close_set_rate_B"]
) / 2

# -------------------------
# SANITY CHECK 4
# -------------------------
print("\n=== SANITY CHECK: MATCHUPS ===")
print(matchups[[
    "date_A",
    "player_A",
    "player_B",
    "game_diff_diff",
    "combined_total_games",
    "combined_3set_rate"
]].head(10))

# -------------------------
# FINAL SUMMARY
# -------------------------
print("\n=== DATA SUMMARY ===")
print(f"Total matches: {len(df)}")
print(f"Player rows: {len(matches)}")
print(f"Matchups: {len(matchups)}")

# -------------------------
# STEP 7: ANALYSIS
# -------------------------

# Remove rows without rolling stats
analysis_df = matchups.dropna(subset=[
    "game_diff_diff",
    "combined_total_games",
    "combined_3set_rate"
]).copy()

# Actual outcomes
analysis_df["actual_total_games"] = (
    analysis_df["games_won_A"] + analysis_df["games_won_B"]
)

analysis_df["is_over_22_5"] = (analysis_df["actual_total_games"] > 22.5).astype(int)
analysis_df["is_3set"] = (
    (analysis_df["sets_won_A"] + analysis_df["sets_won_B"]) == 3
).astype(int)

print("\n=== ANALYSIS SAMPLE SIZE ===")
print(len(analysis_df))

# -------------------------
# 1. TOTALS vs combined_total_games
# -------------------------
print("\n=== TOTALS: combined_total_games bins ===")

analysis_df["total_bin"] = pd.qcut(
    analysis_df["combined_total_games"], 5, duplicates="drop"
)

print(analysis_df.groupby("total_bin")[[
    "actual_total_games",
    "is_over_22_5"
]].mean())

# -------------------------
# 2. CLOSE MATCHES vs game_diff_diff
# -------------------------
print("\n=== 3-SET RATE: game_diff_diff bins ===")

analysis_df["diff_bin"] = pd.qcut(
    analysis_df["game_diff_diff"], 5, duplicates="drop"
)

print(analysis_df.groupby("diff_bin")[[
    "is_3set",
    "actual_total_games"
]].mean())

# -------------------------
# 3. DIRECT SIGNAL CHECKS
# -------------------------

print("\n=== CORRELATIONS ===")

print(analysis_df[[
    "combined_total_games",
    "game_diff_diff",
    "combined_3set_rate",
    "actual_total_games",
    "is_3set"
]].corr())

# -------------------------
# 4. EXTREMES (this is where edges live)
# -------------------------

print("\n=== HIGH TOTAL SIGNAL ===")

high_totals = analysis_df[analysis_df["combined_total_games"] > 24]
print(high_totals[["actual_total_games", "is_over_22_5"]].mean())

print("\n=== LOW DIFF (CLOSE MATCH) SIGNAL ===")

close_matches = analysis_df[analysis_df["game_diff_diff"].abs() < 1]
print(close_matches[["is_3set", "actual_total_games"]].mean())

print("\n=== BIG DIFF (BLOWOUT) SIGNAL ===")

blowouts = analysis_df[analysis_df["game_diff_diff"].abs() > 4]
print(blowouts[["is_3set", "actual_total_games"]].mean())

# -------------------------
# 5. CLOSE SET SIGNAL
# -------------------------

analysis_df = analysis_df.dropna(subset=["combined_close_set_rate"])

analysis_df["close_set_bin"] = pd.qcut(
    analysis_df["combined_close_set_rate"], 5, duplicates="drop"
)

print("\n=== CLOSE SET RATE SIGNAL ===")
print(analysis_df.groupby("close_set_bin")[[
    "actual_total_games",
    "is_over_22_5"
]].mean())

# -------------------------
# LOAD AND NORMALIZE UPCOMING SCHEDULE
# -------------------------
upcoming = pd.read_csv("data/tennis_schedule_resolved.csv")

# Make sure Date is datetime
upcoming["Date"] = pd.to_datetime(upcoming["Date"])

# Canonical names mapping
players = pd.read_csv("data/tennisplayers.csv")
aliases = pd.read_csv("data/player_aliases.csv")
alias_map = dict(zip(aliases["scoreboard_name"], aliases["canonical_name"]))

# Normalize upcoming player names
upcoming["player_1_canon"] = upcoming["Player 1"].map(lambda x: alias_map.get(x, x))
upcoming["player_2_canon"] = upcoming["Player 2"].map(lambda x: alias_map.get(x, x))

# -------------------------
# MERGE HISTORICAL ROLLING STATS
# -------------------------
# Player 1 stats
upcoming = upcoming.merge(
    matches[["player", "surface", "avg_total_games", "three_set_rate"]],
    left_on=["player_1_canon", "Surface"],
    right_on=["player", "surface"],
    how="left"
).rename(columns={
    "avg_total_games": "avg_total_games_1",
    "three_set_rate": "three_set_rate_1"
}).drop(columns=["player", "surface"])

# Player 2 stats
upcoming = upcoming.merge(
    matches[["player", "surface", "avg_total_games", "three_set_rate"]],
    left_on=["player_2_canon", "Surface"],
    right_on=["player", "surface"],
    how="left"
).rename(columns={
    "avg_total_games": "avg_total_games_2",
    "three_set_rate": "three_set_rate_2"
}).drop(columns=["player", "surface"])

# -------------------------
# COMPUTE COMBINED METRICS
# -------------------------
upcoming["combined_total_games"] = (upcoming["avg_total_games_1"] + upcoming["avg_total_games_2"]) / 2
upcoming["combined_3set_rate"] = (upcoming["three_set_rate_1"] + upcoming["three_set_rate_2"]) / 2

# -------------------------
# INTERPOLATE PROBABILITIES BASED ON HISTORICAL ANALYSIS
# -------------------------
# Make sure analysis_df is sorted
analysis_sorted = analysis_df.sort_values("combined_total_games")

upcoming["prob_over_22_5"] = np.interp(
    upcoming["combined_total_games"],
    analysis_sorted["combined_total_games"].values,
    analysis_sorted["is_over_22_5"].values
)

# -------------------------
# SHOW RESULTS
# -------------------------
print("\n=== UPCOMING MATCH PROBABILITIES ===")
print(upcoming[[
    "Date", "Player 1", "Player 2", "Surface", "prob_over_22_5"
]])