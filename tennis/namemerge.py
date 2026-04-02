import pandas as pd

# Load data
player_db = pd.read_csv("data/atp_player_database.csv")
schedule = pd.read_csv("data/tennis_schedule_resolved.csv")

# Build a mapping of all variants → full_name
variant_to_full = {}

for _, row in schedule.iterrows():
    for name in [row['Player 1'], row['Player 2']]:
        key = name.lower().strip()
        variant_to_full[key] = name

# Also include canonical, display, and variants from player_db
def get_variants(row):
    vars_list = [row['canonical_name'], row['display_name']]
    if pd.notna(row['variants']):
        vars_list += [v.strip() for v in str(row['variants']).split(',')]
    return [v.lower() for v in vars_list]

# Match each player row to schedule full name
full_names = []
for _, row in player_db.iterrows():
    matched = None
    for var in get_variants(row):
        if var in variant_to_full:
            matched = variant_to_full[var]
            break
    full_names.append(matched)

player_db['full_name'] = full_names
player_db.to_csv("data/atp_player_database_updated.csv", index=False)

print("✅ Full names updated where matches found")