import pandas as pd
import unicodedata

# ========================
# CONFIG
# ========================
PLAYERS_FILE = "tennisplayers.csv"
MATCH_FILE = "wta_matches_2025.csv"  # your WTA CSV
OUTPUT_FILE = "wta_player_gamelogs.csv"


# ------------------------
# Helper functions
# ------------------------
def norm_name(name):
    """Normalize a name string (remove accents, extra spaces)."""
    if pd.isna(name):
        return ""
    name = unicodedata.normalize("NFKD", str(name))
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.replace("-", " ")
    name = " ".join(name.split())
    return name.lower()


def make_key(full_name):
    """
    Create last name + first initial key for matching:
    e.g., "Naomi Osaka" -> "osakan"
    """
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ""
    last = parts[-1].lower()
    first_initial = parts[0][0].lower()
    return last + first_initial


# ------------------------
# Load players
# ------------------------
print("Loading players...")
players = pd.read_csv(PLAYERS_FILE)

# Only WTA players
players = players[players["tour"] == "WTA"]

# Build lookup table keyed by last+initial
player_lookup = {make_key(norm_name(row.player_name)): row.player_id
                 for _, row in players.iterrows()}

# ------------------------
# Load matches
# ------------------------
print("Loading matches...")
matches = pd.read_csv(MATCH_FILE, low_memory=False)

rows = []

for _, m in matches.iterrows():
    # Get player names from CSV
    p1_name = norm_name(m["Winner"])
    p2_name = norm_name(m["Loser"])

    # Convert to key
    p1_key = "".join([x.lower() for x in p1_name.split()[-1]] + [p1_name[0].lower()])
    p2_key = "".join([x.lower() for x in p2_name.split()[-1]] + [p2_name[0].lower()])

    # Lookup player_id
    p1_id = player_lookup.get(p1_key)
    p2_id = player_lookup.get(p2_key)

    if not p1_id or not p2_id:
        continue

    # ------------------------
    # Compute games won/lost
    # ------------------------
    # Matches are best of 3 sets
    p1_games = 0
    p2_games = 0
    for s in range(1, 4):
        w_col = f"W{s}"
        l_col = f"L{s}"
        try:
            w = int(m[w_col])
            l = int(m[l_col])
            p1_games += w
            p2_games += l
        except:
            pass

    # ------------------------
    # Double faults
    # ------------------------
    p1_df = m.get("BFEW", 0)
    p2_df = m.get("BFEL", 0)

    # ------------------------
    # Add both players
    # ------------------------
    rows.append({
        "player_id": p1_id,
        "opponent": p2_id,
        "match_date": m["Date"],
        "games_won": p1_games,
        "games_lost": p2_games,
        "aces": None,  # Not in this CSV
        "double_faults": p1_df,
        "match_win": 1,
        "tourney_name": m.get("Tournament"),
        "tourney_level": m.get("Tier"),
        "surface": m.get("Surface"),
        "round": m.get("Round")
    })

    rows.append({
        "player_id": p2_id,
        "opponent": p1_id,
        "match_date": m["Date"],
        "games_won": p2_games,
        "games_lost": p1_games,
        "aces": None,
        "double_faults": p2_df,
        "match_win": 0,
        "tourney_name": m.get("Tournament"),
        "tourney_level": m.get("Tier"),
        "surface": m.get("Surface"),
        "round": m.get("Round")
    })

# ------------------------
# Save gamelogs
# ------------------------
gamelogs = pd.DataFrame(rows)
gamelogs.to_csv(OUTPUT_FILE, index=False)

print("Done.")
print("Player games created:", len(gamelogs))
