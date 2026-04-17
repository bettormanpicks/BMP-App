# buildallleagues.py
import os
import pickle
import pandas as pd
from tabletennis.helpers import load_tt_raw_data, merge_h2h_indexes, LEAGUE_FILES
import gzip

DATA_DIR = os.path.join("tabletennis", "data")

all_schedules = []
all_indexes = []

for league in LEAGUE_FILES:
    schedule, _, _, h2h_index = load_tt_raw_data(league)
    schedule = schedule.copy()
    schedule["league"] = league
    all_schedules.append(schedule)
    all_indexes.append(h2h_index)

combined_schedule = pd.concat(all_schedules, ignore_index=True)
combined_h2h_index = merge_h2h_indexes(all_indexes)

combined_schedule.to_pickle(os.path.join(DATA_DIR, "tt_all_schedule.pkl"))

with gzip.open(os.path.join(DATA_DIR, "tt_all_h2h_index.pkl.gz"), "wb") as f:
    pickle.dump(combined_h2h_index, f)

print("Done.")