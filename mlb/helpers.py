import pandas as pd
import streamlit as st
import pytz
from datetime import datetime

# -------------------------
# LOAD + CACHE DATA
# -------------------------
@st.cache_data
def load_mlb_raw_data():
    box = pd.read_csv("mlb/data/mlb_cleaned_boxscores.csv")
    schedule = pd.read_csv("mlb/data/2026_mlb_schedule.csv")  # ← remove dtype override

    box["date"] = pd.to_datetime(box["date"], utc=True)
    schedule["date"] = pd.to_datetime(schedule["date"], utc=True)

    return box, schedule

def get_today_schedule(schedule_df):
    from datetime import timezone
    today = datetime.now(timezone.utc).date()

    # Ensure tz-awareness survived the cache round-trip
    if schedule_df["date"].dt.tz is None:
        schedule_df = schedule_df.copy()
        schedule_df["date"] = schedule_df["date"].dt.tz_localize("UTC")

    return schedule_df[schedule_df["date"].dt.date == today]

def build_today_matchups(schedule_df):
    matchups = {}

    for _, row in schedule_df.iterrows():
        matchups[row["home_team"]] = {
            "opp": row["away_team"],
            "pitcher": row["away_pitcher"]
        }
        matchups[row["away_team"]] = {
            "opp": row["home_team"],
            "pitcher": row["home_pitcher"]
        }

    return matchups

# -------------------------
# PERFORMANCE WINDOW HELPER
# -------------------------
def apply_performance_window(df, window):
    df = df.sort_values("date", ascending=False)

    if window == "L5":
        return df.head(5)
    elif window == "L10":
        return df.head(10)
    elif window == "L30":
        return df.head(30)
    else:  # ALL
        return df


# -------------------------
# SAFE AB CALCULATION
# -------------------------
def calculate_ab(df):
    if "at_bats" in df.columns:
        return df["at_bats"].sum()

    # fallback if not present
    pa = df["plate_appearances"].sum()
    walks = df["walks"].sum() if "walks" in df.columns else 0
    return pa - walks


# -------------------------
# BATTER STATS
# -------------------------
def compute_batter_stats(df):
    if df.empty:
        return {
            "games": 0,
            "ab": 0,
            "hits": 0,
            "hr": 0,
            "hrr": 0,
            "avg": None,
            "hr_rate": None,
            "hrr_per_game": None,
            "k_rate": None
        }

    games = df["game_id"].nunique()
    hits = df["hits"].sum()
    hr = df["home_runs"].sum()
    hrr = df["hrr"].sum()
    ab = calculate_ab(df)

    pa = df["plate_appearances"].sum()
    k = df["strikeouts"].sum()

    return {
        "games": games,
        "AB": ab,
        "PA": pa,
        "H": hits,
        "HR": hr,
        "HRR": hrr,
        "AVG": (hits / ab) if ab else None,
        "HR_rate": (hr / ab) if ab else None,
        "HRRpg": (hrr / games) if games else None,
        "K_rate": (k / pa) if pa else None
    }


# -------------------------
# PITCHER STATS
# -------------------------
def compute_pitcher_stats(df):
    if df.empty:
        return {
            "games": 0,
            "ip": 0,
            "k": 0,
            "k_per_9": None,
            "era": None,
            "whip": None
        }

    games = df["game_id"].nunique()
    outs = df["outs"].sum()
    ip = outs / 3 if outs else 0

    k = df["strikeouts_pitching"].sum()
    er = df["earned_runs"].sum()
    walks = df["walks_pitching"].sum()
    hits = df["hits_allowed"].sum()

    return {
        "games": games,
        "IP": ip,
        "K": k,
        "Kp9": (k * 9 / ip) if ip else None,
        "ERA": (er * 9 / ip) if ip else None,
        "WHIP": ((walks + hits) / ip) if ip else None
    }


# -------------------------
# MAIN PLAYER QUERY FUNCTION
# -------------------------
def get_player_stats(
    box_df,
    player,
    window="L5",
    opponent=None,
    pitcher=None,
    all_opponents=False
):
    df = box_df[box_df["player"] == player]

    if df.empty:
        return {}

    is_pitcher = df["is_pitcher"].iloc[0]

    # -------------------------
    # APPLY FILTERS
    # -------------------------
    if not all_opponents:
        if not is_pitcher:
            if pitcher:
                df = df[df["opposing_pitcher"] == pitcher]
            elif opponent:
                df = df[df["opponent"] == opponent]
        else:
            if opponent:
                df = df[df["opponent"] == opponent]

    if not is_pitcher:
        df = df[
            (df["plate_appearances"] > 0) &
            (df["opposing_pitcher"].notna()) &
            (df["opposing_pitcher"] != "Unknown")
        ]

    # -------------------------
    # APPLY WINDOW
    # -------------------------
    df = apply_performance_window(df, window)

    # -------------------------
    # COMPUTE STATS
    # -------------------------
    if is_pitcher:
        stats = compute_pitcher_stats(df)
    else:
        stats = compute_batter_stats(df)

    # -------------------------
    # SMALL SAMPLE FLAG
    # -------------------------
    if "PA" in stats:
        stats["small_sample"] = stats["PA"] < 20
    else:
        stats["small_sample"] = stats["games"] < 5

    return stats