import pandas as pd
import numpy as np

# -----------------------------
# Configuration
# -----------------------------
MATCHLOG_CSV = "data/tt_czech_matchlogs.csv"
ROLLING_WINDOW = 30  # L30 H2H
NS_COL = "NS_L30"
ATP_COL = "ATP_L30"

# -----------------------------
# Load matchlogs
# -----------------------------
df = pd.read_csv(MATCHLOG_CSV)
df["match_date"] = pd.to_datetime(df["match_date"])
df = df.sort_values("match_date")

# Identify sweeps (3-0)
def is_sweep(sets_str):
    try:
        sets = sets_str.split("|")
        p1_sets = 0
        p2_sets = 0
        for s in sets:
            p1, p2 = map(int, s.split(":"))
            if p1 > p2:
                p1_sets += 1
            else:
                p2_sets += 1
        return (p1_sets == 3 and p2_sets == 0) or (p2_sets == 3 and p1_sets == 0)
    except:
        return False

df["is_sweep"] = df["sets"].apply(is_sweep)
df["non_sweep"] = 1 - df["is_sweep"]

# -----------------------------
# Compute rolling L30 H2H features
# -----------------------------
df["player_low"] = df[["player1","player2"]].min(axis=1)
df["player_high"] = df[["player1","player2"]].max(axis=1)

def compute_rolling(group):
    group = group.sort_values("match_date")
    group[NS_COL] = group["non_sweep"].rolling(ROLLING_WINDOW, min_periods=1).mean() * 100
    group[ATP_COL] = group["total_points"].rolling(ROLLING_WINDOW, min_periods=1).mean()
    return group

df = df.groupby(["player_low","player_high"], group_keys=False).apply(compute_rolling)

# -----------------------------
# Text-based threshold analysis
# -----------------------------
ns_thresholds = np.arange(70, 100, 2)    # 70% → 98%
atp_thresholds = np.arange(75, 100, 2)   # 75 → 98 points

print("=== Non-Sweep Success Rate Table (NS% × ATP Thresholds) ===\n")
print(f"{'NS% \\ ATP':>9}", end=" ")

for atp in atp_thresholds:
    print(f"{atp:>5}", end=" ")
print()

for ns in ns_thresholds:
    print(f"{ns:>9}", end=" ")
    for atp in atp_thresholds:
        subset = df[(df[NS_COL] >= ns) & (df[ATP_COL] >= atp)]
        if len(subset) == 0:
            print("  -  ", end=" ")
        else:
            success_rate = subset["non_sweep"].mean() * 100
            print(f"{success_rate:5.1f}", end=" ")
    print()