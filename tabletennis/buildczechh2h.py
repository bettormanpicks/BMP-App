import pandas as pd

df = pd.read_csv("data/tt_czech_matchlogs.csv")

# Identify sweep
df["is_sweep"] = df[["sets1", "sets2"]].min(axis=1) == 0

# Normalize player pairs
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
h2h.to_csv("data/tt_czech_h2h_summary.csv", index=False)

print("Final H2H shape:", h2h.shape)

league_sweep_rate = df["is_sweep"].mean()
print("League Sweep Rate:", league_sweep_rate)

# Sort by lowest sweep rate
goldmine = h2h.sort_values("sweep_rate")

print("\nTop 20 Lowest Sweep Rate Rivalries (min 20 matches):\n")
print(goldmine.head(20))