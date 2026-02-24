# resolve_tennis_player.py
import pandas as pd
import re
import os
from name_normalizer import clean_name, generate_name_keys

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
def infer_tour(player_id):
    if player_id.startswith("atp_"):
        return "ATP"
    if player_id.startswith("wta_"):
        return "WTA"
    return None

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

# Log each key generated and which player_id it matched
key_match_log = []  # Will store dicts like {'schedule_name': name, 'key': key, 'player_id': pid, 'matched_by': method}

# ==============================
# BUILD LOOKUPS
# ==============================
# Alias lookup: canonical_name -> player_id
alias_lookup = {}
for _, row in aliases.iterrows():
    keys = generate_name_keys(row['scoreboard_name'])
    for k in keys:
        alias_lookup[k] = row['player_id']

# Player lookup: canonical_name -> player_id
player_lookup = {}
for _, row in players.iterrows():
    keys = generate_name_keys(row['player_name'])
    for k in keys:
        player_lookup[k] = row['player_id']

# Ranking lookup: canonical_name -> (player_id, rank)
ranking_lookup = {}

for _, row in atp_rankings.iterrows():
    keys = generate_name_keys(row['player'])
    for k in keys:
        ranking_lookup[k] = (f"atp_{row['rank']}", row['rank'])

for _, row in wta_rankings.iterrows():
    keys = generate_name_keys(row['player'])
    for k in keys:
        ranking_lookup[k] = (f"wta_{row['rank']}", row['rank'])

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

    global players, aliases, alias_lookup, player_lookup, ranking_lookup, atp_rankings, wta_rankings, new_players_created, key_match_log

    if "/" in name:
        return None  # skip doubles automatically

    # Generate identity keys for the incoming name
    keys = generate_name_keys(name)
    if not keys:
        return None

    n = clean_name(name)  # base cleaned name

    # --------------------------------------------------
    # 1) Alias match
    # --------------------------------------------------
    for k in keys:
        if k in alias_lookup:
            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": alias_lookup[k],
                "matched_by": "alias"
            })
            print(f"[DEBUG] Alias matched: {name} (key: {k}) -> {alias_lookup[k]}")
            return alias_lookup[k]
        else:
            # Log the non-match
            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": None,
                "matched_by": "alias_no_match"
            })

    # --------------------------------------------------
    # 2) Existing players match
    # --------------------------------------------------
    for k in keys:
        if k in player_lookup:
            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": player_lookup[k],
                "matched_by": "player_lookup"
            })
            print(f"[DEBUG] Player lookup matched: {name} (key: {k}) -> {player_lookup[k]}")
            return player_lookup[k]
        else:
            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": None,
                "matched_by": "player_lookup_no_match"
            })

    # --------------------------------------------------
    # 3) Ranking lookup
    # --------------------------------------------------
    tour = None
    new_id = None
    row = None

    for k in keys:
        if k in ranking_lookup:
            ranked_id, rank = ranking_lookup[k]
            tour = "ATP" if ranked_id.startswith("atp_") else "WTA"

            # Pull full ranking row for metadata
            if tour == "ATP":
                match = atp_rankings[atp_rankings['rank'] == rank]
            else:
                match = wta_rankings[wta_rankings['rank'] == rank]

            if not match.empty:
                row = match.iloc[0]

            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": ranked_id,
                "matched_by": "ranking"
            })
            print(f"[DEBUG] Rankings matched: {name} (key: {k}) -> {ranked_id} (rank {rank})")
            return ranked_id
        else:
            key_match_log.append({
                "schedule_name": name,
                "key": k,
                "player_id": None,
                "matched_by": "ranking_no_match"
            })

    # --------------------------------------------------
    # 4) If still unknown → generate new ID
    # --------------------------------------------------
    if new_id is None:
        tour = "ATP"  # fallback
        new_id = generate_new_id(tour, players['player_id'])

    # --------------------------------------------------
    # 5) Add to players and aliases if not already there
    # --------------------------------------------------
    if new_id not in set(players['player_id']):
        # Add to players
        new_row = {
            "player_id": new_id,
            "player_name": name,
            "tour": tour,
            "rank": row['rank'] if row is not None and 'rank' in row else None,
            "points": row['points'] if row is not None and 'points' in row else None,
            "country": row['country'] if row is not None and 'country' in row else None
        }
        players = pd.concat([players, pd.DataFrame([new_row])], ignore_index=True)
        new_players_created.append((name, new_id))

        # Add to aliases
        canonical_key = clean_name(name)  # <-- replaces normalize_name
        new_alias = {
            "scoreboard_name": name,
            "player_id": new_id,
            "canonical_name": canonical_key
        }
        aliases = pd.concat([aliases, pd.DataFrame([new_alias])], ignore_index=True)

        # Update lookup tables
        alias_lookup[canonical_key] = new_id
        player_lookup[canonical_key] = new_id

        # Optional: track which key matched for debugging
        key_match_log.append({
            "schedule_name": name,
            "key": canonical_key,
            "player_id": new_id,
            "matched_by": "generated"
        })

    return new_id

# ==============================
# PROCESS SCHEDULE
# ==============================
total_processed = 0
matched = 0
unmatched = []

# Create new columns for player IDs
schedule['player_id'] = None
schedule['opponent_id'] = None

for idx, row in schedule.iterrows():
    for col, id_col in [("Player 1", "player_id"), ("Player 2", "opponent_id")]:
        name = row[col]
        pid = resolve_player(name)
        total_processed += 1
        if pid is not None:
            matched += 1
            # Assign resolved player_id into new column
            schedule.at[idx, id_col] = pid
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

# Save key-to-player_id log
if key_match_log:
    log_df = pd.DataFrame(key_match_log)
    log_df.to_csv("data/key_match_log.csv", index=False)

# Save updated players and aliases
players.to_csv(PLAYERS_FILE, index=False)
aliases.to_csv(ALIASES_FILE, index=False)

schedule["Tour"] = schedule["player_id"].apply(infer_tour)

if (
    schedule["player_id"].fillna("").str[:3] 
    != schedule["opponent_id"].fillna("").str[:3]
).any():
    print("WARNING: Mixed tours detected")

tournaments = pd.read_csv("data/tournament_list.csv", dtype=str)

tournaments["Tournament"] = tournaments["Tournament"].str.strip().str.lower()
schedule["Tournament_clean"] = schedule["Tournament"].str.strip().str.lower()

schedule = schedule.merge(
    tournaments[["Tournament","Surface"]],
    left_on="Tournament_clean",
    right_on="Tournament",
    how="left"
)

schedule.drop(columns=["Tournament_clean","Tournament_y"], inplace=True, errors="ignore")
schedule.rename(columns={"Tournament_x":"Tournament"}, inplace=True)

missing_surface = schedule["Surface"].isna().sum()
print(f"Missing surface count: {missing_surface}")

# ==============================
# DEDUPLICATE MATCHES
# ==============================
# Consider a match duplicate if Date, Time, Tournament, Player 1, and Player 2 are identical
schedule = schedule.drop_duplicates(
    subset=["Date", "Time", "Tournament", "Player 1", "Player 2"],
    keep="first"
)
print(f"Total matches after deduplication: {len(schedule)}")

# ==============================
# SAVE RESOLVED SCHEDULE
# ==============================
schedule.to_csv("data/tennis_schedule_resolved.csv", index=False)

# Print new players added
if new_players_created:
    print("New players created:")
    for n, pid in new_players_created:
        print(f"{n} -> {pid}")