import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MATCHLOGS_CSV = os.path.join(BASE_DIR, "data", "tt_cup_matchlogs.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_cup_h2h_summary.csv")

df = pd.read_csv(MATCHLOGS_CSV, dtype={"match_id": str})

# -------------------------
# Normalize column names
# -------------------------
if "match_date" in df.columns:
    df.rename(columns={"match_date": "date"}, inplace=True)

# -------------------------
# Normalize player names
# -------------------------
df["player1"] = df["player1"].str.strip().str.lower()
df["player2"] = df["player2"].str.strip().str.lower()

# -------------------------
# Parse sets
# -------------------------
def parse_sets(sets_str):
    try:
        return [tuple(map(int, s.split(":"))) for s in sets_str.split("|")]
    except:
        return []

def compute_set_wins(parsed_sets):
    p1 = sum(1 for a, b in parsed_sets if a > b)
    p2 = sum(1 for a, b in parsed_sets if b > a)
    return p1, p2

df["parsed_sets"] = df["sets"].apply(parse_sets)
df = df[df["parsed_sets"].apply(len) > 0]

df["sets1"], df["sets2"] = zip(*df["parsed_sets"].apply(compute_set_wins))

# -------------------------
# Derived stats
# -------------------------
df["total_sets"] = df["sets1"] + df["sets2"]

# Sweep = 3-0
df["is_sweep"] = (df["sets1"] == 3) & (df["sets2"] == 0) | \
                 (df["sets2"] == 3) & (df["sets1"] == 0)

# -------------------------
# Normalize player pairs
# -------------------------
df["player_low"] = df[["player1", "player2"]].min(axis=1)
df["player_high"] = df[["player1", "player2"]].max(axis=1)

# Total sets in match
df["total_sets"] = df["sets1"] + df["sets2"]

# Group
h2h = (
    df.groupby(["player_low", "player_high"])
      .agg(
          matches=("match_id", "count"),
          sweeps=("is_sweep", "sum"),
          avg_total_sets=("total_sets", "mean"),
          avg_ATP=("total_points", "mean"),
          last_match=("date", "max")
      )
      .reset_index()
)

# Rates
h2h["sweep_rate"] = h2h["sweeps"] / h2h["matches"]
h2h["non_sweep_rate"] = 1 - h2h["sweep_rate"]

# Minimum 10 match filter
h2h = h2h[h2h["matches"] >= 20]

# Save
h2h.to_csv(OUTPUT_CSV, index=False)

print("Final H2H shape:", h2h.shape)

league_sweep_rate = df["is_sweep"].mean()
print("League Sweep Rate:", league_sweep_rate)

# Sort by lowest sweep rate
goldmine = h2h.sort_values("sweep_rate")

print("\nTop 20 Lowest Sweep Rate Rivalries (min 20 matches):\n")
print(goldmine.head(20))