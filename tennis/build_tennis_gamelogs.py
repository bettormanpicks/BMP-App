import pandas as pd
import unicodedata

# -------------------------------
# Config
# -------------------------------
MATCH_FILE = "atp_matches_2025.csv"
PLAYERS_FILE = "tennisplayers.csv"
OUTPUT_FILE = "tennis_player_gamelogs.csv"

# -------------------------------
# Utilities
# -------------------------------
def norm(name):
    """Normalize player names for consistent lookup."""
    if pd.isna(name):
        return ""
    name = unicodedata.normalize("NFKD", str(name))
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.replace("-", " ")
    name = " ".join(name.split())
    return name.lower()

def parse_tourney_date(date_int):
    """Convert YYYYMMDD numeric date to pandas datetime."""
    return pd.to_datetime(str(int(date_int)), format="%Y%m%d")

# -------------------------------
# Load Players
# -------------------------------
print("Loading players...")
players = pd.read_csv(PLAYERS_FILE)
player_lookup = {norm(row.player_name): row.player_id for _, row in players.iterrows()}

# -------------------------------
# Load Matches
# -------------------------------
print("Loading matches...")
matches = pd.read_csv(MATCH_FILE)

rows = []

for _, m in matches.iterrows():
    # Normalize player names
    winner_name = norm(m["winner_name"])
    loser_name = norm(m["loser_name"])

    # Skip if player not in master list
    if winner_name not in player_lookup or loser_name not in player_lookup:
        continue

    winner_id = player_lookup[winner_name]
    loser_id = player_lookup[loser_name]

    # Convert tourney_date to datetime
    match_date = parse_tourney_date(m["tourney_date"])

    # Compute games won/lost using winner/loser games stats if available
    # Fallback: estimate from score string could be added later
    try:
        games_won_w = float(m.get("w_SvGms", 0))
        games_lost_w = float(m.get("l_SvGms", 0))
        games_won_l = float(m.get("l_SvGms", 0))
        games_lost_l = float(m.get("w_SvGms", 0))
    except:
        games_won_w = games_lost_w = games_won_l = games_lost_l = 0

    # Winner gamelog
    rows.append({
        "player_id": winner_id,
        "opponent": loser_id,
        "match_date": match_date,
        "games_won": games_won_w,
        "games_lost": games_lost_w,
        "aces": m.get("w_ace", 0),
        "double_faults": m.get("w_df", 0),
        "match_win": 1,
        "tourney_name": m.get("tourney_name", ""),
        "tourney_level": m.get("tourney_level", ""),
        "surface": m.get("surface", ""),
        "round": m.get("round", "")
    })

    # Loser gamelog
    rows.append({
        "player_id": loser_id,
        "opponent": winner_id,
        "match_date": match_date,
        "games_won": games_won_l,
        "games_lost": games_lost_l,
        "aces": m.get("l_ace", 0),
        "double_faults": m.get("l_df", 0),
        "match_win": 0,
        "tourney_name": m.get("tourney_name", ""),
        "tourney_level": m.get("tourney_level", ""),
        "surface": m.get("surface", ""),
        "round": m.get("round", "")
    })

# -------------------------------
# Build DataFrame and Save
# -------------------------------
gamelogs = pd.DataFrame(rows)
gamelogs = gamelogs.sort_values("match_date")
gamelogs.to_csv(OUTPUT_FILE, index=False)

print("Done.")
print("Player games created:", len(gamelogs))
