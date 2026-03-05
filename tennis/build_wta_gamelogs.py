import pandas as pd
import os
from helpers.player_utils import get_wta_player_id

# ==============================
# BASE DIRECTORY (robust path fix)
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ========================
# CONFIG
# ========================
PLAYERS_FILE = os.path.join(DATA_DIR, "tennisplayers.csv")
MATCH_FILE = os.path.join(DATA_DIR, "wta_match_logs.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "wta_player_gamelogs.csv")


# ------------------------
# Load players
# ------------------------
print("Loading players...")


# ------------------------
# Load matches
# ------------------------
print("Loading matches...")
matches = pd.read_csv(MATCH_FILE, low_memory=False)

rows = []

# ------------------------
# Process matches
# ------------------------
for _, m in matches.iterrows():
    p1_id = get_wta_player_id(m["Winner"])
    p2_id = get_wta_player_id(m["Loser"])

    if not p1_id:
        print("ADD ALIAS:", m["Winner"])

    if not p2_id:
        print("ADD ALIAS:", m["Loser"])

    if not p1_id or not p2_id:
        continue

    # --- games won/lost ---
    p1_games = 0
    p2_games = 0
    for s in range(1, 6):  # handle best of 3/5 sets
        w_col = f"W{s}"
        l_col = f"L{s}"
        if w_col in m and l_col in m:
            try:
                w = int(m[w_col])
                l = int(m[l_col])
                p1_games += w
                p2_games += l
            except:
                pass

    # ensure integers
    p1_games = int(p1_games)
    p2_games = int(p2_games)

    p1_diff = p1_games - p2_games
    p2_diff = p2_games - p1_games
    total_games = p1_games + p2_games

    match_date = pd.to_datetime(m["Date"], errors="coerce")
    match_date = match_date.strftime("%Y-%m-%d")

    # --- player 1 ---
    rows.append({
        "player_id": p1_id,
        "opponent": p2_id,
        "game_date": match_date,
        "games_won": p1_games,
        "games_lost": p2_games,
        "game_diff": p1_diff,
        "total_games": total_games,
        "aces": None,
        "double_faults": None,
        "match_win": 1,
        "tourney_name": m.get("Tournament"),
        "tourney_level": m.get("Tier"),
        "surface": m.get("Surface"),
        "round": m.get("Round")
    })

    # --- player 2 ---
    rows.append({
        "player_id": p2_id,
        "opponent": p1_id,
        "game_date": match_date,
        "games_won": p2_games,
        "games_lost": p1_games,
        "game_diff": p2_diff,
        "total_games": total_games,
        "aces": None,
        "double_faults": None,
        "match_win": 0,
        "tourney_name": m.get("Tournament"),
        "tourney_level": m.get("Tier"),
        "surface": m.get("Surface"),
        "round": m.get("Round")
    })

# ------------------------
# Save
# ------------------------
gamelogs = pd.DataFrame(rows)
gamelogs.to_csv(OUTPUT_FILE, index=False)

print("Done.")
print("Player games created:", len(gamelogs))
