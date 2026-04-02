import pandas as pd
from collections import defaultdict

# ----------------------------
# 1️⃣ Load master WTA player list
# ----------------------------
# Format: Rank, Player, Country, Birthdate
# Strip extra spaces in column names and data
wta_master = pd.read_csv("data/wta_players.csv", sep=None, engine='python')
wta_master.columns = wta_master.columns.str.strip()
wta_master['Player'] = wta_master['Player'].str.strip()

# Standardize full name column
wta_master['full_name'] = wta_master['Player']

# Assign a unique player_id
wta_master['player_id'] = ["wta_" + str(i+1) for i in range(len(wta_master))]

# ----------------------------
# 2️⃣ Create canonical_name and display_name
# ----------------------------
def canonicalize(name):
    """Return lowercase last name + first initial."""
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0].lower()
    first, last = parts[0], parts[-1]
    return f"{last.lower()} {first[0].lower()}."

def display_name(name):
    """Return standard display name: F. Last"""
    parts = name.strip().split()
    if len(parts) == 1:
        return name
    first, last = parts[0], parts[-1]
    return f"{first[0]}. {last}"

wta_master['canonical_name'] = wta_master['full_name'].apply(canonicalize)
wta_master['display_name'] = wta_master['full_name'].apply(display_name)

# ----------------------------
# 3️⃣ Extract variants from match logs
# ----------------------------
match_logs = pd.read_csv("data/wta_match_logs.csv")

# Strip extra whitespace from match log names
match_logs['Winner'] = match_logs['Winner'].str.strip()
match_logs['Loser'] = match_logs['Loser'].str.strip()

# Collect all unique player names from logs
all_names = pd.concat([match_logs['Winner'], match_logs['Loser']]).unique()

# Build variants dict: full_name → set of variants
variants_dict = defaultdict(set)

for name in all_names:
    name_lower = name.lower()
    # Attempt to find a match in master list by canonical_name
    matched = wta_master[wta_master['canonical_name'] == canonicalize(name)]
    if not matched.empty:
        full_name = matched.iloc[0]['full_name']
        variants_dict[full_name].add(name.strip())

# Convert to comma-separated string
wta_master['variants'] = wta_master['full_name'].apply(
    lambda fn: ",".join(sorted(variants_dict.get(fn, [])))
)

# ----------------------------
# 4️⃣ Save final player database
# ----------------------------
wta_master = wta_master[['player_id', 'canonical_name', 'display_name', 'variants', 'full_name']]
wta_master.to_csv("data/wta_player_database.csv", index=False)

print(f"✅ Created wta_player_database.csv with {len(wta_master)} players.")