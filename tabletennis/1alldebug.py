import pandas as pd

# -------------------------
# Helpers
# -------------------------
def parse_sets(sets_str):
    """Parses sets string like '11:8|9:11|11:7' into list of (p1_points, p2_points)."""
    try:
        sets = [tuple(map(int, s.split(":"))) for s in sets_str.split("|")]
        return sets
    except Exception:
        return []

def loser_wins_set2(parsed_sets):
    """
    Returns (p1_lost_s1_won_s2, p2_lost_s1_won_s2) as booleans for the first 2 sets.
    Only counts if the first 2 sets were split.
    """
    if len(parsed_sets) < 2:
        return False, False
    
    s1_winner = 1 if parsed_sets[0][0] > parsed_sets[0][1] else 2
    s2_winner = 1 if parsed_sets[1][0] > parsed_sets[1][1] else 2

    # Only consider split
    if s1_winner == s2_winner:
        return False, False

    p1_lost_s1 = s1_winner != 1
    p2_lost_s1 = s1_winner != 2

    p1_result = p1_lost_s1 and s2_winner == 1
    p2_result = p2_lost_s1 and s2_winner == 2

    return p1_result, p2_result

# -------------------------
# Load matchlogs
# -------------------------
MATCHLOGS_CSV = "data/tt_czech_matchlogs.csv"
df = pd.read_csv(MATCHLOGS_CSV)
df["parsed_sets"] = df["sets"].apply(parse_sets)

# -------------------------
# H2H filter
# -------------------------
player_a = "Jiri Plachy"
player_b = "Jaroslav Prokupek"

def normalize_name(name):
    return name.strip().lower()

player_a_n = normalize_name(player_a)
player_b_n = normalize_name(player_b)

h2h_df = df[((df["player1"].apply(normalize_name) == player_a_n) & 
             (df["player2"].apply(normalize_name) == player_b_n)) |
            ((df["player1"].apply(normalize_name) == player_b_n) & 
             (df["player2"].apply(normalize_name) == player_a_n))]

# -------------------------
# Quick sanity check using pandas filtering
# -------------------------
# Check player A (Jiri Plachy) lost set 1 and won set 2
a_check = h2h_df[
    h2h_df['parsed_sets'].apply(lambda x: len(x) >= 2 and x[0][0] < x[0][1] and x[1][0] > x[1][1])
]
b_check = h2h_df[
    h2h_df['parsed_sets'].apply(lambda x: len(x) >= 2 and x[0][0] > x[0][1] and x[1][0] < x[1][1])
]
print(f"Sanity check - player A lost Set 1 & won Set 2: {len(a_check)}")
print(f"Sanity check - player B lost Set 1 & won Set 2: {len(b_check)}")

# -------------------------
# Count bounce-backs
# -------------------------
a_lost_s1_won_s2 = 0
a_lost_s1_total = 0
b_lost_s1_won_s2 = 0
b_lost_s1_total = 0

for _, row in h2h_df.iterrows():
    parsed = row["parsed_sets"]
    if len(parsed) < 2:  # skip short/malformed matches
        continue

    p1 = normalize_name(row["player1"])
    p2 = normalize_name(row["player2"])

    p1_bounce, p2_bounce = loser_wins_set2(parsed)

    # Determine who lost Set 1 to count totals
    s1_winner = 1 if parsed[0][0] > parsed[0][1] else 2
    if s1_winner == 1:
        s1_loser_a = p2
        s1_loser_b = p1
    else:
        s1_loser_a = p1
        s1_loser_b = p2

    # Player A
    if p1 == player_a_n:
        if p1_bounce:
            a_lost_s1_won_s2 += 1
        if s1_loser_a == player_a_n:
            a_lost_s1_total += 1
    else:  # player_a is p2
        if p2_bounce:
            a_lost_s1_won_s2 += 1
        if s1_loser_a == player_a_n:
            a_lost_s1_total += 1

    # Player B
    if p1 == player_b_n:
        if p1_bounce:
            b_lost_s1_won_s2 += 1
        if s1_loser_a == player_b_n:
            b_lost_s1_total += 1
    else:  # player_b is p2
        if p2_bounce:
            b_lost_s1_won_s2 += 1
        if s1_loser_a == player_b_n:
            b_lost_s1_total += 1

# -------------------------
# Print results
# -------------------------
def pct(num, denom):
    return round((num / denom * 100) if denom > 0 else 0, 1)

print(f"H2H ({player_a}, {player_b}) last {len(h2h_df)} matches:")
print(f"{player_a} loses Set 1 → wins Set 2: {a_lost_s1_won_s2}/{a_lost_s1_total} → {pct(a_lost_s1_won_s2, a_lost_s1_total)}%")
print(f"{player_b} loses Set 1 → wins Set 2: {b_lost_s1_won_s2}/{b_lost_s1_total} → {pct(b_lost_s1_won_s2, b_lost_s1_total)}%")