import os
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join("tabletennis", "data")
SCHEDULE_PATH = os.path.join(DATA_DIR, "tt_elite_schedule.csv")
MATCHLOGS_PATH = os.path.join(DATA_DIR, "tt_elite_matchlogs.csv")
H2H_PATH = os.path.join(DATA_DIR, "tt_elite_h2h_summary.csv")

# -------------------------
# Load Raw CSVs
# -------------------------
@st.cache_data(show_spinner=False)
def load_tt_raw_data():
    """
    Loads raw Table Tennis datasets and applies minimal cleaning.
    Cached for performance.
    """

    schedule = pd.read_csv(SCHEDULE_PATH)
    matchlogs = pd.read_csv(MATCHLOGS_PATH)
    h2h = pd.read_csv(H2H_PATH)

    # --- Date parsing + normalization ---

    if "date" in schedule.columns:
        schedule["date"] = (
            pd.to_datetime(schedule["date"], errors="coerce", utc=True)
            .dt.tz_convert(None)
        )

    if "date" in matchlogs.columns:
        matchlogs["date"] = (
            pd.to_datetime(matchlogs["date"], errors="coerce", utc=True)
            .dt.tz_convert(None)
        )

    # --- Drop bad rows ---
    schedule.dropna(subset=["match_id", "date"], inplace=True)
    matchlogs.dropna(subset=["match_id", "date"], inplace=True)

    # --- Ensure newest first globally (extra safety) ---
    matchlogs.sort_values("date", ascending=False, inplace=True)

    # --- Compute winner column in matchlogs ---
    matchlogs["winner"] = matchlogs.apply(
        lambda row: row["player1"] if row["sets1"] > row["sets2"] else row["player2"],
        axis=1
    )

    return schedule, matchlogs, h2h

# -------------------------
# Build H2H index from matchlogs
# -------------------------
@st.cache_data(show_spinner=False)
def build_h2h_index(matchlogs):
    """
    Creates a dictionary keyed by sorted player pair (tuple),
    with a list of matches (newest first)
    """
    h2h_index = {}

    # Sort newest first
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
            "winner": row["winner"]
        })

    return h2h_index

# -------------------------
# Compute H2H stats for a player pair
# -------------------------
def compute_h2h_stats(h2h_index, player_a, player_b, window="ALL"):
    """
    Returns head-to-head stats for player_a vs player_b
    window = "ALL", "L10", "L30"
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
            "non_sweep_pct": 0
        }

    # Count wins
    a_wins = sum(1 for m in matches if m["winner"] == player_a)
    b_wins = total - a_wins

    # Average total sets per match
    avg_total_sets = sum(m["sets1"] + m["sets2"] for m in matches) / total

    # Count sweeps (3-0 wins) — orientation safe
    sweeps_a = 0
    sweeps_b = 0

    for m in matches:
        p1 = m["player1"]
        p2 = m["player2"]
        s1 = m["sets1"]
        s2 = m["sets2"]

        # Player A sweep
        if (p1 == player_a and s1 == 3 and s2 == 0) or \
           (p2 == player_a and s2 == 3 and s1 == 0):
            sweeps_a += 1

        # Player B sweep
        if (p1 == player_b and s1 == 3 and s2 == 0) or \
           (p2 == player_b and s2 == 3 and s1 == 0):
            sweeps_b += 1

    # Count non-sweep matches
    non_sweep = sum(
        1 for m in matches if not (
            (m["sets1"] == 3 and m["sets2"] == 0) or
            (m["sets2"] == 3 and m["sets1"] == 0)
        )
    )
    non_sweep_pct = non_sweep / total if total > 0 else 0

    last_played = matches[0]["date"]  # newest first

    return {
        "matches": total,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "win_pct": a_wins / total if total > 0 else 0,
        "last_played": last_played,
        "sweeps_a": sweeps_a,
        "sweeps_b": sweeps_b,
        "non_sweep_pct": non_sweep_pct,
        "avg_total_sets": avg_total_sets
    }