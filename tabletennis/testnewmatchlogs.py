import pandas as pd

# Load matchlogs
df = pd.read_csv("data/tt_czech_matchlogs.csv", parse_dates=["match_date"])

# Sort newest first and take last 30
df = df.sort_values("match_date", ascending=False).head(30).copy()

# --- Helpers ---
def parse_sets(sets_str):
    return [tuple(map(int, s.split(":"))) for s in sets_str.split("|")]

def compute_metrics(parsed_sets):
    p1_sets = sum(1 for p1, p2 in parsed_sets if p1 > p2)
    p2_sets = sum(1 for p1, p2 in parsed_sets if p2 > p1)

    total_sets = len(parsed_sets)
    total_points = sum(p1 + p2 for p1, p2 in parsed_sets)
    atp = total_points / total_sets
    ps = sum(p1 - p2 for p1, p2 in parsed_sets)

    winner = 1 if p1_sets > p2_sets else 2

    return p1_sets, p2_sets, total_sets, total_points, atp, ps, winner

# --- Apply calculations ---
results = []

for _, row in df.iterrows():
    parsed = parse_sets(row["sets"])

    p1_sets, p2_sets, total_sets, total_points_calc, atp, ps, winner_calc = compute_metrics(parsed)

    results.append({
        "match_id": row["match_id"],
        "player1": row["player1"],
        "player2": row["player2"],

        # Original
        "orig_total_points": row.get("total_points"),
        "orig_winner": row.get("match_winner"),

        # Calculated
        "calc_sets1": p1_sets,
        "calc_sets2": p2_sets,
        "calc_total_sets": total_sets,
        "calc_total_points": total_points_calc,
        "ATP": round(atp, 2),
        "PS": ps,
        "calc_winner": winner_calc,

        # Checks
        "points_match": row.get("total_points") == total_points_calc,
        "winner_match": row.get("match_winner") == winner_calc,
    })

diag_df = pd.DataFrame(results)

# --- Print summary ---
print("\n=== DIAGNOSTIC RESULTS (Last 30 Matches) ===\n")
print(diag_df)

print("\n=== SUMMARY CHECKS ===")
print("Total Matches:", len(diag_df))
print("Points Mismatches:", (~diag_df["points_match"]).sum())
print("Winner Mismatches:", (~diag_df["winner_match"]).sum())