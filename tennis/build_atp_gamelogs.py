import pandas as pd
import unicodedata

# ========================
# CONFIG
# ========================
PLAYERS_FILE = "data/tennisplayers.csv"
MATCH_FILE = "data/atp_match_logs.csv"
OUTPUT_FILE = "data/atp_player_gamelogs.csv"


# ------------------------
# Normalize names (from tennisplayers pipeline)
# ------------------------
def normalize_name(name: str) -> str:
    if pd.isna(name):
        return ""
    # remove accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    # lowercase
    name = name.lower()
    # remove punctuation (dots, commas, apostrophes, hyphens)
    name = name.replace(".", "").replace(",", "").replace("'", "").replace("-", " ")
    # collapse spaces
    name = " ".join(name.split())
    return name


# ------------------------
# Build lookup: "last first_initial" -> player_id
# ------------------------
def build_player_lookup(players_df):
    lookup = {}

    for _, row in players_df.iterrows():
        if row["tour"] != "ATP":
            continue

        player_id = row["player_id"]
        full_name = normalize_name(row["player_name"])
        parts = full_name.split()
        if len(parts) < 2:
            continue

        first = parts[0]
        last = parts[-1]

        key = f"{last} {first[0]}"
        lookup[key] = player_id

    return lookup


# ------------------------
# Convert scoreboard name -> player_id
# ------------------------
def resolve_scoreboard_name(name, lookup):
    name = normalize_name(name)
    parts = name.split()
    if len(parts) < 2:
        return None

    first = parts[0]
    last = parts[-1]

    key = f"{last} {first[0]}"
    pid = lookup.get(key)
    if not pid:
        print(f"Unmatched scoreboard name: '{name}' -> key '{key}'")
    return pid


# ------------------------
# Load players
# ------------------------
print("Loading players...")
players = pd.read_csv(PLAYERS_FILE)
player_lookup = build_player_lookup(players)
print("ATP players indexed:", len(player_lookup))


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
        continue  # skip unmatched

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