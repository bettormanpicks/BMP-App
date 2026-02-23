# resolve_tennis_player.py
import pandas as pd
import re
import os

# ==============================
# CONFIG
# ==============================
PLAYERS_FILE = "data/tennisplayers.csv"
ALIASES_FILE = "data/player_aliases.csv"
ATP_RANKINGS_FILE = "data/atp_rankings.csv"
WTA_RANKINGS_FILE = "data/wta_rankings.csv"
SCHEDULE_FILE = "data/tennis_schedule.csv"
UNMATCHED_FILE = "data/unmatched_singles.txt"

# starting point for new unknown IDs
ATP_NEW_START = 9100
WTA_NEW_START = 9100

# ==============================
# HELPERS
# ==============================
def normalize_name(name):
    """Lowercase, remove periods, accents, extra spaces"""
    name = name.lower()
    name = re.sub(r"[.\']", "", name)
    name = name.strip()
    return name

def generate_new_id(tour, existing_ids):
    """Generate a new player_id above the 9000 threshold"""
    prefix = "atp" if tour == "ATP" else "wta"
    nums = [int(x.split("_")[1]) for x in existing_ids if x.startswith(prefix)]
    start = ATP_NEW_START if tour == "ATP" else WTA_NEW_START
    next_id = max(nums + [start - 1]) + 1
    return f"{prefix}_{next_id}"

# ==============================
# LOAD DATA
# ==============================
players = pd.read_csv(PLAYERS_FILE)
aliases = pd.read_csv(ALIASES_FILE)

atp_rankings = pd.read_csv(ATP_RANKINGS_FILE)
wta_rankings = pd.read_csv(WTA_RANKINGS_FILE)
schedule = pd.read_csv(SCHEDULE_FILE)

# ==============================
# BUILD LOOKUPS
# ==============================
# Alias lookup: canonical_name -> player_id
alias_lookup = {}
for _, row in aliases.iterrows():
    n = normalize_name(row['scoreboard_name'])
    alias_lookup[n] = row['player_id']

# Player lookup: canonical_name -> player_id
player_lookup = {}
for _, row in players.iterrows():
    n = normalize_name(row['player_name'])
    player_lookup[n] = row['player_id']

# Ranking lookup: canonical_name -> (player_id, rank)
ranking_lookup = {}

for _, row in atp_rankings.iterrows():
    n = normalize_name(row['player'])
    pid = f"atp_{row['rank']}"
    ranking_lookup[n] = (pid, row['rank'])

for _, row in wta_rankings.iterrows():
    n = normalize_name(row['player'])
    pid = f"wta_{row['rank']}"
    ranking_lookup[n] = (pid, row['rank'])

# ==============================
# RESOLVE FUNCTION
# ==============================
new_players_created = []

def resolve_player(name):
    """
    Resolve a player name to player_id.
    - Skips doubles automatically.
    - Checks alias lookup first.
    - Checks existing players next.
    - Checks ATP/WTA rankings to assign rank-aligned IDs.
    - Falls back to new generated ID if completely unknown.
    """
    global players, aliases, alias_lookup, player_lookup, atp_rankings, wta_rankings, new_players_created

    if "/" in name:
        return None  # skip doubles automatically

    n = normalize_name(name)

    # 1) Check alias
    if n in alias_lookup:
        return alias_lookup[n]

    # 2) Check existing players
    if n in player_lookup:
        return player_lookup[n]

    # 3) Check ATP/WTA rankings
    tour = None
    new_id = None

    # Check ATP rankings
    match = atp_rankings[atp_rankings['player'].apply(lambda x: normalize_name(x) == n)]
    if not match.empty:
        row = match.iloc[0]
        tour = "ATP"
        new_id = f"atp_{row['rank']}"

    # Check WTA rankings
    else:
        match = wta_rankings[wta_rankings['player'].apply(lambda x: normalize_name(x) == n)]
        if not match.empty:
            row = match.iloc[0]
            tour = "WTA"
            new_id = f"wta_{row['rank']}"

    # 4) If still unknown → generate new ID
    if new_id is None:
        tour = "ATP"  # fallback
        new_id = generate_new_id(tour, players['player_id'])

    # Add to players if not already there
    if new_id not in set(players['player_id']):
        new_row = {
            "player_id": new_id,
            "player_name": name,
            "tour": tour,
            "rank": row['rank'] if 'row' in locals() else None,
            "points": row['points'] if 'row' in locals() and 'points' in row else None,
            "country": row['country'] if 'row' in locals() and 'country' in row else None
        }
        players = pd.concat([players, pd.DataFrame([new_row])], ignore_index=True)
        new_players_created.append((name, new_id))

    # Add to aliases
    new_alias = {
        "scoreboard_name": name,
        "player_id": new_id,
        "canonical_name": n
    }
    aliases = pd.concat([aliases, pd.DataFrame([new_alias])], ignore_index=True)

    # Update lookups
    alias_lookup[n] = new_id
    player_lookup[n] = new_id

    return new_id

# ==============================
# PROCESS SCHEDULE
# ==============================
total_processed = 0
matched = 0
unmatched = []

for idx, row in schedule.iterrows():
    for col in ["Player 1", "Player 2"]:
        name = row[col]
        pid = resolve_player(name)
        total_processed += 1
        if pid is not None:
            matched += 1
        else:
            unmatched.append(name)

# ==============================
# OUTPUT RESULTS
# ==============================
print(f"Total names processed: {total_processed}")
print(f"Matched names: {matched}")
print(f"Unmatched singles ({len(unmatched)}): {unmatched}")

if unmatched:
    pd.Series(unmatched).to_csv(UNMATCHED_FILE, index=False, header=False)

# Save updated players and aliases
players.to_csv(PLAYERS_FILE, index=False)
aliases.to_csv(ALIASES_FILE, index=False)

# Print new players added
if new_players_created:
    print("New players created:")
    for n, pid in new_players_created:
        print(f"{n} -> {pid}")