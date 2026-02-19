import pandas as pd
import re

# ========================
# CONFIG
# ========================
PLAYERS_FILE = "tennisplayers.csv"
MATCH_FILE = "wta_matches_2025.csv"
OUTPUT_FILE = "wta_player_gamelogs.csv"


# ------------------------
# Name normalization
# ------------------------
def normalize(text):
    if pd.isna(text):
        return ""
    text = text.lower()
    text = text.replace(".", "")
    text = re.sub(r"[^a-z ]", "", text)
    text = " ".join(text.split())
    return text


# ------------------------
# Build lookup: "osaka n" -> player_id
# ------------------------
def build_player_lookup(players_df):
    lookup = {}

    for _, row in players_df.iterrows():
        if row["tour"] != "WTA":
            continue

        player_id = row["player_id"]
        full_name = normalize(row["player_name"])

        parts = full_name.split()
        if len(parts) < 2:
            continue

        first = parts[0]
        last = parts[-1]

        key = f"{last} {first[0]}"
        lookup[key] = player_id

    return lookup


# ------------------------
# Convert "Osaka N." -> player_id
# ------------------------
def resolve_scoreboard_name(name, lookup):
    name = normalize(name)

    parts = name.split()
    if len(parts) < 2:
        return None

    last = parts[0]
    first_initial = parts[1][0]

    key = f"{last} {first_initial}"

    return lookup.get(key)


# ------------------------
# Load players
# ------------------------
print("Loading players...")
players = pd.read_csv(PLAYERS_FILE)

player_lookup = build_player_lookup(players)
print("WTA players indexed:", len(player_lookup))


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

    p1_id = resolve_scoreboard_name(m["Winner"], player_lookup)
    p2_id = resolve_scoreboard_name(m["Loser"], player_lookup)

    if not p1_id or not p2_id:
        continue

    # --- games won/lost ---
    p1_games = 0
    p2_games = 0

    for s in range(1, 4):
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
