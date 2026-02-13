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

# -----------------------------
# Reactive Opponent Windows
# -----------------------------
def compute_opponent_window_stats(nhlteamgames_df, player_type="Skaters", window_n=None):
    """
    Returns a DataFrame indexed by TEAM with averages and ranks for the opponent window.
    
    Parameters:
    - nhlteamgames_df: DataFrame with columns ['GAME_ID','GAME_DATE','TEAM','OPP_TEAM','GF','GA','SF','SA']
    - player_type: "Skaters" or "Goalies"
    - window_n: number of recent games to consider (L5, L10), None = ALL
    
    Returns:
    - team_def_df: DataFrame indexed by TEAM, with columns:
        Skaters → GA_A, GA_R, SA_A, SA_R
        Goalies → GF_A, GF_R, SF_A, SF_R
    """
    import pandas as pd

    df = nhlteamgames_df.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    
    records = []

    teams = df["TEAM"].unique()
    for team in teams:
        if player_type == "Skaters":
            # For skaters, opponent window is defensive → we look at GA/SA allowed by the team
            team_games = df[df["TEAM"] == team].sort_values("GAME_DATE", ascending=False)
            if window_n is not None:
                team_games = team_games.head(window_n)
            GA_A = team_games["GA"].mean()
            SA_A = team_games["SA"].mean()
            GA_R = team_games["GA"].rank(method="min").mean()  # optional: can rank all teams after loop
            SA_R = team_games["SA"].rank(method="min").mean()
            records.append({
                "Team": team,
                "GA_A": round(GA_A, 2),
                "GA_R": int(GA_R),
                "SA_A": round(SA_A, 2),
                "SA_R": int(SA_R)
            })
        else:
            # For goalies, opponent window is offensive → look at GF/SF scored by opponent
            team_games = df[df["TEAM"] == team].sort_values("GAME_DATE", ascending=False)
            if window_n is not None:
                team_games = team_games.head(window_n)
            GF_A = team_games["GF"].mean()
            SF_A = team_games["SF"].mean()
            GF_R = team_games["GF"].rank(method="min").mean()
            SF_R = team_games["SF"].rank(method="min").mean()
            records.append({
                "Team": team,
                "GF_A": round(GF_A, 2),
                "GF_R": int(GF_R),
                "SF_A": round(SF_A, 2),
                "SF_R": int(SF_R)
            })

    team_def_df = pd.DataFrame(records).set_index("Team")
    return team_def_df

# -------------------------------
# Player Analysis
# -------------------------------
def analyze_nhl_players(
    nhl_df,
    nhl_stats_selected,
    stat_map,
    recent_n=None,
    recent_pct=None,           # decimal from sidebar (0-1)
    filter_teams=None,
    nhlteamgames_df=None,      # the new nhlteamgames.csv
    player_type=None,          # "Skaters" or "Goalies"
    b2b_map=None,
    inj_status_map=None,
):
    """
    Main NHL player analysis engine with dynamic opponent windowing.

    Returns a DataFrame ready for display.

    Parameters
    ----------
    nhl_df : DataFrame
        Raw NHL player game logs
    nhl_stats_selected : list
        Stats selected by the user (ex: ["G","A","SOG"])
    stat_map : dict
        {"Display Name": "CSV Column Name"}
    recent_n : int or None
        Recent window (5, 10, or None for ALL)
    recent_pct : float
        Hit rate decimal (0-1)
    filter_teams : set
        Optional set of teams to include
    nhlteamgames_df : DataFrame
        Team-level game logs (for opponent windowing)
    player_type : str
        "Skaters" or "Goalies"
    b2b_map : dict
        Optional B2B status per team
    inj_status_map : dict
        Optional injury status per player
    """
    if player_type is None or recent_pct is None:
        raise ValueError("player_type and recent_pct must be provided by the caller.")

    nhl_df = nhl_df.copy().fillna(0)
    nhl_df.columns = dedupe_columns(nhl_df.columns)

    # Filter players by type
    if player_type == "Skaters":
        df_players = nhl_df[(nhl_df["is_goalie"] == False) & (nhl_df["toi_minutes"] > 8)].copy()
    else:
        df_players = nhl_df[(nhl_df["is_goalie"] == True) & (nhl_df["toi_minutes"] > 40)].copy()

    # Compute dynamic opponent window stats if team games provided
    team_def_df = pd.DataFrame()
    if nhlteamgames_df is not None:
        team_def_df = compute_opponent_window_stats(
            nhlteamgames_df=nhlteamgames_df,
            player_type=player_type,
            window_n=recent_n  # L5, L10, or None for ALL
        )

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

        # Attach opponent defense/offense based on window
        if not team_def_df.empty and team in team_def_df.index:
            if player_type == "Skaters":
                rec["GA_A"] = team_def_df.loc[team, "GA_A"]
                rec["GA_R"] = int(team_def_df.loc[team, "GA_R"])
                rec["SA_A"] = team_def_df.loc[team, "SA_A"]
                rec["SA_R"] = int(team_def_df.loc[team, "SA_R"])
            else:
                rec["GF_A"] = team_def_df.loc[team, "GF_A"]
                rec["GF_R"] = int(team_def_df.loc[team, "GF_R"])
                rec["SF_A"] = team_def_df.loc[team, "SF_A"]
                rec["SF_R"] = int(team_def_df.loc[team, "SF_R"])
        else:
            # fallback if no team_def_df
            if player_type == "Skaters":
                rec["GA_A"] = rec["GA_R"] = rec["SA_A"] = rec["SA_R"] = None
            else:
                rec["GF_A"] = rec["GF_R"] = rec["SF_A"] = rec["SF_R"] = None

        # --- Player stat hit rates ---
        # ALL games
        g_all = g.sort_values("game_date", ascending=False)
        prefix_all = ""
        for stat, col in stat_map.items():
            if stat not in nhl_stats_selected:
                continue
            col_name_all = f"{stat}@{int(recent_pct*100)}"
            rec[col_name_all] = hit_rate_threshold(g_all[col], recent_pct*100)

        # Recent window
        if recent_n is not None:
            g_recent = g_all.head(recent_n)
            prefix_recent = f"L{recent_n}"
            for stat, col in stat_map.items():
                if stat not in nhl_stats_selected:
                    continue
                col_name_recent = f"{prefix_recent}{stat}@{int(recent_pct*100)}"
                rec[col_name_recent] = hit_rate_threshold(g_recent[col], recent_pct*100)

        rows.append(rec)

    df_out = pd.DataFrame(rows)
    return df_out