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
# Player Analysis (with reactive opponent window)
# -------------------------------
def analyze_nhl_players(
    nhl_df,
    nhl_stats_selected,
    stat_map,
    recent_n=None,
    recent_pct=None,
    filter_teams=None,
    player_type=None,
    b2b_map=None,
    inj_status_map=None,
    nhlteamgames_df=None,   # dataframe with every team/game row
    opp_recent_n=None       # number of recent games for opponent window
):
    """
    Main analysis engine for NHL players with dynamic opponent window.

    nhl_df: raw uploaded CSV
    nhl_stats_selected: list of stats user selected
    stat_map: {"Display": "csv_column"}
    recent_n: player performance window (L5/L10/ALL)
    recent_pct: decimal pct (0-1)
    filter_teams: optional set of team codes to filter
    player_type: "Skaters" or "Goalies"
    b2b_map: optional dict {team: B2B status}
    inj_status_map: optional dict {norm_name(player): status}
    nhlteamgames_df: dataframe with each team/game row
    opp_recent_n: opponent window (L5/L10/ALL)
    """
    if player_type is None or recent_pct is None:
        raise ValueError("player_type and recent_pct must be provided by the caller.")

    nhl_df = nhl_df.copy().fillna(0)
    nhl_df.columns = dedupe_columns(nhl_df.columns)

    # Filter by player type & TOI
    if player_type == "Skaters":
        df_players = nhl_df[(nhl_df["is_goalie"] == False) & (nhl_df["toi_minutes"] > 8)].copy()
    else:
        df_players = nhl_df[(nhl_df["is_goalie"] == True) & (nhl_df["toi_minutes"] > 40)].copy()

    rows = []
    grouped = df_players.groupby(["player_id", "player_name", "team", "position"])

    # Precompute opponent stats if nhlteamgames_df and opp_recent_n are provided
    opp_stats = {}
    if nhlteamgames_df is not None and opp_recent_n is not None:
        nhlteamgames_df = nhlteamgames_df.copy()
        nhlteamgames_df["game_date"] = pd.to_datetime(nhlteamgames_df["GAME_DATE"])

        teams = nhlteamgames_df["TEAM"].unique()
        opp_avgs = {}

        # Compute averages per team
        for team in teams:
            team_games = nhlteamgames_df[nhlteamgames_df["TEAM"] == team].sort_values("game_date", ascending=False)
            if opp_recent_n:
                team_games = team_games.head(opp_recent_n)

            if player_type == "Skaters":
                opp_avgs[team] = {
                    "GA_A": team_games["GA"].mean(),
                    "SA_A": team_games["SA"].mean()
                }
            else:
                opp_avgs[team] = {
                    "GF_A": team_games["GF"].mean(),
                    "SF_A": team_games["SF"].mean()
                }

        # Compute ranks across all teams
        if player_type == "Skaters":
            ga_series = pd.Series({t: v["GA_A"] for t, v in opp_avgs.items()})
            sa_series = pd.Series({t: v["SA_A"] for t, v in opp_avgs.items()})
            ga_rank = ga_series.rank(method="min", ascending=True).astype(int)
            sa_rank = sa_series.rank(method="min", ascending=True).astype(int)
            for t in teams:
                opp_avgs[t]["GA_R"] = ga_rank[t]
                opp_avgs[t]["SA_R"] = sa_rank[t]
        else:
            gf_series = pd.Series({t: v["GF_A"] for t, v in opp_avgs.items()})
            sf_series = pd.Series({t: v["SF_A"] for t, v in opp_avgs.items()})
            gf_rank = gf_series.rank(method="min", ascending=False).astype(int)
            sf_rank = sf_series.rank(method="min", ascending=False).astype(int)
            for t in teams:
                opp_avgs[t]["GF_R"] = gf_rank[t]
                opp_avgs[t]["SF_R"] = sf_rank[t]

        opp_stats = opp_avgs

    # --- Iterate players ---
    for (pid, name, team, pos), g in grouped:

        if filter_teams and team not in filter_teams:
            continue

        rec = {"Player": name, "Pos": pos, "Team": team, "Gms": len(g)}

        # B2B
        rec["B2B"] = b2b_map.get(team, "N") if b2b_map else "N"

        # Injury status
        rec["Status"] = inj_status_map.get(norm_name(name), "A") if inj_status_map else "A"

        # Opponent team
        rec["Opp"] = ""  # Optional: can fill if you have schedule mapping

        # Attach opponent stats
        if team in opp_stats:
            rec.update(opp_stats[team])
        else:
            if player_type == "Skaters":
                rec.update({"GA_A": None, "GA_R": None, "SA_A": None, "SA_R": None})
            else:
                rec.update({"GF_A": None, "GF_R": None, "SF_A": None, "SF_R": None})

        # Player recent form
        g_sorted = g.sort_values("game_date", ascending=False)
        if recent_n is not None:
            g_sorted = g_sorted.head(recent_n)

        prefix = f"L{recent_n}" if recent_n else ""  # L5/L10 or "" for ALL

        # Compute hit rate thresholds
        for stat, col in stat_map.items():
            if stat not in nhl_stats_selected:
                continue
            col_name = f"{prefix}{stat}@{int(recent_pct*100)}" if prefix else f"{stat}@{int(recent_pct*100)}"
            rec[col_name] = hit_rate_threshold(g_sorted[col], recent_pct*100)

        rows.append(rec)

    return pd.DataFrame(rows)
