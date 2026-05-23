# nhl/helpers.py

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import requests
from shared.utils import get_central_today, hit_rate_threshold, dedupe_columns, norm_name

# -------------------------------
# Load NHL Static Data (game logs + team games)
# No TTL — these CSVs only change when your GitHub Action pushes a new file.
# Bundling injuries here was wrong: injuries need to refresh mid-session.
# -------------------------------
@st.cache_data
def load_nhl_raw_data():
    player_df = pd.read_csv("nhl/data/nhlplayergamelogs.csv").fillna(0)
    team_games_df = pd.read_csv("nhl/data/nhlteamgames.csv").fillna(0)
    return player_df, team_games_df

# -------------------------------
# Load NHL Injury Data (separate, TTL-cached so it refreshes mid-session)
# TTL matches the GitHub Action cadence (~15 min). Injuries are served from
# the local CSV written by the action, no Selenium scrape needed at runtime.
# -------------------------------
@st.cache_data(ttl=900)
def load_nhl_injuries():
    try:
        df = pd.read_csv("nhl/data/nhlplayerstatus.csv").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

# -------------------------------
# Legacy Selenium-based fetcher kept for reference but not called at runtime.
# The GitHub Action writes nhlplayerstatus.csv; load_nhl_injuries() reads that.
# -------------------------------
@st.cache_data(ttl=900)
def get_nhl_injuries(headless=True):
    try:
        return fetch_nhl_injuries_selenium(headless=headless)
    except Exception:
        # fetch_nhl_injuries_selenium is only available when Selenium deps are
        # installed (not on Streamlit Community Cloud). Fall back to the CSV.
        return load_nhl_injuries()

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
        target_date = get_central_today()

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
# Opponent Window Stats (cached)
# -----------------------------
@st.cache_data
def compute_opponent_window_stats(nhlteamgames_df, player_type="Skaters", window_n=None):
    """
    Compute and CACHE per-team defensive (Skaters) or offensive (Goalies) averages
    and ranks for a given game window.

    Previously this logic lived uncached inside analyze_nhl_players and ran on
    every UI interaction. Now it is cached keyed on (player_type, window_n) so
    the heavy team-loop only re-runs when those inputs change.

    Parameters:
    - nhlteamgames_df: DataFrame with columns GAME_DATE, TEAM, GF, GA, SF, SA
    - player_type: "Skaters" or "Goalies"
    - window_n: number of recent games per team (5, 10, or None = ALL)

    Returns a dict {team: {stat_avg: float, stat_rank: int, ...}}
    """
    df = nhlteamgames_df.copy()
    df["game_date"] = pd.to_datetime(df["GAME_DATE"], errors="coerce").dt.date
    df = df.dropna(subset=["game_date"])

    teams = df["TEAM"].unique()
    opp_avgs = {}

    for team in teams:
        team_games = df[df["TEAM"] == team].sort_values("game_date", ascending=False)
        if window_n is not None:
            team_games = team_games.head(int(window_n))

        if player_type == "Skaters":
            opp_avgs[team] = {
                "GA_A": team_games["GA"].mean(),
                "SA_A": team_games["SA"].mean(),
            }
        else:
            opp_avgs[team] = {
                "GF_A": team_games["GF"].mean(),
                "SF_A": team_games["SF"].mean(),
            }

    # Compute cross-team ranks in one vectorised pass
    if player_type == "Skaters":
        ga_s = pd.Series({t: v["GA_A"] for t, v in opp_avgs.items()})
        sa_s = pd.Series({t: v["SA_A"] for t, v in opp_avgs.items()})
        ga_r = ga_s.rank(method="min", ascending=True).astype(int)
        sa_r = sa_s.rank(method="min", ascending=True).astype(int)
        for t in teams:
            opp_avgs[t]["GA_R"] = ga_r[t]
            opp_avgs[t]["SA_R"] = sa_r[t]
            opp_avgs[t]["GA_A"] = round(opp_avgs[t]["GA_A"], 2)
            opp_avgs[t]["SA_A"] = round(opp_avgs[t]["SA_A"], 2)
    else:
        gf_s = pd.Series({t: v["GF_A"] for t, v in opp_avgs.items()})
        sf_s = pd.Series({t: v["SF_A"] for t, v in opp_avgs.items()})
        gf_r = gf_s.rank(method="min", ascending=False).astype(int)
        sf_r = sf_s.rank(method="min", ascending=False).astype(int)
        for t in teams:
            opp_avgs[t]["GF_R"] = gf_r[t]
            opp_avgs[t]["SF_R"] = sf_r[t]
            opp_avgs[t]["GF_A"] = round(opp_avgs[t]["GF_A"], 2)
            opp_avgs[t]["SF_A"] = round(opp_avgs[t]["SF_A"], 2)

    return opp_avgs

# -------------------------------
# Player Analysis (with reactive opponent window)
# -------------------------------
def analyze_nhl_players(
    nhl_df,
    nhl_stats_selected,
    stat_map,
    opp_map=None,
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

    # --- Opponent window stats: delegate to the cached function ---
    # compute_opponent_window_stats is @st.cache_data keyed on (df hash, player_type, window_n)
    # so this heavy team-loop only re-runs when those inputs change, not on every UI rerun.
    opp_stats = {}
    if nhlteamgames_df is not None:
        opp_stats = compute_opponent_window_stats(nhlteamgames_df, player_type, opp_recent_n)

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
        opp_team = opp_map.get(team, "") if opp_map else ""
        rec["Opp"] = opp_team

        # Attach opponent stats (FIXED)
        if opp_team in opp_stats:
            rec.update(opp_stats[opp_team])
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