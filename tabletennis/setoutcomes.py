import pandas as pd
import numpy as np

# -------------------------
# CONFIG
# -------------------------
NS_VALUES = range(80, 93, 2)     # 80,82,...92
ATP_VALUES = range(75, 91, 3)    # 75,78,...90
MIN_MATCHES = 10

ODDS_DECIMAL = 1.833

# -------------------------
# LOAD + PREP
# -------------------------
df = pd.read_csv("data/tt_czech_matchlogs.csv")

df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
df = df.dropna(subset=["match_date"])
df = df.sort_values("match_date").reset_index(drop=True)

df["player_low"] = df[["player1", "player2"]].min(axis=1)
df["player_high"] = df[["player1", "player2"]].max(axis=1)

# -------------------------
# HELPERS
# -------------------------
def parse_sets(sets_str):
    try:
        return [tuple(map(int, s.split(":"))) for s in sets_str.split("|")]
    except:
        return []

def is_sweep(parsed_sets):
    p1 = sum(1 for a,b in parsed_sets if a > b)
    p2 = sum(1 for a,b in parsed_sets if b > a)
    return (p1 == 3 and p2 == 0) or (p2 == 3 and p1 == 0)

def total_points(parsed_sets):
    return sum(a+b for a,b in parsed_sets)

def outcome(parsed_sets):
    if len(parsed_sets) < 3:
        return 0

    s1 = parsed_sets[0]
    loser = 1 if s1[0] < s1[1] else 2

    s2 = parsed_sets[1]
    if (loser == 1 and s2[0] > s2[1]) or (loser == 2 and s2[1] > s2[0]):
        return 1

    s3 = parsed_sets[2]
    if (loser == 1 and s3[0] > s3[1]) or (loser == 2 and s3[1] > s3[0]):
        return 2

    return 0

df["parsed_sets"] = df["sets"].apply(parse_sets)

# -------------------------
# BUILD CLEAN DATASET
# -------------------------
rows = []

for (p_low, p_high), group in df.groupby(["player_low", "player_high"]):

    group = group.sort_values("match_date").reset_index(drop=True)
    history = []

    for _, row in group.iterrows():

        prior = history[-30:]

        if len(prior) >= MIN_MATCHES:
            sweeps = sum(m["sweep"] for m in prior)
            ns_pct = 100 * (1 - sweeps / len(prior))
            atp = np.mean([m["points"] for m in prior])

            rows.append({
                "ns_pct": ns_pct,
                "atp": atp,
                "outcome": outcome(row["parsed_sets"]),
                "actual_points": total_points(row["parsed_sets"])
            })

        history.append({
            "sweep": is_sweep(row["parsed_sets"]),
            "points": total_points(row["parsed_sets"])
        })

clean = pd.DataFrame(rows)

# -------------------------
# OPTIMIZATION
# -------------------------
results = []

for ns in NS_VALUES:
    for atp in ATP_VALUES:

        subset = clean[(clean["ns_pct"] >= ns) & (clean["atp"] >= atp)]

        total = len(subset)
        if total < 200:  # skip tiny samples
            continue

        p2 = (subset["outcome"] == 1).mean()
        p3 = (subset["outcome"] == 2).mean()
        pl = (subset["outcome"] == 0).mean()

        profit2 = ODDS_DECIMAL - 1
        profit3 = 2 * profit2 - 1
        loss = -3

        ev = p2*profit2 + p3*profit3 + pl*loss

        results.append({
            "NS": ns,
            "ATP": atp,
            "matches": total,
            "sweep%": pl*100,
            "EV": ev
        })

res = pd.DataFrame(results)

# Sort best first
res = res.sort_values("EV", ascending=False)

# -------------------------
# OUTPUT
# -------------------------
print("\n=== TOP 25 STRATEGIES ===\n")
print(res.head(25).to_string(index=False))

print("\n=== SUMMARY ===")
print(f"Total evaluated rows: {len(clean)}")

# -------------------------
# APPLY FILTERS
# -------------------------
filtered = clean[
    (clean["ns_pct"] >= 86) &
    (clean["atp"] >= 84)
]

print(f"\nFiltered matches: {len(filtered)}")

# -------------------------
# STRATEGY COMPARISON
# -------------------------
profit_set2_only = []
profit_martingale = []

profit_win = ODDS_DECIMAL - 1
profit_recover = 2 * profit_win - 1

for _, row in filtered.iterrows():
    o = row["outcome"]

    # Set 2 only
    if o == 1:
        profit_set2_only.append(profit_win)
    else:
        profit_set2_only.append(-1)

    # Martingale
    if o == 1:
        profit_martingale.append(profit_win)
    elif o == 2:
        profit_martingale.append(profit_recover)
    else:
        profit_martingale.append(-3)

p2 = np.array(profit_set2_only)
pm = np.array(profit_martingale)

print("\n=== FILTERED STRATEGY COMPARISON ===\n")

print("Set 2 Only:")
print(f"Mean profit per match: {p2.mean():.4f}")
print(f"Std dev: {p2.std():.4f}")

print("\nMartingale:")
print(f"Mean profit per match: {pm.mean():.4f}")
print(f"Std dev: {pm.std():.4f}")

# -------------------------
# TOTAL POINTS STRATEGY TEST
# -------------------------
TOTAL_LINE = 75       # try 73, 75, 77, etc
TOTAL_ODDS = 1.83     # typical -120

filtered_totals = clean[
    (clean["ns_pct"] >= 86) &
    (clean["atp"] >= 84)
]

profits_totals = []

for _, row in filtered_totals.iterrows():
    if row["actual_points"] > TOTAL_LINE:
        profits_totals.append(TOTAL_ODDS - 1)
    else:
        profits_totals.append(-1)

pt = np.array(profits_totals)

print("\n=== TOTALS STRATEGY ===\n")
print(f"Line: Over {TOTAL_LINE}")
print(f"Matches: {len(pt)}")
print(f"Win rate: {(pt > 0).mean()*100:.2f}%")
print(f"Mean profit per match: {pt.mean():.4f}")
print(f"Std dev: {pt.std():.4f}")

print("\n=== TOTALS LINE TEST ===\n")

for line in range(70, 91, 2):  # 70,72,...90

    profits = []

    for _, row in filtered_totals.iterrows():
        if row["actual_points"] > line:
            profits.append(TOTAL_ODDS - 1)
        else:
            profits.append(-1)

    p = np.array(profits)

    if len(p) < 200:
        continue

    print(f"Line {line}: "
          f"Win% {(p > 0).mean()*100:.2f} | "
          f"EV {p.mean():.4f} | "
          f"Std {p.std():.3f}")

# -------------------------
# TOTALS LINE SCAN
# -------------------------

ODDS_DECIMAL = 1.833  # adjust to your average book odds
LINES = range(70, 91)  # scan lines from 70 to 90

print("\n=== TOTALS LINE SCAN (Filtered Matches NS>=86, ATP>=84) ===\n")

for line in LINES:
    wins = (filtered["actual_points"] > line).sum()
    total = len(filtered)
    
    if total == 0:
        continue
    
    win_pct = wins / total
    ev = win_pct * (ODDS_DECIMAL - 1) - (1 - win_pct)
    std = np.sqrt(win_pct*(1-win_pct))
    
    if ev > 0:  # only show positive EV
        print(f"Line {line}: Win% {win_pct*100:.2f} | EV {ev:.4f} | Std {std:.3f}")

LINES = range(70, 91)  # totals lines to check
MIN_MATCHES = 10

summary = []

for ns in range(80, 93, 2):
    for atp in range(75, 91, 3):
        subset = clean[(clean["ns_pct"] >= ns) & (clean["atp"] >= atp)]
        if len(subset) < MIN_MATCHES:
            continue

        for line in LINES:
            wins = (subset["actual_points"] > line).sum()
            total = len(subset)
            win_pct = wins / total
            ev = win_pct * (ODDS_DECIMAL - 1) - (1 - win_pct)
            std = np.sqrt(win_pct*(1-win_pct))  # approximate
            if ev > 0:
                summary.append({
                    "NS": ns,
                    "ATP": atp,
                    "line": line,
                    "matches": total,
                    "win%": win_pct*100,
                    "EV": ev,
                    "Std": std
                })
                break  # stop at the lowest profitable line

summary_df = pd.DataFrame(summary)
summary_df = summary_df.sort_values(["NS","ATP","line"])

# -------------------------
# INVERSE LINE SCAN: Lowest NS% and ATP for +EV at given totals lines
# -------------------------
lines_to_check = [79, 78, 77, 76, 75, 74, 73, 72]
results = []

for line in lines_to_check:

    # Filter dataset by NS% / ATP thresholds that would still give positive EV
    # Start from lowest possible values and increase until EV > 0
    for ns_thresh in range(80, 101):          # NS% 80 -> 100
        for atp_thresh in range(75, 101):     # ATP 75 -> 100
            filt = clean[(clean["ns_pct"] >= ns_thresh) & (clean["atp"] >= atp_thresh)]

            if len(filt) < 50:  # skip tiny samples
                continue

            # compute profit per match (over bet)
            profit_array = np.where(filt["actual_points"] > line, ODDS_DECIMAL - 1, -1)

            ev = profit_array.mean()

            if ev > 0:  # first combination that is profitable
                results.append({
                    "line": line,
                    "min_NS": ns_thresh,
                    "min_ATP": atp_thresh,
                    "matches": len(filt),
                    "EV": ev,
                    "Std": profit_array.std()
                })
                break  # stop at first profitable ATP for this NS
        else:
            continue
        break  # stop at first profitable NS

res_lines = pd.DataFrame(results)
print("\n=== LOWEST NS/ATP FOR +EV BY LINE (Over) ===\n")
print(res_lines)