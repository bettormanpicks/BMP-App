import pandas as pd
import re

# ----------------------------
# Load player database
# ----------------------------
player_db = pd.read_csv("data/atp_player_database.csv")

# ----------------------------
# Normalize canonical names
# ----------------------------
def normalize_name_for_mapping(name):
    """Normalize to 'last_name first_initial.' to match DB."""
    name = str(name).lower().strip()
    # Remove hyphens and punctuation (except spaces)
    name = re.sub(r"[-']", " ", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    parts = name.split()
    if len(parts) >= 2:
        last_name = " ".join(parts[:-1])
        # Take only the **first letter** of the first initial part
        first_initial = parts[-1][0]
        return f"{last_name} {first_initial}."
    return name

# Apply normalization to DB
player_db["canonical_name_norm"] = player_db["canonical_name"].apply(normalize_name_for_mapping)

# Build lookup: canonical_name_norm → player_id
canonical_to_id = dict(zip(player_db["canonical_name_norm"], player_db["player_id"]))

# ----------------------------
# Alias map for true exceptions
# ----------------------------
alias_map = {
    "o connell c.": "oconnell c.",
    "mpetshi g.": "mpetshi perricard g.",
    "auger aliassime f.": "augeraliassime f.",  # hyphen in DB removed
    # Add any other real exceptions here
}

# ----------------------------
# Load match logs
# ----------------------------
match_logs = pd.read_csv("data/atp_match_logs.csv")

# ----------------------------
# Apply canonical + alias
# ----------------------------
def canonicalize_with_alias(name):
    canonical = normalize_name_for_mapping(name)
    return alias_map.get(canonical, canonical)

match_logs["winner_canonical"] = match_logs["Winner"].apply(canonicalize_with_alias)
match_logs["loser_canonical"] = match_logs["Loser"].apply(canonicalize_with_alias)

# Map to player IDs
match_logs["winner_id"] = match_logs["winner_canonical"].map(canonical_to_id)
match_logs["loser_id"] = match_logs["loser_canonical"].map(canonical_to_id)

# ----------------------------
# Debug unmatched names
# ----------------------------
missing_winners = match_logs[match_logs["winner_id"].isna()]["Winner"].drop_duplicates()
missing_losers = match_logs[match_logs["loser_id"].isna()]["Loser"].drop_duplicates()

print(f"Missing winners: {len(missing_winners)}")
print(f"Missing losers: {len(missing_losers)}")

if len(missing_winners) > 0:
    print("Sample missing winners:", missing_winners.head(10).tolist())

if len(missing_losers) > 0:
    print("Sample missing losers:", missing_losers.head(10).tolist())

# Suggest new alias_map entries only for real unmatched names
all_missing = pd.concat([missing_winners, missing_losers]).unique()
print("\n--- SUGGESTED alias_map ENTRIES ---")
for name in all_missing[:20]:
    normalized = normalize_name_for_mapping(name)
    if normalized not in canonical_to_id and normalized not in alias_map:
        print(f'"{normalized}": "",')

# ----------------------------
# Save updated match logs
# ----------------------------
match_logs.to_csv("data/atp_match_logs_with_ids.csv", index=False)
print("✅ Match logs updated with player IDs")