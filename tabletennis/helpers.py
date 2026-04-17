import os
import pickle
import pandas as pd
import streamlit as st
import gzip

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
        return False

    first_set_winner  = 1 if parsed_sets[0][0] > parsed_sets[0][1] else 2
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
@st.cache_data(show_spinner=False, max_entries=4)
def load_tt_raw_data(league):
    """
    Loads raw Table Tennis datasets and applies minimal cleaning.
    Cached for performance.
    """
    paths = LEAGUE_FILES[league]

    schedule  = pd.read_csv(paths["schedule"])
    matchlogs = pd.read_csv(paths["matchlogs"])
    h2h       = pd.read_csv(paths["h2h"])

    # Keep originals for display
    matchlogs["player1_display"] = matchlogs["player1"]
    matchlogs["player2_display"] = matchlogs["player2"]
    schedule["player1_display"]  = schedule["player1"]
    schedule["player2_display"]  = schedule["player2"]

    # Normalize for logic
    matchlogs["player1"] = matchlogs["player1"].apply(normalize_name)
    matchlogs["player2"] = matchlogs["player2"].apply(normalize_name)
    schedule["player1"]  = schedule["player1"].apply(normalize_name)
    schedule["player2"]  = schedule["player2"].apply(normalize_name)

    # Normalize column naming
    if "match_date" in matchlogs.columns:
        matchlogs.rename(columns={"match_date": "date"}, inplace=True)
    if "match_date" in schedule.columns:
        schedule.rename(columns={"match_date": "date"}, inplace=True)

    # Date parsing
    for df, col in [(schedule, "date"), (matchlogs, "date")]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    schedule.dropna(subset=["match_id", "date"], inplace=True)
    matchlogs.dropna(subset=["match_id", "date"], inplace=True)

    # Parse sets
    matchlogs["parsed_sets"] = matchlogs["sets"].apply(parse_sets)

    # Drop bad parsed rows
    matchlogs = matchlogs[matchlogs["parsed_sets"].apply(len) > 0].copy()

    # Compute stats
    matchlogs["sets1"], matchlogs["sets2"] = zip(*matchlogs["parsed_sets"].apply(compute_set_wins))
    matchlogs["ATP"]    = matchlogs["parsed_sets"].apply(total_points_match)
    matchlogs["PS"]     = matchlogs["parsed_sets"].apply(point_spread)
    matchlogs["SS"]     = matchlogs["parsed_sets"].apply(set_spread)
    matchlogs["winner"] = matchlogs.apply(
        lambda r: r["player1"] if r["sets1"] > r["sets2"] else r["player2"],
        axis=1
    )
    matchlogs["four_plus"] = matchlogs["parsed_sets"].apply(lambda x: int(len(x) >= 4))

    # Newest first
    matchlogs.sort_values("date", ascending=False, inplace=True)

    h2h_index = build_h2h_index(matchlogs)

    return schedule, matchlogs, h2h, h2h_index

# -------------------------
# Build all league data
# -------------------------
@st.cache_data(show_spinner=False, max_entries=1)
def load_tt_all_leagues():
    schedule = pd.read_pickle(os.path.join(DATA_DIR, "tt_all_schedule.pkl"))

    with gzip.open(os.path.join(DATA_DIR, "tt_all_h2h_index.pkl.gz"), "rb") as f:
        h2h_index = pickle.load(f)

    return schedule, None, None, h2h_index

# -------------------------
# Build H2H index from matchlogs
# -------------------------
def build_h2h_index(matchlogs):
    """
    Creates a dictionary keyed by sorted player pair (tuple),
    with a list of matches (newest first).

    Each match entry now includes set-level winners to support
    BB% (bounce-back: lost s1, won s2) and SR% (sweep resistance:
    lost s1 and s2, won s3) calculations.
    """
    h2h_index = {}
    matchlogs_sorted = matchlogs.sort_values("date", ascending=False)

    for _, row in matchlogs_sorted.iterrows():
        p1  = row["player1"]
        p2  = row["player2"]
        key = tuple(sorted([p1, p2]))

        if key not in h2h_index:
            h2h_index[key] = []

        parsed = row["parsed_sets"]

        # Derive per-set winners (1 = player1 won that set, 2 = player2 won)
        s1_winner = 1 if len(parsed) >= 1 and parsed[0][0] > parsed[0][1] else 2
        s2_winner = 1 if len(parsed) >= 2 and parsed[1][0] > parsed[1][1] else 2
        s3_winner = (1 if parsed[2][0] > parsed[2][1] else 2) if len(parsed) >= 3 else None

        h2h_index[key].append({
            "date":        row["date"],
            "player1":     p1,
            "player2":     p2,
            "sets1":       row["sets1"],
            "sets2":       row["sets2"],
            "parsed_sets": parsed,
            "winner":      row["winner"],
            "ATP":         row["ATP"],
            "PS":          row["PS"],
            "SS":          row["SS"],
            # Set-level winners for BB% / SR% computation
            "s1_winner":   s1_winner,
            "s2_winner":   s2_winner,
            "s3_winner":   s3_winner,
        })

    return h2h_index

# -------------------------
# Merge H2H indexes
# -------------------------
def merge_h2h_indexes(indexes):
    """
    Merges multiple h2h_index dicts by combining match lists for shared
    keys and sorting merged lists newest-first.
    """
    merged = {}
    for index in indexes:
        for key, matches in index.items():
            if key in merged:
                merged[key].extend(matches)
            else:
                merged[key] = list(matches)

    # Re-sort each pair's matches newest-first after merging
    for key in merged:
        merged[key].sort(key=lambda m: m["date"], reverse=True)

    return merged

# -------------------------
# Compute H2H stats for a player pair
# -------------------------
def compute_h2h_stats(h2h_index, player_a, player_b, window="ALL"):
    """
    Returns head-to-head stats for player_a vs player_b.

    Stats returned
    --------------
    matches, a_wins, b_wins, win_pct, last_played
    sweeps_a, sweeps_b, non_sweep_pct
    one_all_pct
    avg_total_sets, ATP, PS, SS

    Per-player bounce-back (lost s1, won s2 vs this opponent):
      a_bounce_pct, a_bounce_n
      b_bounce_pct, b_bounce_n

    Per-player sweep resistance (lost s1 AND s2, won s3 vs this opponent):
      a_sr_pct, a_sr_n
      b_sr_pct, b_sr_n

    window = "ALL" | "L10" | "L20" | "L30" | "L60"
    """
    key = tuple(sorted([player_a, player_b]))
    if key not in h2h_index:
        return None

    matches = h2h_index[key]

    # Apply recency window (list is newest-first)
    if window == "L10":
        matches = matches[:10]
    elif window == "L20":
        matches = matches[:20]
    elif window == "L30":
        matches = matches[:30]
    elif window == "L60":
        matches = matches[:60]

    total = len(matches)
    if total == 0:
        return _empty_stats()

    # Win counts
    a_wins = sum(1 for m in matches if m["winner"] == player_a)
    b_wins = total - a_wins

    # Average total sets
    avg_total_sets = sum(m["sets1"] + m["sets2"] for m in matches) / total

    # Sweeps (winner took all sets, loser took zero)
    def is_sweep_by(m, player_name):
        if player_name == m["player1"]:
            return m["sets1"] == len(m["parsed_sets"]) and m["sets2"] == 0
        else:
            return m["sets2"] == len(m["parsed_sets"]) and m["sets1"] == 0

    sweeps_a = sum(1 for m in matches if is_sweep_by(m, player_a))
    sweeps_b = sum(1 for m in matches if is_sweep_by(m, player_b))

    non_sweep     = sum(1 for m in matches if not (is_sweep_by(m, player_a) or is_sweep_by(m, player_b)))
    non_sweep_pct = non_sweep / total

    # 1-All %
    one_all_count = sum(1 for m in matches if is_1all(m["parsed_sets"]))
    one_all_pct   = one_all_count / total

    # Averages
    avg_ATP = sum(m["ATP"]        for m in matches) / total
    avg_PS  = sum(abs(m["PS"])    for m in matches) / total
    avg_SS  = sum(abs(m["SS"])    for m in matches) / total

    last_played = matches[0]["date"]

    # --------------------------------------------------
    # Bounce-back % (BB%)
    # Lost s1, won s2 — vs this specific opponent
    # --------------------------------------------------
    def player_bounce_pct(player_name):
        """
        Numerator:   matches where player lost s1 AND won s2
        Denominator: matches where player lost s1
        Returns (pct, n) where n = denominator count
        """
        # p1_col = 1 means player1 won that set
        lost_s1 = [
            m for m in matches
            if len(m["parsed_sets"]) >= 2 and (
                (m["player1"] == player_name and m["s1_winner"] == 2) or
                (m["player2"] == player_name and m["s1_winner"] == 1)
            )
        ]
        if not lost_s1:
            return 0, 0

        won_s2 = sum(
            1 for m in lost_s1
            if (m["player1"] == player_name and m["s2_winner"] == 1) or
               (m["player2"] == player_name and m["s2_winner"] == 2)
        )
        return won_s2 / len(lost_s1), len(lost_s1)

    a_bounce_pct, a_bounce_n = player_bounce_pct(player_a)
    b_bounce_pct, b_bounce_n = player_bounce_pct(player_b)

    # --------------------------------------------------
    # Sweep resistance % (SR%)
    # Lost s1 AND s2 (down 2-0), won s3 — vs this opponent
    # --------------------------------------------------
    def player_sr_pct(player_name):
        """
        Numerator:   matches where player was down 2-0 AND won s3
        Denominator: matches where player was down 2-0
        Returns (pct, n) where n = denominator count
        """
        down_2_0 = [
            m for m in matches
            if len(m["parsed_sets"]) >= 3 and (
                (m["player1"] == player_name and m["s1_winner"] == 2 and m["s2_winner"] == 2) or
                (m["player2"] == player_name and m["s1_winner"] == 1 and m["s2_winner"] == 1)
            )
        ]
        if not down_2_0:
            return 0, 0

        won_s3 = sum(
            1 for m in down_2_0
            if m["s3_winner"] is not None and (
                (m["player1"] == player_name and m["s3_winner"] == 1) or
                (m["player2"] == player_name and m["s3_winner"] == 2)
            )
        )
        return won_s3 / len(down_2_0), len(down_2_0)

    a_sr_pct, a_sr_n = player_sr_pct(player_a)
    b_sr_pct, b_sr_n = player_sr_pct(player_b)

    # --------------------------------------------------
    # Exact set count percentages (3Set%, 4Set%, 5Set%)
    # --------------------------------------------------
    pct_3sets = sum(1 for m in matches if len(m["parsed_sets"]) == 3) / total
    pct_4sets = sum(1 for m in matches if len(m["parsed_sets"]) == 4) / total
    pct_5sets = sum(1 for m in matches if len(m["parsed_sets"]) == 5) / total

    # --------------------------------------------------
    # Slow starter stats
    # S1W%: set 1 win rate vs this opponent
    # Recovery%: win rate when losing set 1 (lost s1, won match)
    # --------------------------------------------------
    def player_slow_starter(player_name):
        """
        Returns:
          s1w_pct      - % of matches where player won set 1
          recovery_pct - % of set-1-loss matches where player still won
          recovery_n   - denominator for recovery_pct (times player lost s1)
        """
        s1_wins = sum(
            1 for m in matches
            if (m["player1"] == player_name and m["s1_winner"] == 1) or
               (m["player2"] == player_name and m["s1_winner"] == 2)
        )
        s1w_pct = s1_wins / total

        lost_s1 = [
            m for m in matches
            if (m["player1"] == player_name and m["s1_winner"] == 2) or
               (m["player2"] == player_name and m["s1_winner"] == 1)
        ]
        recovery_n = len(lost_s1)

        if recovery_n == 0:
            return s1w_pct, 0, 0

        recovered = sum(1 for m in lost_s1 if m["winner"] == player_name)
        recovery_pct = recovered / recovery_n

        return s1w_pct, recovery_pct, recovery_n

    a_s1w_pct, a_recovery_pct, a_recovery_n = player_slow_starter(player_a)
    b_s1w_pct, b_recovery_pct, b_recovery_n = player_slow_starter(player_b)

    # Slow starter score = P(loses s1) × P(wins match | lost s1)
    # Represents the probability of the specific scenario: lose s1, win match
    a_ss_score = (1 - a_s1w_pct) * a_recovery_pct
    b_ss_score = (1 - b_s1w_pct) * b_recovery_pct

    return {
        "matches":        total,
        "a_wins":         a_wins,
        "b_wins":         b_wins,
        "win_pct":        a_wins / total,
        "last_played":    last_played,
        "sweeps_a":       sweeps_a,
        "sweeps_b":       sweeps_b,
        "non_sweep_pct":  non_sweep_pct,
        "one_all_pct":    one_all_pct,
        "avg_total_sets": avg_total_sets,
        "ATP":            avg_ATP,
        "PS":             avg_PS,
        "SS":             avg_SS,
        # Bounce-back
        "a_bounce_pct":   a_bounce_pct,
        "a_bounce_n":     a_bounce_n,
        "b_bounce_pct":   b_bounce_pct,
        "b_bounce_n":     b_bounce_n,
        # Sweep resistance
        "a_sr_pct":       a_sr_pct,
        "a_sr_n":         a_sr_n,
        "b_sr_pct":       b_sr_pct,
        "b_sr_n":         b_sr_n,
        # Exact set count percentages
        "pct_3sets":      pct_3sets,
        "pct_4sets":      pct_4sets,
        "pct_5sets":      pct_5sets,
        # Slow starter
        "a_s1w_pct":      a_s1w_pct,
        "a_recovery_pct": a_recovery_pct,
        "a_recovery_n":   a_recovery_n,
        "a_ss_score":     a_ss_score,
        "b_s1w_pct":      b_s1w_pct,
        "b_recovery_pct": b_recovery_pct,
        "b_recovery_n":   b_recovery_n,
        "b_ss_score":     b_ss_score,
    }


def _empty_stats():
    """Zero-value stats dict returned when a pair has no H2H history."""
    return {
        "matches":        0,
        "a_wins":         0,
        "b_wins":         0,
        "win_pct":        0,
        "last_played":    None,
        "sweeps_a":       0,
        "sweeps_b":       0,
        "non_sweep_pct":  0,
        "one_all_pct":    0,
        "avg_total_sets": 0,
        "ATP":            0,
        "PS":             0,
        "SS":             0,
        "a_bounce_pct":   0,
        "a_bounce_n":     0,
        "b_bounce_pct":   0,
        "b_bounce_n":     0,
        "a_sr_pct":       0,
        "a_sr_n":         0,
        "b_sr_pct":       0,
        "b_sr_n":         0,
        # Exact set count percentages
        "pct_3sets":      0,
        "pct_4sets":      0,
        "pct_5sets":      0,
        # Slow starter
        "a_s1w_pct":      0,
        "a_recovery_pct": 0,
        "a_recovery_n":   0,
        "a_ss_score":     0,
        "b_s1w_pct":      0,
        "b_recovery_pct": 0,
        "b_recovery_n":   0,
        "b_ss_score":     0,
    }