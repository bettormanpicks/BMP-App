import pandas as pd

# Load data
df = pd.read_csv("data/tt_czech_matchlogs.csv")

# --- Identify sweeps (3-0) ---
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

# -------------------------
# BASELINE (ALL MATCHES)
# -------------------------
df["is_sweep"] = df["sets"].apply(is_sweep)

bins = [0, 60, 70, 80, 90, 200]
df["points_bucket"] = pd.cut(df["total_points"], bins)

bucket_stats = df.groupby("points_bucket", observed=False)["is_sweep"].mean() * 100
print("\nSweep % by Total Points Bucket:")
print(bucket_stats)

total_matches = len(df)
total_sweeps = df["is_sweep"].sum()
baseline_pct = (total_sweeps / total_matches * 100) if total_matches > 0 else 0

# -------------------------
# ≥80 TOTAL POINTS
# -------------------------
high_points_df = df[df["total_points"] >= 80].copy()

high_points_df["is_sweep"] = high_points_df["sets"].apply(is_sweep)

total_high = len(high_points_df)
sweeps_high = high_points_df["is_sweep"].sum()
high_pct = (sweeps_high / total_high * 100) if total_high > 0 else 0

# -------------------------
# OUTPUT
# -------------------------
print("=== Sweep Analysis ===")
print(f"Total Matches: {total_matches}")
print(f"Total Sweeps: {total_sweeps}")
print(f"Baseline Sweep %: {baseline_pct:.2f}%")

print("\n=== High Total Points Sweep Analysis ===")
print(f"Matches with ≥80 points: {total_high}")
print(f"Sweeps (3-0): {sweeps_high}")
print(f"Sweep %: {high_pct:.2f}%")

print("\n=== Edge Comparison ===")
print(f"Difference vs Baseline: {baseline_pct - high_pct:.2f}%")