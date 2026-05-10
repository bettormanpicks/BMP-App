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
# MAIN PLAYER QUERY FUNCTION
# -------------------------
def get_player_game_log(
    box_df,
    player,
    window="L5",
    opponent=None,
    pitcher=None,
    all_opponents=False
):
    df = box_df[box_df["player"] == player]

    if df.empty:
        return pd.DataFrame()

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

    return df