#shared/utils.py

import pandas as pd
import math
from datetime import datetime, timedelta
import pytz
import streamlit as st
from typing import Iterable, Union

def get_nba_today(cutoff_hour_ct=3):
    """
    Returns the NBA 'logical date' using a CT cutoff.
    Before cutoff_hour_ct, treat today as yesterday.
    """
    ct = pytz.timezone("US/Central")
    now_ct = datetime.now(ct)

    if now_ct.hour < cutoff_hour_ct:
        nba_date = (now_ct - timedelta(days=1)).date()
    else:
        nba_date = now_ct.date()

    return nba_date

def hit_rate_threshold(values, pct):
    """
    Lowest stat value hit in at least pct% of games.
    Accepts pandas Series, list, or iterable.
    """
    if values is None:
        return 0

    # Convert to numeric pandas Series safely
    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return 0

    values = values.sort_values()
    n = len(values)
    k = math.ceil((pct / 100.0) * n)
    k = min(max(k, 1), n)

    return values.iloc[-k]

def trim_df_to_recent_82(df, date_col="GAME_DATE"):
    # Keep behavior consistent with your original code (works for NBA GAME_DATE)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return (
        df.sort_values(["player_id", date_col], ascending=[True, False])
          .groupby("player_id", group_keys=False)
          .head(82)
          .reset_index(drop=True)
    )

def dedupe_columns(cols):
    counts = {}
    new_cols = []
    for c in cols:
        if c not in counts:
            counts[c] = 0
            new_cols.append(c)
        else:
            counts[c] += 1
            new_cols.append(f"{c}_{counts[c]}")
    return new_cols

def strip_display_ids(df):
    return df.drop(columns=[c for c in df.columns if c.lower() in ("player_id",)], errors="ignore")

def norm_name(s):
    s = str(s).lower().replace(".", "").replace(",", "").strip()
    parts = s.split()
    if len(parts) == 1:
        return parts[0]
    first_initial = parts[0][0]
    last = parts[-1]
    return f"{first_initial} {last}"

@st.cache_data(ttl=3600)
def get_teams_playing_on_date(schedule_data, target_date):
    """
    schedule_data: loaded JSON dict (full season)
    target_date: datetime.date
    Returns: set of team tricodes playing on that date
    """
    teams = set()
    target_str = target_date.strftime("%Y-%m-%d")

    # ---- Simple format ----
    if "games" in schedule_data:
        for g in schedule_data["games"]:
            if g.get("gameDate") == target_str:
                home = g.get("home")
                away = g.get("away")
                if home and away:
                    teams.add(home.upper())
                    teams.add(away.upper())
        return teams

    # ---- NBA API format ----
    for day in schedule_data.get("leagueSchedule", {}).get("gameDates", []):
        raw = day.get("gameDate", "")
        try:
            parsed = pd.to_datetime(raw).date()
        except:
            continue

        if parsed != target_date:
            continue

        for g in day.get("games", []):
            teams.add(g["homeTeam"]["teamTricode"].upper())
            teams.add(g["awayTeam"]["teamTricode"].upper())

    return teams
