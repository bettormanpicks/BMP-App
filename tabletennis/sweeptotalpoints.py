import pandas as pd
from collections import defaultdict

# -------------------------
# Configuration
# -------------------------
MATCHLOGS_CSV = "data/tt_czech_matchlogs.csv"
L_WINDOW = 30  # L30 H2H
NS_THRESHOLD = 0.82  # 82% non-sweep
ATP_THRESHOLD = 81   # example threshold for ATP

# -------------------------
# Helpers
# -------------------------
def parse_sets(sets_str):
    try:
        sets = [tuple(map(int, s.split(":"))) for s in sets_str.split("|") if ":" in s]
        return sets
    except:
        return []

def is_sweep(sets_str):
    parsed = parse_sets(sets_str)
    if not parsed:
        return False
    p1_sets = sum(1 for p1, p2 in parsed if p1 > p2)
    p2_sets = sum(1 for p1, p2 in parsed if p2 > p1)
    return (p1_sets == 3 and p2_sets == 0) or (p2_sets == 3 and p1_sets == 0)

def normalize_name(name):
    if pd.isna(name):
        return ""
    return name.strip().lower()

# -------------------------
# Load matchlogs
# -------------------------
df = pd.read_csv(MATCHLOGS_CSV)

# Normalize player names
df["player1"] = df["player1"].apply(normalize_name)
df["player2"] = df["player2"].apply(normalize_name)

# Sort newest first
df["date"] = pd.to_datetime(df["match_date"], errors="coerce")
df.sort_values("date", ascending=False, inplace=True)

# -------------------------
# Build L30 H2H dictionary
# -------------------------
h2h_index = defaultdict(list)

for _, row in df.iterrows():
    key = tuple(sorted([row["player1"], row["player2"]]))
    h2h_index[key].append({
        "sets": row["sets"],
        "total_points": row["total_points"],
        "is_sweep": is_sweep(row["sets"])
    })

# -------------------------
# Analyze predictive thresholds
# -------------------------
results = {
    "NS_only": {"matches": 0, "non_sweep": 0},
    "ATP_only": {"matches": 0, "non_sweep": 0},
    "NS_plus_ATP": {"matches": 0, "non_sweep": 0},
}

for key, matches in h2h_index.items():
    last_l = matches[:L_WINDOW]  # newest first

    if not last_l:
        continue

    # Compute L30 NS% and ATP
    non_sweeps = [not m["is_sweep"] for m in last_l]
    ns_pct = sum(non_sweeps) / len(last_l)

    atp = sum(m["total_points"] for m in last_l) / len(last_l)

    # Current match: oldest in window (or most recent)
    current_match = last_l[0]
    current_ns = not current_match["is_sweep"]

    # Threshold checks
    if ns_pct >= NS_THRESHOLD:
        results["NS_only"]["matches"] += 1
        if current_ns:
            results["NS_only"]["non_sweep"] += 1

    if atp >= ATP_THRESHOLD:
        results["ATP_only"]["matches"] += 1
        if current_ns:
            results["ATP_only"]["non_sweep"] += 1

    if (ns_pct >= NS_THRESHOLD) and (atp >= ATP_THRESHOLD):
        results["NS_plus_ATP"]["matches"] += 1
        if current_ns:
            results["NS_plus_ATP"]["non_sweep"] += 1

# -------------------------
# Display results
# -------------------------
print("=== L30 H2H Sweep Prediction Analysis ===\n")

for key, data in results.items():
    m = data["matches"]
    ns = data["non_sweep"]
    pct = (ns / m * 100) if m > 0 else 0
    print(f"{key}:")
    print(f"  Matches meeting threshold: {m}")
    print(f"  Actual non-sweep: {ns}")
    print(f"  Success rate: {pct:.2f}%\n")