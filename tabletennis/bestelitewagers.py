import pandas as pd

# --- Load CSVs ---
matchlogs = pd.read_csv("data/tt_elite_matchlogs.csv", parse_dates=["match_date"])
schedule = pd.read_csv("data/tt_elite_schedule.csv", parse_dates=["match_date"])

# Convert UTC → CDT (US Central time)
schedule['match_date'] = (
    pd.to_datetime(schedule['match_date'], utc=True)
      .dt.tz_convert('America/Chicago')
      .dt.tz_localize(None)  # remove timezone info for clean CSV
)

# --- Helper functions ---
def compute_sets_won(sets_str):
    p1, p2 = 0, 0
    if not isinstance(sets_str, str) or sets_str.lower() == 'nan':
        return p1, p2
    for s in sets_str.split('|'):
        a, b = map(int, s.split(':'))
        if a > b:
            p1 += 1
        else:
            p2 += 1
    return p1, p2

def to_american(prob, max_odds=1000):
    if prob is None:
        return None
    epsilon = 1e-6
    prob = min(max(prob, epsilon), 1 - epsilon)
    if prob == 0.5:
        return 100
    elif prob > 0.5:
        odds = round(-100 * prob / (1 - prob))
        return max(odds, -max_odds)
    else:
        odds = round(100 * (1 - prob) / prob)
        return min(odds, max_odds)

matchlogs['player1_sets'] = matchlogs['sets'].apply(lambda x: compute_sets_won(x)[0])
matchlogs['player2_sets'] = matchlogs['sets'].apply(lambda x: compute_sets_won(x)[1])
matchlogs['match_winner'] = matchlogs.apply(lambda row: 1 if row['player1_sets'] > row['player2_sets'] else 2, axis=1)

def compute_h2h_stats(df, player_a, player_b, window=None):
    h2h = df[((df['player1'] == player_a) & (df['player2'] == player_b)) |
             ((df['player1'] == player_b) & (df['player2'] == player_a))]
    if window:
        h2h = h2h.sort_values("match_date").tail(window)

    total_matches = len(h2h)
    a_wins = sum(((h2h['player1'] == player_a) & (h2h['match_winner'] == 1)) |
                 ((h2h['player2'] == player_a) & (h2h['match_winner'] == 2)))
    b_wins = sum(((h2h['player1'] == player_b) & (h2h['match_winner'] == 1)) |
                 ((h2h['player2'] == player_b) & (h2h['match_winner'] == 2)))

    a_prob = a_wins / total_matches if total_matches > 0 else None
    b_prob = b_wins / total_matches if total_matches > 0 else None

    return {
        "p1_prob": a_prob,
        "p2_prob": b_prob,
        "p1_samples": a_wins,
        "p2_samples": b_wins,
        "matches_in_window": total_matches,
        "p1_worst_odds": to_american(a_prob),
        "p2_worst_odds": to_american(b_prob)
    }

def blend_probability(base_p, window_p, samples, min_samples=18, max_boost=0.08):
    if window_p is None or samples < min_samples:
        return base_p
    edge = window_p - base_p
    if edge <= 0:
        return base_p
    weight = min(samples / 25, 1)
    return base_p + min(edge * weight, max_boost)

# --- Main loop ---
MIN_MATCHES = 18
K_SHRINK = 50
WINDOWS = ["L30", "L60", "ALL"]  # L10 removed
rows = []

for _, match in schedule.iterrows():
    match_date = match['match_date']  # <-- added
    p1 = match['player1']
    p2 = match['player2']

    # Compute H2H stats for all windows
    ev_windows = {}
    for w in WINDOWS:
        n = None if w=="ALL" else int(w[1:])
        ev_windows[w] = compute_h2h_stats(matchlogs, p1, p2, window=n)

    # Skip match if L30 sample too small
    if ev_windows["L30"]["p1_samples"] < MIN_MATCHES and ev_windows["L30"]["p2_samples"] < MIN_MATCHES:
        continue

    # Shrink probabilities toward ALL
    def safe_shrink(prob, samples, global_prob):
        if prob is None or samples < MIN_MATCHES:
            return global_prob
        return (prob * samples + global_prob * K_SHRINK) / (samples + K_SHRINK)

    adj_p1 = safe_shrink(ev_windows["L30"]["p1_prob"], ev_windows["L30"]["p1_samples"], ev_windows["ALL"]["p1_prob"])
    adj_p2 = safe_shrink(ev_windows["L30"]["p2_prob"], ev_windows["L30"]["p2_samples"], ev_windows["ALL"]["p2_prob"])

    # Variance across windows
    var_p1 = max(ev_windows[w]["p1_prob"] for w in WINDOWS) - min(ev_windows[w]["p1_prob"] for w in WINDOWS)
    var_p2 = max(ev_windows[w]["p2_prob"] for w in WINDOWS) - min(ev_windows[w]["p2_prob"] for w in WINDOWS)

    # Best Wager Score
    score_p1 = adj_p1 - var_p1
    score_p2 = adj_p2 - var_p2

    # Only append players meeting MIN_MATCHES
    if ev_windows["L30"]["p1_samples"] >= MIN_MATCHES:
        rows.append({
            "Match Date": match_date,           # <-- added
            "Match": f"{p1} vs {p2}",
            "Player": p1,
            "Adjusted Prob": round(adj_p1,3),
            "Variance": round(var_p1,3),
            "Best Wager Score": round(score_p1,3),
            "Worst Odds": ev_windows["ALL"]["p1_worst_odds"]
        })
    if ev_windows["L30"]["p2_samples"] >= MIN_MATCHES:
        rows.append({
            "Match Date": match_date,           # <-- added
            "Match": f"{p1} vs {p2}",
            "Player": p2,
            "Adjusted Prob": round(adj_p2,3),
            "Variance": round(var_p2,3),
            "Best Wager Score": round(score_p2,3),
            "Worst Odds": ev_windows["ALL"]["p2_worst_odds"]
        })

# --- Create DataFrame and save CSV ---
if rows:
    df_out = pd.DataFrame(rows)
    df_out = df_out.sort_values("Best Wager Score", ascending=False)
    df_out.to_csv("data/bestelitewagers.csv", index=False)
    print("Saved best wagers table to data/bestelitewagers.csv")
else:
    print("No matches meet MIN_MATCHES requirement. CSV not created.")