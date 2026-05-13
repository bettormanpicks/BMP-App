# buildallleagues.py
import os
import pickle
import pandas as pd
from tabletennis.helpers import load_tt_raw_data, merge_h2h_indexes, LEAGUE_FILES, normalize_name
import gzip

# Clear cached data so we always fetch fresh CSVs from Supabase
load_tt_raw_data.clear()

DATA_DIR = os.path.join("tabletennis", "data")

# -------------------------
# Step 1: Build combined schedule (unchanged from original)
# -------------------------
all_schedules = []
all_indexes = []

for league in LEAGUE_FILES:
    schedule, _, _, h2h_index = load_tt_raw_data(league)
    schedule = schedule.copy()
    schedule["league"] = league
    # Restore display names from the display columns before saving
    schedule["player1"] = schedule["player1_display"]
    schedule["player2"] = schedule["player2_display"]
    all_schedules.append(schedule)
    all_indexes.append(h2h_index)

combined_schedule = pd.concat(all_schedules, ignore_index=True)
combined_schedule.to_csv(os.path.join(DATA_DIR, "tt_all_schedule.csv"), index=False)
print(f"Combined schedule saved: {len(combined_schedule)} matches")

# -------------------------
# Step 2: Build set of scheduled pair keys from today's schedule
# (normalized names, same as how they appear in the h2h_index)
# -------------------------
scheduled_pairs = set()
for _, row in combined_schedule.iterrows():
    p1 = normalize_name(str(row["player1"]))
    p2 = normalize_name(str(row["player2"]))
    key = tuple(sorted([p1, p2]))
    scheduled_pairs.add(key)

print(f"Unique pairs on schedule: {len(scheduled_pairs)}")

# -------------------------
# Step 3: Merge indexes but keep only scheduled pairs
# -------------------------
combined_h2h_index = merge_h2h_indexes(all_indexes)

before = len(combined_h2h_index)
combined_h2h_index = {k: v for k, v in combined_h2h_index.items() if k in scheduled_pairs}
after = len(combined_h2h_index)
total_records = sum(len(v) for v in combined_h2h_index.values())

print(f"Index filtered: {before:,} pairs -> {after:,} pairs ({total_records:,} match records)")

# -------------------------
# Step 4: Save (same as original)
# -------------------------
with gzip.open(os.path.join(DATA_DIR, "tt_all_h2h_index.pkl.gz"), "wb") as f:
    pickle.dump(combined_h2h_index, f)

print("Done.")