#shared/utils.py

import pandas as pd
import math
from datetime import datetime, timedelta
import pytz
import streamlit as st
from typing import Iterable, Union

def get_league_today(cutoff_hour_ct=3):
    """
    Returns the logical sports date using a CT cutoff.
    Before the cutoff hour, treat today as the previous slate day.
    """
    ct = pytz.timezone("US/Central")
    now_ct = datetime.now(ct)

    if now_ct.hour < cutoff_hour_ct:
        return (now_ct - timedelta(days=1)).date()
    else:
        return now_ct.date()

def hit_rate_threshold(values, pct):
    """
    Returns the highest stat floor S such that
    the player achieved >= S in at least pct% of games.
    """

    if values is None:
        return 0

    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    values = pd.to_numeric(values, errors="coerce").dropna()

    if values.empty:
        return 0

    n = len(values)
    target = pct / 100.0

    # Check candidate floors from high → low
    for s in sorted(values.unique(), reverse=True):
        hit_rate = (values >= s).sum() / n
        if hit_rate >= target:
            return s

    return values.min()

def compute_hit_rates(group: pd.DataFrame, stat_map: dict, stats_selected: list, recent_n=None, pct=0.8):
    """
    Compute hit rate thresholds for a player's recent games.

    Parameters
    ----------
    group : pd.DataFrame
        Player's game log (already filtered by player_id)
    stat_map : dict
        Mapping of display stat → DataFrame column, e.g. {"G": "goals", "A": "assists"}
    stats_selected : list
        Stats to calculate, e.g. ["G", "A", "P"]
    recent_n : int | None
        Number of most recent games to consider. If None, uses all games
    pct : float
        Hit rate percentage (0–1). E.g., 0.8 for 80%.

    Returns
    -------
    dict
        Keys are stat names (like "G") or tagged (like "L5G@80"), values are thresholds
    """
    g = group.sort_values("game_date", ascending=False)
    if recent_n is not None:
        g = g.head(recent_n)

    results = {}
    pct_pct = pct * 100

    for stat in stats_selected:
        if stat not in stat_map:
            continue
        col = stat_map[stat]
        if col not in g.columns:
            results[stat] = None
            continue
        results[stat] = hit_rate_threshold(g[col], pct_pct)

    return results

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
