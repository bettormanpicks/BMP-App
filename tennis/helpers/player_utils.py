# helpers/player_utils.py
import re
from fuzzywuzzy import process

# =====================================================
# 1️⃣ Master player list
# =====================================================
# This should come from your consolidated CSV with stable player IDs
# Example structure:
# player_id,first_name,last_name,tour
# 101,Alex,Vukic,ATP
# 102,David,Goffin,ATP
# 201,Ons,Jabeur,WTA
import pandas as pd

PLAYER_MASTER_FILE = "data/tennisplayers.csv"
player_df = pd.read_csv(PLAYER_MASTER_FILE)

# Build mapping: normalized_name -> player_id
# Normalized names are: Last + FirstInitial (dots removed)
player_mapping = {}

def normalize_name(name: str) -> str:
    """
    Normalize scoreboard names to 'Last FirstInitial' without punctuation.
    Handles multi-word last names, initials, and removes dots/apostrophes for matching.
    """
    if not isinstance(name, str):
        return ""
    
    name = name.strip()
    # Remove extra dots and apostrophes for safer matching
    name_clean = re.sub(r"[.'’]", "", name)
    
    # Split into parts
    parts = name_clean.split()
    if len(parts) == 1:
        return parts[0].title()
    
    # Last name is everything except the last part (assume last part is initial)
    last = " ".join(parts[:-1]).title()
    first_initial = parts[-1][0].upper()  # Take first character
    return f"{last} {first_initial}"

# Populate the mapping
for _, row in player_df.iterrows():
    last = row['last_name'].title()
    first_initial = row['first_name'][0].upper()
    norm_name = f"{last} {first_initial}"
    player_mapping[norm_name] = row['player_id']

# =====================================================
# 2️⃣ Name resolution function
# =====================================================
def get_player_id(log_name: str, fuzzy: bool = True) -> int | None:
    """
    Return player_id from a scoreboard name.
    If fuzzy=True, fallback to fuzzy matching for typos.
    """
    if pd.isna(log_name) or not log_name.strip():
        return None

    norm_name = normalize_name(log_name)
    
    # Exact match first
    if norm_name in player_mapping:
        return player_mapping[norm_name]
    
    if fuzzy:
        # Use fuzzy matching as last resort
        best_match, score = process.extractOne(norm_name, player_mapping.keys())
        if score >= 90:  # tweak threshold if needed
            return player_mapping[best_match]

    # Not found
    print(f"[WARN] Player not found: '{log_name}' (normalized: '{norm_name}')")
    return None

# =====================================================
# 3️⃣ Optional helper for ETL scripts
# =====================================================
def resolve_match_row(row):
    """Apply get_player_id to Winner and Loser columns in a match row"""
    row['winner_id'] = get_player_id(row['Winner'])
    row['loser_id'] = get_player_id(row['Loser'])
    return row