import pandas as pd

# Load your matchlogs
df = pd.read_csv("data/tt_czech_matchlogs.csv")

# --- Helper to parse sets ---
def parse_sets(sets_str):
    try:
        return [tuple(map(int, s.split(":"))) for s in sets_str.split("|")]
    except:
        return []

# --- Track stats ---
total_2_0_starts = 0
non_sweep_after_2_0 = 0

for _, row in df.iterrows():
    parsed = parse_sets(row["sets"])

    # Need at least 2 sets to evaluate 2-0 start
    if len(parsed) < 2:
        continue

    # Determine set winners (1 = player1, 2 = player2)
    set_winners = []
    for p1, p2 in parsed:
        if p1 > p2:
            set_winners.append(1)
        elif p2 > p1:
            set_winners.append(2)

    # Check if match starts 2-0
    if len(set_winners) >= 2 and set_winners[0] == set_winners[1]:
        total_2_0_starts += 1

        leader = set_winners[0]

        # If match has at least 3 sets
        if len(set_winners) >= 3:
            # If leader LOSES set 3 → NOT a sweep
            if set_winners[2] != leader:
                non_sweep_after_2_0 += 1

# --- Final calculation ---
if total_2_0_starts > 0:
    pct = non_sweep_after_2_0 / total_2_0_starts * 100
else:
    pct = 0

print("=== 2-0 Start Analysis ===")
print(f"Matches starting 2-0: {total_2_0_starts}")
print(f"Non-sweeps after 2-0: {non_sweep_after_2_0}")
print(f"Percentage: {pct:.2f}%")