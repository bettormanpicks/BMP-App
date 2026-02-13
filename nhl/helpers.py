# nhl/helpers.py

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import requests
from shared.utils import hit_rate_threshold, dedupe_columns, norm_name

# -------------------------------
# Fetch NHL Injuries
# -------------------------------
@st.cache_data(ttl=900)
def get_nhl_injuries(headless=True):
    return fetch_nhl_injuries_selenium(headless=headless)

# -------------------------------
# Schedule / Teams
# -------------------------------
@st.cache_data(ttl=900)
def get_nhl_todays_schedule(target_date=None):
    """
    Returns (teams_set, opponent_map) from NHL API for a given date.
    If no date provided, defaults to today.
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    teams, opp_map = set(), {}
    try:
        r = requests.get(f"https://api-web.nhle.com/v1/schedule/{target_date}", timeout=15)
        r.raise_for_status()
        data = r.json()
        for block in data.get("gameWeek", []):
            if block.get("date") != target_date:
                continue
            for g in block.get("games", []):
                away = (g.get("awayTeam") or {}).get("abbrev")
                home = (g.get("homeTeam") or {}).get("abbrev")
                if away and home:
                    teams.add(away)
                    teams.add(home)
                    opp_map[away] = home
                    opp_map[home] = away
    except Exception:
        # Optional: log or st.warning
        pass

    return teams, opp_map


def get_nhl_teams_on_date(date_str):
    """
    Returns only the set of NHL teams playing on a given date.
    """
    teams, _ = get_nhl_todays_schedule(date_str)
    return teams


# -------------------------------
# B2B Logic
# -------------------------------
def compute_nhl_b2b(teams_today, teams_yesterday, teams_tomorrow):
    """
    Returns a dict {team: B2B status 'N','1','2'}
    """
    b2b = {}
    for team in teams_today:
        if team in teams_yesterday:
            b2b[team] = "2"
        elif team in teams_tomorrow:
            b2b[team] = "1"
        else:
            b2b[team] = "N"
    return b2b

# -------------------------------
# Player Analysis (New Version)
# -------------------------------
def analyze_nhl_players(
    nhl_df,
    nhl_stats_selected,
    stat_map,
    recent_n=None,
    recent_pct=None,           # Must be provided by caller (from slider)
    filter_teams=None,
    team_games_csv="nhl/data/nhlteamgames.csv",  # New CSV path
    player_type=None,           # Must be provided by caller (Skaters or Goalies)
    b2b_map=None,
    inj_status_map=None,
):
    """
    Main analysis engine for NHL players with dynamic opponent stats.

    nhl_df: raw uploaded CSV (players)
    nhl_stats_selected: list of stats user selected
    stat_map: {"Display": "csv_column"}
    recent_n: number of recent games to consider for player (None = all)
    recent_pct: decimal pct (0-1), must come from sidebar
    filter_teams: optional set of team codes to filter
    team_games_csv: path to nhlteamgames.csv
    player_type: "Skaters" or "Goalies"
    b2b_map: optional dict {team: B2B status}
    inj_status_map: optional dict {norm_name(player): status}
    """
    if player_type is None or recent_pct is None:
        raise ValueError("player_type and recent_pct must be provided by the caller.")

    nhl_df = nhl_df.copy().fillna(0)
    nhl_df.columns = dedupe_columns(nhl_df.columns)

    # -------------------------------
    # Filter by player type & TOI
    # -------------------------------
    if player_type == "Skaters":
        df_players = nhl_df[(nhl_df["is_goalie"] == False) & (nhl_df["toi_minutes"] > 8)].copy()
    else:
        df_players = nhl_df[(nhl_df["is_goalie"] == True) & (nhl_df["toi_minutes"] > 40)].copy()

    # -------------------------------
    # Load team game log for opponent stats
    # -------------------------------
    team_games_df = pd.read_csv(team_games_csv)
    team_games_df["GAME_DATE"] = pd.to_datetime(team_games_df["GAME_DATE"])

    rows = []
    grouped = df_players.groupby(["player_id", "player_name", "team", "position"])

    for (pid, name, team, pos), g in grouped:

        if filter_teams and team not in filter_teams:
            continue

        rec = {"Player": name, "Pos": pos, "Team": team, "Gms": len(g)}

        # B2B
        rec["B2B"] = b2b_map.get(team, "N") if b2b_map else "N"

        # Injury status
        rec["Status"] = inj_status_map.get(norm_name(name), "A") if inj_status_map else "A"

        # Opponent
        opp = g["opponent"].iloc[-1] if "opponent" in g.columns else None
        rec["Opp"] = opp or ""

        # -------------------------------
        # Attach opponent stats (dynamic, windowed)
        # -------------------------------
        if opp:
            # Filter nhlteamgames for opponent
            opp_rows = team_games_df[team_games_df["TEAM"] == opp].sort_values("GAME_DATE", ascending=False)

            # Apply recent_n window if provided
            if recent_n is not None:
                opp_rows = opp_rows.head(recent_n)

            # Compute averages & ranks
            if not opp_rows.empty:
                if player_type == "Skaters":
                    rec["GA_A"] = round(opp_rows["GF"].mean(), 2)
                    rec["SA_A"] = round(opp_rows["SF"].mean(), 2)
                    rec["GA_R"] = int(opp_rows["GF"].rank(method="min", ascending=True).iloc[-1])
                    rec["SA_R"] = int(opp_rows["SF"].rank(method="min", ascending=True).iloc[-1])
                else:
                    rec["GF_A"] = round(opp_rows["GF"].mean(), 2)
                    rec["SF_A"] = round(opp_rows["SF"].mean(), 2)
                    rec["GF_R"] = int(opp_rows["GF"].rank(method="min", ascending=False).iloc[-1])
                    rec["SF_R"] = int(opp_rows["SF"].rank(method="min", ascending=False).iloc[-1])
            else:
                # fallback if no data
                if player_type == "Skaters":
                    rec["GA_A"] = rec["GA_R"] = rec["SA_A"] = rec["SA_R"] = None
                else:
                    rec["GF_A"] = rec["GF_R"] = rec["SF_A"] = rec["SF_R"] = None
        else:
            # fallback if no opponent
            if player_type == "Skaters":
                rec["GA_A"] = rec["GA_R"] = rec["SA_A"] = rec["SA_R"] = None
            else:
                rec["GF_A"] = rec["GF_R"] = rec["SF_A"] = rec["SF_R"] = None

        # -------------------------------
        # Recent form / hit rate thresholds
        # -------------------------------
        g_sorted = g.sort_values("game_date", ascending=False)
        if recent_n is not None:
            g_sorted = g_sorted.head(recent_n)

        prefix = f"L{recent_n}" if recent_n else ""  # L5, L10, or ALL

        for stat, col in stat_map.items():
            if stat not in nhl_stats_selected:
                continue
            col_name = f"{prefix}{stat}@{int(recent_pct*100)}" if prefix else f"{stat}@{int(recent_pct*100)}"
            rec[col_name] = hit_rate_threshold(g_sorted[col], recent_pct*100)

        rows.append(rec)

    return pd.DataFrame(rows)
