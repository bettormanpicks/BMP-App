import pandas as pd

OUTPUT_CSV = "data/mlb_cleaned_boxscores.csv"

box_2025 = pd.read_csv("data/2025boxscores.csv")
box_2026 = pd.read_csv("data/2026boxscores.csv")

# Combine
box = pd.concat([box_2025, box_2026], ignore_index=True)

# Add AB
box["at_bats"] = (
    box["plate_appearances"].fillna(0)
    - box["walks"].fillna(0)
).clip(lower=0)

# Remove duplicates
box = box.drop_duplicates(subset=["game_id", "player_id"], keep="last")

# -------------------------
# ADD OPPOSING PITCHER
# -------------------------
starters = box[
    (box["is_pitcher"] == True) &
    (box["is_starter"] == True)
][["game_id", "team", "player"]]

starters = starters.rename(columns={"player": "starting_pitcher"})

box = box.merge(
    starters,
    left_on=["game_id", "opponent"],
    right_on=["game_id", "team"],
    how="left",
    suffixes=("", "_opp")
)

box.rename(columns={"starting_pitcher": "opposing_pitcher"}, inplace=True)
box.drop(columns=["team_opp"], inplace=True)

# Fill missing
box["opposing_pitcher"] = box["opposing_pitcher"].fillna("Unknown")

# -------------------------
# CLEAN TYPES
# -------------------------
box["date"] = pd.to_datetime(box["date"])

box = box.sort_values(["date", "game_id", "team"]).reset_index(drop=True)

# -------------------------
# SAVE
# -------------------------
box.to_csv(OUTPUT_CSV, index=False)

print(f"Saved {len(box)} rows to {OUTPUT_CSV}")