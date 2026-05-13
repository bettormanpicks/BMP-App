# buildallleagues.py
#
# Offline build script — reads local CSV files directly, never touches Supabase.
# Produces:
#   - tt_all_schedule.csv         (combined schedule for All leagues view)
#   - tt_all_h2h_index.pkl.gz     (slim index for All leagues, scheduled pairs only)
#   - tt_elite_h2h_index.pkl.gz   (slim index for TT Elite, scheduled pairs only)
#   - tt_czech_h2h_index.pkl.gz   (slim index for Czech, scheduled pairs only)
#   - tt_setka_h2h_index.pkl.gz   (slim index for Setka, scheduled pairs only)
#   - tt_cup_h2h_index.pkl.gz     (slim index for TT Cup, scheduled pairs only)
#
# Run this after scraping, then run upload_tt_leagues_to_supabase.py.

import os
import pickle
import gzip
import pandas as pd
from tabletennis.helpers import (
    LEAGUE_FILES,
    normalize_name,
    parse_sets,
    compute_set_wins,
    total_points_match,
    point_spread,
    set_spread,
    build_h2h_index,
    merge_h2h_indexes,
)

DATA_DIR = os.path.join("tabletennis", "data")

# -------------------------
# Step 1: Build combined schedule from local CSVs
# -------------------------
all_schedules = []

for league, paths in LEAGUE_FILES.items():
    schedule_path = paths["schedule"]
    df = pd.read_csv(schedule_path)
    df["league"] = league
    all_schedules.append(df)
    print(f"  {league}: {len(df)} scheduled matches")

combined_schedule = pd.concat(all_schedules, ignore_index=True)
combined_schedule.to_csv(os.path.join(DATA_DIR, "tt_all_schedule.csv"), index=False)
print(f"Combined schedule saved: {len(combined_schedule)} matches\n")

# -------------------------
# Step 2: Build per-league indexes from local matchlog CSVs
# -------------------------
def load_and_index(league, paths):
    """Load local matchlog CSV, clean it, filter to scheduled pairs, build index."""
    # Load schedule for this league to get scheduled pairs
    schedule = pd.read_csv(paths["schedule"])
    if "match_date" in schedule.columns:
        schedule = schedule.rename(columns={"match_date": "date"})
    schedule["player1"] = schedule["player1"].apply(normalize_name)
    schedule["player2"] = schedule["player2"].apply(normalize_name)

    scheduled_pairs = set()
    for _, row in schedule.iterrows():
        key = tuple(sorted([row["player1"], row["player2"]]))
        scheduled_pairs.add(key)

    # Load matchlogs
    matchlogs = pd.read_csv(paths["matchlogs"])
    if "match_date" in matchlogs.columns:
        matchlogs = matchlogs.rename(columns={"match_date": "date"})

    matchlogs["date"] = pd.to_datetime(matchlogs["date"], errors="coerce")
    matchlogs.dropna(subset=["match_id", "date"], inplace=True)

    matchlogs["player1"] = matchlogs["player1"].apply(normalize_name)
    matchlogs["player2"] = matchlogs["player2"].apply(normalize_name)

    # Filter to scheduled pairs only
    before = len(matchlogs)
    matchlogs = matchlogs[
        matchlogs.apply(
            lambda r: tuple(sorted([r["player1"], r["player2"]])) in scheduled_pairs,
            axis=1
        )
    ].copy()
    after = len(matchlogs)
    print(f"  {league}: {before:,} rows -> {after:,} rows after pair filter")

    if matchlogs.empty:
        return scheduled_pairs, {}

    # Parse sets and compute stats
    matchlogs["parsed_sets"] = matchlogs["sets"].apply(parse_sets)
    matchlogs = matchlogs[matchlogs["parsed_sets"].apply(len) > 0].copy()
    matchlogs["sets1"], matchlogs["sets2"] = zip(*matchlogs["parsed_sets"].apply(compute_set_wins))
    matchlogs["ATP"]    = matchlogs["parsed_sets"].apply(total_points_match)
    matchlogs["PS"]     = matchlogs["parsed_sets"].apply(point_spread)
    matchlogs["SS"]     = matchlogs["parsed_sets"].apply(set_spread)
    matchlogs["winner"] = matchlogs.apply(
        lambda r: r["player1"] if r["sets1"] > r["sets2"] else r["player2"],
        axis=1
    )
    matchlogs["four_plus"] = matchlogs["parsed_sets"].apply(lambda x: int(len(x) >= 4))
    matchlogs.sort_values("date", ascending=False, inplace=True)

    h2h_index = build_h2h_index(matchlogs)
    return scheduled_pairs, h2h_index


print("Building per-league indexes...")
all_indexes = []
all_scheduled_pairs = set()

for league, paths in LEAGUE_FILES.items():
    scheduled_pairs, h2h_index = load_and_index(league, paths)
    all_indexes.append(h2h_index)
    all_scheduled_pairs.update(scheduled_pairs)

    # Save per-league slim pickle
    output_path = paths["h2h_index"]
    with gzip.open(output_path, "wb") as f:
        pickle.dump(h2h_index, f)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  {league}: {len(h2h_index):,} pairs saved ({size_kb:.0f}KB)\n")

# -------------------------
# Step 3: Merge and save All leagues index
# -------------------------
print("Building All leagues index...")
combined_h2h_index = merge_h2h_indexes(all_indexes)

before = len(combined_h2h_index)
combined_h2h_index = {k: v for k, v in combined_h2h_index.items() if k in all_scheduled_pairs}
after = len(combined_h2h_index)
total_records = sum(len(v) for v in combined_h2h_index.values())
print(f"Index filtered: {before:,} pairs -> {after:,} pairs ({total_records:,} records)")

output_path = os.path.join(DATA_DIR, "tt_all_h2h_index.pkl.gz")
with gzip.open(output_path, "wb") as f:
    pickle.dump(combined_h2h_index, f)

size_kb = os.path.getsize(output_path) / 1024
print(f"All leagues: {size_kb:.0f}KB compressed")
print("\nDone.")