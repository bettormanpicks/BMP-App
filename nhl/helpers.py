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
# Player Analysis
# -------------------------------
def analyze_nhl_players(
    nhl_df,
    nhl_stats_selected,
    stat_map,
    recent_n=None,
    recent_pct=0.8,
    filter_teams=None,
    team_def_df=pd.DataFrame(),
    player_type="Skaters",
    b2b_map=None,
    inj_status_map=None,
):
    """
    Main analysis engine for NHL players.
    Returns DataFrame ready for display.
    """

    nhl_df = nhl_df.copy().fillna(0)
    nhl_df.columns = dedupe_columns(nhl_df.columns)

    # ✅ Convert game_date to datetime to ensure proper sorting
    nhl_df['game_date'] = pd.to_datetime(nhl_df['game_date'], errors='coerce')

    if player_type == "Skaters":
        df_players = nhl_df[(nhl_df["is_goalie"] == False) & (nhl_df["toi_minutes"] > 8)].copy()
    else:
        df_players = nhl_df[(nhl_df["is_goalie"] == True) & (nhl_df["toi_minutes"] > 40)].copy()

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
        opp = None
        if "opp_map" in locals():
            opp = filter_teams.get(team) if filter_teams else None
        rec["Opp"] = opp or ""

        # Attach opponent defense
        if not team_def_df.empty and opp in team_def_df.index:
            if player_type == "Skaters":
                rec["GA_A"] = team_def_df.loc[opp, "GA_A"]
                rec["GA_R"] = int(team_def_df.loc[opp, "GA_R"])
                rec["SA_A"] = team_def_df.loc[opp, "SA_A"]
                rec["SA_R"] = int(team_def_df.loc[opp, "SA_R"])
            else:
                rec["GF_A"] = team_def_df.loc[opp, "GF_A"]
                rec["GF_R"] = int(team_def_df.loc[opp, "GF_R"])
                rec["SF_A"] = team_def_df.loc[opp, "SF_A"]
                rec["SF_R"] = int(team_def_df.loc[opp, "SF_R"])
        else:
            if player_type == "Skaters":
                rec["GA_A"] = rec["GA_R"] = rec["SA_A"] = rec["SA_R"] = None
            else:
                rec["GF_A"] = rec["GF_R"] = rec["SF_A"] = rec["SF_R"] = None

        # ✅ Sort by game_date descending and slice recent_n if specified
        g = g.sort_values("game_date", ascending=False)
        if recent_n is not None:
            g = g.head(recent_n)

        for stat, col in stat_map.items():
            if stat not in nhl_stats_selected:
                continue
            rec[f"{stat}@{int(recent_pct*100)}"] = hit_rate_threshold(g[col], recent_pct*100)

        rows.append(rec)

    return pd.DataFrame(rows)
