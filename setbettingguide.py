import pandas as pd

# --- Conditional probability function ---
def conditional_prob(df, player_col, target_set, condition_sets):
    target_col = f"Set{target_set}"
    if target_col not in df.columns:
        return None
    
    cond = pd.Series(True, index=df.index)
    for set_num, winner in condition_sets.items():
        col = f"Set{set_num}"
        if col not in df.columns:
            return None
        cond &= df[col].notna() & (df[col] == winner)

    total = cond.sum()
    if total == 0:
        return None

    if player_col == "player1":
        wins = (df.loc[cond, target_col] == 1).sum()
    else:
        wins = (df.loc[cond, target_col] == 2).sum()
    
    return wins / total

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

def blend_probability(base_p, window_p, samples, min_samples=12, max_boost=0.08):
    if window_p is None or samples < min_samples:
        return base_p
    edge = window_p - base_p
    if edge <= 0:
        return base_p
    weight = min(samples / 25, 1)
    adjustment = min(edge * weight, max_boost)
    return base_p + adjustment

# --- Load CSV ---
df = pd.read_csv("tabletennis/data/tt_elite_matchlogs.csv",
                 parse_dates=["match_date"], dtype={"sets": str})

# --- Expand sets into per-set rows ---
rows = []
for _, row in df.iterrows():
    sets = row['sets']
    if not isinstance(sets, str) or sets.lower() == 'nan':
        continue
    sets_split = sets.split('|')
    for i, s in enumerate(sets_split, start=1):
        p1_score, p2_score = map(int, s.split(':'))
        set_winner = 1 if p1_score > p2_score else 2
        rows.append({
            "match_id": row['match_id'],
            "match_date": row['match_date'],
            "player1": row['player1'],
            "player2": row['player2'],
            "set_num": i,
            "p1_score": p1_score,
            "p2_score": p2_score,
            "set_winner": set_winner
        })

sets_df = pd.DataFrame(rows)

# --- Pivot to per-match sets ---
pivot = sets_df.pivot(index='match_id', columns='set_num', values='set_winner')
for i in range(1, 6):
    if i not in pivot.columns:
        pivot[i] = pd.NA
pivot.columns = [f"Set{i}" for i in range(1, 6)]
pivot = pivot.merge(df[['match_id', 'player1', 'player2', 'match_date']], on='match_id')
pivot = pivot.reset_index(drop=True)

# --- Player-level conditional probabilities ---
def player_conditional(df, player_name, target_set, condition_sets):
    probs, counts = [], []

    df_p1 = df[df['player1'] == player_name]
    if len(df_p1) > 0:
        p = conditional_prob(df_p1, "player1", target_set, condition_sets)
        if p is not None:
            set_num = list(condition_sets.keys())[0]
            winner = list(condition_sets.values())[0]
            n = ((df_p1[f"Set{set_num}"].notna()) & (df_p1[f"Set{set_num}"] == winner)).sum()
            probs.append(p)
            counts.append(n)

    df_p2 = df[df['player2'] == player_name]
    if len(df_p2) > 0:
        flipped_conditions = {k: (1 if v == 2 else 2) for k, v in condition_sets.items()}
        p = conditional_prob(df_p2, "player2", target_set, flipped_conditions)
        if p is not None:
            set_num = list(flipped_conditions.keys())[0]
            winner = list(flipped_conditions.values())[0]
            n = ((df_p2[f"Set{set_num}"].notna()) & (df_p2[f"Set{set_num}"] == winner)).sum()
            probs.append(p)
            counts.append(n)

    if not probs:
        return None, 0

    total_n = sum(counts)
    weighted_p = sum(p * n for p, n in zip(probs, counts)) / total_n
    return weighted_p, total_n

# --- Compute Set2 probability after losing Set1 ---
def get_set2_probability(pivot, player1, player2, k=50):
    h2h_1 = pivot[(pivot['player1'] == player1) & (pivot['player2'] == player2)]
    h2h_2 = pivot[(pivot['player1'] == player2) & (pivot['player2'] == player1)]

    p1_h2h_1 = conditional_prob(h2h_1, "player1", 2, {1:2})
    p1_h2h_2 = conditional_prob(h2h_2, "player2", 2, {1:1})
    p2_h2h_1 = conditional_prob(h2h_1, "player2", 2, {1:1})
    p2_h2h_2 = conditional_prob(h2h_2, "player1", 2, {1:2})

    h2h_n = (h2h_1["Set1"] == 2).sum() + (h2h_2["Set1"] == 1).sum()

    def combine_probs(p_list, n_list):
        valid = [(p, n) for p, n in zip(p_list, n_list) if p is not None]
        if not valid:
            return None
        total_n = sum(n for _, n in valid)
        return sum(p * n for p, n in valid) / total_n

    n1 = (h2h_1["Set1"] == 2).sum()
    n2 = (h2h_2["Set1"] == 1).sum()
    p1_h2h = combine_probs([p1_h2h_1, p1_h2h_2], [n1, n2])
    p2_h2h = combine_probs([p2_h2h_1, p2_h2h_2], [n1, n2])

    p1_player, n1 = player_conditional(pivot, player1, 2, {1:2})
    p2_player, n2 = player_conditional(pivot, player2, 2, {1:1})

    global_p1 = conditional_prob(pivot, "player1", 2, {1:2})
    global_p2 = conditional_prob(pivot, "player2", 2, {1:1})

    if p1_h2h is None: p1_h2h = p1_player if p1_player else global_p1
    if p2_h2h is None: p2_h2h = p2_player if p2_player else global_p2

    def shrink(p, n, baseline):
        if p is None or n == 0:
            return baseline
        return (p * n + baseline * k) / (n + k)

    p1_final = shrink(p1_h2h, h2h_n, global_p1)
    p2_final = shrink(p2_h2h, h2h_n, global_p2)

    return {
        "p1_prob": p1_final,
        "p2_prob": p2_final,
        "p1_worst_odds": to_american(p1_final),
        "p2_worst_odds": to_american(p2_final),
        "h2h_samples": h2h_n
    }

result = get_set2_probability(pivot, "Szymon Sporek", "Michal Olbrycht")
base_p1 = result["p1_prob"]
base_p2 = result["p2_prob"]

print(result)

# --- Player-level bounce-back stats ---
p1_set2_after_loss = conditional_prob(pivot, "player1", 2, {1:2})
p2_set2_after_loss = conditional_prob(pivot, "player2", 2, {1:1})

print(f"Player1 BB% (Set2 after Set1 loss): {p1_set2_after_loss:.2f}")
print(f"Player2 BB% (Set2 after Set1 loss): {p2_set2_after_loss:.2f}")

def worst_odds(prob):
    if prob is None:
        return None
    return to_american(prob)

print(f"Player1 worst odds for Set2: {worst_odds(p1_set2_after_loss)}")
print(f"Player2 worst odds for Set2: {worst_odds(p2_set2_after_loss)}")

# --- Compute rolling window adjustments ---
from tabletennis.helpers import load_tt_raw_data, normalize_name, compute_h2h_stats

schedule, matchlogs, h2h, h2h_index = load_tt_raw_data("TT Elite")
player1 = normalize_name("Szymon Sporek")
player2 = normalize_name("Michal Olbrycht")

def compute_window_bb(h2h_index, player_a, player_b, window="ALL", k=50):
    stats = compute_h2h_stats(h2h_index, player_a, player_b, window)
    a_bb = stats["a_bounce_pct"]
    b_bb = stats["b_bounce_pct"]
    return {
        "p1_prob": a_bb,
        "p2_prob": b_bb,
        "p1_worst_odds": to_american(a_bb),
        "p2_worst_odds": to_american(b_bb),
        "p1_samples": stats["a_bounce_n"],
        "p2_samples": stats["b_bounce_n"],
        "matches_in_window": stats["matches"]
    }

windows = ["L10", "L30", "L60", "ALL"]
ev_windows = {w: compute_window_bb(h2h_index, player1, player2, window=w) for w in windows}
l30 = ev_windows["L30"]

adj_p1 = blend_probability(base_p1, l30["p1_prob"], l30["p1_samples"])
adj_p2 = blend_probability(base_p2, l30["p2_prob"], l30["p2_samples"])

print("\n--- ADJUSTED PROBABILITIES ---")
print("P1 adjusted:", round(adj_p1, 3), "Odds:", to_american(adj_p1))
print("P2 adjusted:", round(adj_p2, 3), "Odds:", to_american(adj_p2))

print(f"Set2 probabilities + worst odds by rolling window:")
for w, d in ev_windows.items():
    print(f"{w}: {d}")

# --- Build single summary table ---
summary_rows = []

for player, base_prob, adj_prob in zip(
    ["Player1", "Player2"],
    [base_p1, base_p2],
    [adj_p1, adj_p2]
):
    row = {
        "Player": player,
        "Base Prob": base_prob,
        "Adjusted Prob": adj_prob,
        "Worst Odds": to_american(base_prob)
    }
    # Add rolling window probabilities and samples
    for w in ["L10", "L30", "L60", "ALL"]:
        row[f"{w} Prob"] = ev_windows[w]["p1_prob"] if player == "Player1" else ev_windows[w]["p2_prob"]
        row[f"{w} Samples"] = ev_windows[w]["p1_samples"] if player == "Player1" else ev_windows[w]["p2_samples"]
        row[f"{w} Worst Odds"] = ev_windows[w]["p1_worst_odds"] if player == "Player1" else ev_windows[w]["p2_worst_odds"]
    summary_rows.append(row)

summary_table = pd.DataFrame(summary_rows)

print("\n=== Set2 Summary Table ===")
print(summary_table.to_string(index=False, float_format="{:.3f}".format))