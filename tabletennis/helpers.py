import os
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join("tabletennis", "data")

LEAGUE_FILES = {
    "TT Cup": {
        "schedule": os.path.join(DATA_DIR, "tt_cup_schedule.csv"),
        "matchlogs": os.path.join(DATA_DIR, "tt_cup_matchlogs.csv"),
        "h2h": os.path.join(DATA_DIR, "tt_cup_h2h_summary.csv"),
    },
    "TT Elite": {
        "schedule": os.path.join(DATA_DIR, "tt_elite_schedule.csv"),
        "matchlogs": os.path.join(DATA_DIR, "tt_elite_matchlogs.csv"),
        "h2h": os.path.join(DATA_DIR, "tt_elite_h2h_summary.csv"),
    },
    "Czech": {
        "schedule": os.path.join(DATA_DIR, "tt_czech_schedule.csv"),
        "matchlogs": os.path.join(DATA_DIR, "tt_czech_matchlogs.csv"),
        "h2h": os.path.join(DATA_DIR, "tt_czech_h2h_summary.csv"),
    },
    "Setka": {
        "schedule": os.path.join(DATA_DIR, "tt_setka_schedule.csv"),
        "matchlogs": os.path.join(DATA_DIR, "tt_setka_matchlogs.csv"),
        "h2h": os.path.join(DATA_DIR, "tt_setka_h2h_summary.csv"),
    }
}

# -------------------------
# Helper: parse sets column
# -------------------------
def parse_sets(sets_str):
    try:
        sets = sets_str.split("|")
        return [tuple(map(int, s.split(":"))) for s in sets]
    except Exception:
        return []

def compute_set_wins(parsed_sets):
    """
    Returns sets won for player1 and player2
    """
    p1_sets = sum(1 for p1, p2 in parsed_sets if p1 > p2)
    p2_sets = sum(1 for p1, p2 in parsed_sets if p2 > p1)
    return p1_sets, p2_sets

def is_1all(parsed_sets):
    """
    Returns True if match was tied 1-1 after first 2 sets.
    Expects parsed_sets as list of (p1_points, p2_points) tuples.
    """
    if len(parsed_sets) < 2:
        return False  # cannot be tied 1-1 with fewer than 2 sets

    # Determine winner of first two sets
    first_set_winner = 1 if parsed_sets[0][0] > parsed_sets[0][1] else 2
    second_set_winner = 1 if parsed_sets[1][0] > parsed_sets[1][1] else 2

    return first_set_winner != second_set_winner

def total_points_match(parsed_sets):
    return sum(p1 + p2 for p1, p2 in parsed_sets)

def point_spread(parsed_sets):
    return sum(p1 - p2 for p1, p2 in parsed_sets)

def set_spread(parsed_sets):
    p1_sets, p2_sets = compute_set_wins(parsed_sets)
    return p1_sets - p2_sets

def normalize_name(name):
    if pd.isna(name):
        return name
    return name.strip().lower()

# -------------------------
# Load Raw CSVs
# -------------------------
@st.cache_data(show_spinner=False)
def load_tt_raw_data(league):
    """
    Loads raw Table Tennis datasets and applies minimal cleaning.
    Cached for performance.
    """
    paths = LEAGUE_FILES[league]

    schedule = pd.read_csv(paths["schedule"])
    matchlogs = pd.read_csv(paths["matchlogs"])
    h2h = pd.read_csv(paths["h2h"])

    # Keep original for display
    matchlogs["player1_display"] = matchlogs["player1"]
    matchlogs["player2_display"] = matchlogs["player2"]

    # Normalize for logic
    matchlogs["player1"] = matchlogs["player1"].apply(normalize_name)
    matchlogs["player2"] = matchlogs["player2"].apply(normalize_name)

    # Keep original for display
    schedule["player1_display"] = schedule["player1"]
    schedule["player2_display"] = schedule["player2"]

    # Normalize for logic
    schedule["player1"] = schedule["player1"].apply(normalize_name)
    schedule["player2"] = schedule["player2"].apply(normalize_name)

    # Normalize column naming
    if "match_date" in matchlogs.columns:
        matchlogs.rename(columns={"match_date": "date"}, inplace=True)

    # Normalize column naming
    if "match_date" in schedule.columns:
        schedule.rename(columns={"match_date": "date"}, inplace=True)

    # --- Date parsing ---
    for df, col in [(schedule, "date"), (matchlogs, "date")]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    schedule.dropna(subset=["match_id", "date"], inplace=True)
    matchlogs.dropna(subset=["match_id", "date"], inplace=True)

    # --- Parse sets ---
    matchlogs["parsed_sets"] = matchlogs["sets"].apply(parse_sets)

    # --- Drop bad parsed rows ---
    matchlogs = matchlogs[matchlogs["parsed_sets"].apply(len) > 0].copy()

    # --- Compute stats ---
    matchlogs["sets1"], matchlogs["sets2"] = zip(*matchlogs["parsed_sets"].apply(compute_set_wins))
    matchlogs["ATP"] = matchlogs["parsed_sets"].apply(total_points_match)
    matchlogs["PS"] = matchlogs["parsed_sets"].apply(point_spread)
    matchlogs["SS"] = matchlogs["parsed_sets"].apply(set_spread)
    matchlogs["winner"] = matchlogs.apply(
        lambda r: r["player1"] if r["sets1"] > r["sets2"] else r["player2"],
        axis=1
    )
    matchlogs["four_plus"] = matchlogs["parsed_sets"].apply(lambda x: int(len(x) >= 4))

    # --- Ensure newest first globally ---
    matchlogs.sort_values("date", ascending=False, inplace=True)

    h2h_index = build_h2h_index(matchlogs)

    return schedule, matchlogs, h2h, h2h_index

# -------------------------
# Build H2H index from matchlogs
# -------------------------
def build_h2h_index(matchlogs):
    """
    Creates a dictionary keyed by sorted player pair (tuple),
    with a list of matches (newest first)
    """
    h2h_index = {}
    matchlogs_sorted = matchlogs.sort_values("date", ascending=False)

    for _, row in matchlogs_sorted.iterrows():
        p1 = row["player1"]
        p2 = row["player2"]
        key = tuple(sorted([p1, p2]))

        if key not in h2h_index:
            h2h_index[key] = []

        h2h_index[key].append({
            "date": row["date"],
            "player1": p1,
            "player2": p2,
            "sets1": row["sets1"],
            "sets2": row["sets2"],
            "parsed_sets": row["parsed_sets"],
            "winner": row["winner"],
            "ATP": row["ATP"],
            "PS": row["PS"],
            "SS": row["SS"]
        })

    return h2h_index

# -------------------------
# Compute H2H stats for a player pair
# -------------------------
def compute_h2h_stats(h2h_index, player_a, player_b, window="ALL"):
    """
    Returns head-to-head stats for player_a vs player_b, including per-player bounce-back %
    window = "ALL", "L10", "L30", "L60"
    """
    key = tuple(sorted([player_a, player_b]))
    if key not in h2h_index:
        return None

    matches = h2h_index[key]

    # Apply recency window
    if window == "L10":
        matches = matches[:10]
    elif window == "L30":
        matches = matches[:30]
    elif window == "L60":
        matches = matches[:60]

    total = len(matches)
    if total == 0:
        return {
            "matches": 0,
            "a_wins": 0,
            "b_wins": 0,
            "win_pct": 0,
            "last_played": None,
            "sweeps_a": 0,
            "sweeps_b": 0,
            "non_sweep_pct": 0,
            "one_all_pct": 0,
            "ATP": 0,
            "PS": 0,
            "SS": 0,
            "a_bounce_pct": 0,
            "b_bounce_pct": 0
        }

    # Count wins
    a_wins = sum(1 for m in matches if m["winner"] == player_a)
    b_wins = total - a_wins

    # Average total sets per match
    avg_total_sets = sum(m["sets1"] + m["sets2"] for m in matches) / total

    # Sweeps (3-0 wins, orientation-safe)
    sweeps_a = sum(1 for m in matches if
                   ((m["player1"] == player_a and m["sets1"] == len(m["parsed_sets"]) and m["sets2"] == 0) or
                    (m["player2"] == player_a and m["sets2"] == len(m["parsed_sets"]) and m["sets1"] == 0)))
    sweeps_b = sum(1 for m in matches if
                   ((m["player1"] == player_b and m["sets1"] == len(m["parsed_sets"]) and m["sets2"] == 0) or
                    (m["player2"] == player_b and m["sets2"] == len(m["parsed_sets"]) and m["sets1"] == 0)))

    # Non-sweep matches
    non_sweep = sum(1 for m in matches if not (
        (m["sets1"] == len(m["parsed_sets"]) and m["sets2"] == 0) or
        (m["sets2"] == len(m["parsed_sets"]) and m["sets1"] == 0)
    ))
    non_sweep_pct = non_sweep / total if total > 0 else 0

    # Count matches tied 1-1 after first 2 sets
    one_all_count = sum(1 for m in matches if is_1all(m["parsed_sets"]))
    one_all_pct = one_all_count / total if total > 0 else 0

    # Average ATP, PS, SS over window
    avg_ATP = sum(m["ATP"] for m in matches) / total
    avg_PS = sum(abs(m["PS"]) for m in matches) / total
    avg_SS = sum(abs(m["SS"]) for m in matches) / total

    last_played = matches[0]["date"]  # newest first

    # -------------------------
    # Bounce-back % per player
    # -------------------------
    def player_bounce_pct(player_name):
        lost_s1 = [
            m for m in matches
            if len(m["parsed_sets"]) >= 2 and (
                (m["player1"] == player_name and m["parsed_sets"][0][0] < m["parsed_sets"][0][1]) or
                (m["player2"] == player_name and m["parsed_sets"][0][1] < m["parsed_sets"][0][0])
            )
        ]
        if not lost_s1:
            return 0, 0

        won_s2 = sum(
            1 for m in lost_s1
            if (m["player1"] == player_name and m["parsed_sets"][1][0] > m["parsed_sets"][1][1]) or
               (m["player2"] == player_name and m["parsed_sets"][1][1] > m["parsed_sets"][1][0])
        )

        return won_s2 / len(lost_s1), len(lost_s1)

    a_bounce_pct, a_n = player_bounce_pct(player_a)
    b_bounce_pct, b_n = player_bounce_pct(player_b)

    return {
        "matches": total,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "win_pct": a_wins / total if total > 0 else 0,
        "last_played": last_played,
        "sweeps_a": sweeps_a,
        "sweeps_b": sweeps_b,
        "non_sweep_pct": non_sweep_pct,
        "one_all_pct": one_all_pct,
        "a_bounce_pct": a_bounce_pct,
        "b_bounce_pct": b_bounce_pct,
        "a_bounce_n": a_n,
        "b_bounce_n": b_n,
        "avg_total_sets": avg_total_sets,
        "ATP": avg_ATP,
        "PS": avg_PS,
        "SS": avg_SS
    }