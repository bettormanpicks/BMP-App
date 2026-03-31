import pandas as pd

# --- Load CSVs ---
matchlogs = pd.read_csv("data/tt_cup_matchlogs.csv", parse_dates=["match_date"])
schedule = pd.read_csv("data/tt_cup_schedule.csv", parse_dates=["match_date"])

# --- Convert UTC → CDT ---
schedule['match_date'] = schedule['match_date'] - pd.Timedelta(hours=5)

# --- Parse sets into per-set results ---
rows = []
for _, row in matchlogs.iterrows():
    if not isinstance(row['sets'], str):
        continue
    for i, s in enumerate(row['sets'].split('|'), start=1):
        a, b = map(int, s.split(':'))
        winner = 1 if a > b else 2
        rows.append({
            "match_id": row['match_id'],
            "match_date": row['match_date'],
            "player1": row['player1'],
            "player2": row['player2'],
            "set_num": i,
            "winner": winner
        })

sets_df = pd.DataFrame(rows)

# --- Pivot into match-level sets ---
pivot = sets_df.pivot(index='match_id', columns='set_num', values='winner')

for i in range(1, 6):
    if i not in pivot.columns:
        pivot[i] = pd.NA

pivot.columns = [f"Set{i}" for i in range(1, 6)]

pivot = pivot.merge(matchlogs[['match_id','player1','player2','match_date']], on='match_id')
pivot = pivot.sort_values("match_date")

# --- Convert probability to American odds ---
def to_american(prob):
    if prob is None:
        return None
    if prob == 0:
        return 1000
    if prob == 1:
        return -1000
    if prob > 0.5:
        return round(-100 * prob / (1 - prob))
    else:
        return round(100 * (1 - prob) / prob)

# --- Bounce-back calculation ---
def compute_bb(df, p1, p2, window=None):
    h2h = df[((df['player1']==p1)&(df['player2']==p2)) |
             ((df['player1']==p2)&(df['player2']==p1))]

    if window:
        h2h = h2h.tail(window)

    # Player1 loses Set1 → wins Set2
    p1_cases = ((h2h['player1']==p1)&(h2h['Set1']==2)) | \
               ((h2h['player2']==p1)&(h2h['Set1']==1))

    p1_total = p1_cases.sum()

    p1_wins = (
        ((h2h['player1']==p1)&(h2h['Set1']==2)&(h2h['Set2']==1)) |
        ((h2h['player2']==p1)&(h2h['Set1']==1)&(h2h['Set2']==2))
    ).sum()

    p1_prob = p1_wins / p1_total if p1_total > 0 else None

    # Player2 (same logic flipped)
    p2_cases = ((h2h['player1']==p2)&(h2h['Set1']==2)) | \
               ((h2h['player2']==p2)&(h2h['Set1']==1))

    p2_total = p2_cases.sum()

    p2_wins = (
        ((h2h['player1']==p2)&(h2h['Set1']==2)&(h2h['Set2']==1)) |
        ((h2h['player2']==p2)&(h2h['Set1']==1)&(h2h['Set2']==2))
    ).sum()

    p2_prob = p2_wins / p2_total if p2_total > 0 else None

    return {
        "p1_prob": p1_prob,
        "p1_samples": p1_total,
        "p2_prob": p2_prob,
        "p2_samples": p2_total
    }

# --- SETTINGS ---
MIN_SAMPLES = 12

rows = []

for _, match in schedule.iterrows():
    p1 = match['player1']
    p2 = match['player2']
    date = match['match_date']

    l30 = compute_bb(pivot, p1, p2, window=30)
    all_stats = compute_bb(pivot, p1, p2, window=None)

    # Skip match if BOTH players are below threshold
    if l30["p1_samples"] < MIN_SAMPLES and l30["p2_samples"] < MIN_SAMPLES:
        continue

    rows.append({
        "Match Date": date,
        "Match": f"{p1} vs {p2}",

        "P1": p1,
        "P1 BB%": round(l30["p1_prob"], 3) if l30["p1_samples"] >= MIN_SAMPLES else None,
        "P1 Samples": l30["p1_samples"],
        "P1 Worst Odds": to_american(l30["p1_prob"]) if l30["p1_samples"] >= MIN_SAMPLES else None,

        "P2": p2,
        "P2 BB%": round(l30["p2_prob"], 3) if l30["p2_samples"] >= MIN_SAMPLES else None,
        "P2 Samples": l30["p2_samples"],
        "P2 Worst Odds": to_american(l30["p2_prob"]) if l30["p2_samples"] >= MIN_SAMPLES else None,

        "Sort Key": max(
            l30["p1_prob"] if l30["p1_samples"] >= MIN_SAMPLES and l30["p1_prob"] else 0,
            l30["p2_prob"] if l30["p2_samples"] >= MIN_SAMPLES and l30["p2_prob"] else 0
        )
    })

# --- Save CSV ---
df_out = pd.DataFrame(rows)

if not df_out.empty:
    df_out = df_out.sort_values("Sort Key", ascending=False)
    df_out = df_out.drop(columns=["Sort Key"])
    df_out.to_csv("data/ttcupset2bb.csv", index=False)
    print("Saved → data/ttcupset2bb.csv")
else:
    print("No qualifying matches.")