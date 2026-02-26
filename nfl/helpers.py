# =====================================================
# NFL HELPERS (PFR CLEAN DATA)
# =====================================================
import re
import os
import json
import math
from datetime import datetime, date
import pandas as pd

# ------------------------------
# Team utilities
# ------------------------------
TEAM_NAME_TO_CODE = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WSH",
}

# nflreadpy / alternate tricodes → canonical app tricodes
TEAM_CODE_CANONICAL = {
    "GNB": "GB",
    "KAN": "KC",
    "LA": "LAR",
    "LVR": "LV",
    "NWE": "NE",
    "NOR": "NO",
    "SFO": "SF",
    "TAM": "TB",
    "WAS": "WSH",
}

def normalize_team_code(code: str) -> str:
    if not isinstance(code, str):
        return ""
    code = code.strip().upper()
    return TEAM_CODE_CANONICAL.get(code, code)

def safe_upper(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    try:
        return str(x).upper()
    except:
        return ""

def team_name_to_code(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.strip()
    if not name:
        return ""
    if name in TEAM_NAME_TO_CODE:
        return TEAM_NAME_TO_CODE[name]
    return "".join(c for c in name.upper() if c.isalpha())[:3]

# ------------------------------
# Stat Types
# ------------------------------
STAT_TYPE_TO_POSITIONS = {
    "Passing": {"QB"},
    "Rushing": {"QB", "RB", "FB"},
    "Receiving": {"RB", "FB", "WR", "TE"},
    "Defense": {
        "CB", "DB", "DE", "DL", "DT", "FS",
        "ILB", "LB", "MLB", "NT", "OLB",
        "S", "SS"
    },
    "Kicking": {"K"},
}

# ------------------------------
# Schedule helper (unchanged)
# ------------------------------
def load_nfl_games_next_3_days(path="nflschedule.json", today_dt: date = None):
    if today_dt is None:
        today_dt = datetime.now().date()

    if not os.path.exists(path):
        return set(), {}, []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return set(), {}, []

    game_dates = data.get("leagueSchedule", {}).get("gameDates", [])
    if not game_dates:
        return set(), {}, []

    wanted_dates = {
        (today_dt + pd.Timedelta(days=i)).strftime("%m/%d/%Y 00:00:00")
        for i in range(3)
    }

    teams = set()
    opp_map = {}
    valid_dates = []

    for gd in game_dates:
        key = str(gd.get("gameDate", ""))
        if key not in wanted_dates:
            continue

        valid_dates.append(key)

        for g in gd.get("games", []):
            home = safe_upper(g.get("homeTeam", {}).get("teamTricode", ""))
            away = safe_upper(g.get("awayTeam", {}).get("teamTricode", ""))

            if home and away:
                teams.add(home)
                teams.add(away)
                opp_map[home] = away
                opp_map[away] = home

    return teams, opp_map, valid_dates

#----------------------------
# Opponent Defensive Rankings
#----------------------------
#def compute_nfl_defensive_rankings(df):
#    """
#    Compute opponent defensive rankings from NFL game-level data.
#
#    Required columns:
#      - Opp (defensive team)
#      - PTS (points scored by offense)
#      - RushYds
#      - PassYds
#    """
#
#    required = {"Opp", "PTS", "RushYds", "PassYds"}
#    missing = required - set(df.columns)
#    if missing:
#        st.warning(f"Cannot compute NFL defensive rankings — missing columns: {missing}")
#        return pd.DataFrame()
#
#    df = df.copy()
#
#    # Aggregate offensive output against each defensive team
#    team_def = (
#        df.groupby("Opp")
#          .agg(
#              Pa=("PTS", "mean"),
#              RuYdsa=("RushYds", "mean"),
#              PaYdsa=("PassYds", "mean"),
#          )
#    )
#
#    # Rankings (lower allowed = tougher defense)
#    team_def["Pa_R"] = team_def["Pa"].rank(method="min")
#    team_def["RuYdsa_R"] = team_def["RuYdsa"].rank(method="min")
#    team_def["PaYdsa_R"] = team_def["PaYdsa"].rank(method="min")
#
#    return team_def.round(1)

# ------------------------------
# NFL hit-rate calculator (FIXED)
# ------------------------------
def calc_nfl_pfr_hit_rates(
    df: pd.DataFrame,
    stat_cols: dict,   # {"Rec": "REC", "RecYds": "REY"}
    percentages=(50, 75, 80),
    recent_n=None,     # None = ALL
    restrict_to_teams=None,
    opp_map=None
):
    df = df.copy()

    # Normalize
    df["Team"] = df["Team"].astype(str)
    df["Pos"] = df["Pos"].astype(str)
    df["Opp"] = df["Opp"].astype(str)

    results = []

    for player, g in df.groupby("Name", sort=False):
        g = g.sort_values("Week")

        team = safe_upper(g.iloc[-1]["Team"])
        if restrict_to_teams and team not in restrict_to_teams:
            continue

        pos = g.iloc[-1]["Pos"]

        opp = opp_map.get(team, g.iloc[-1]["Opp"]) if opp_map else g.iloc[-1]["Opp"]
        opp = safe_upper(opp)

        row = {
            "Player": player,
            "Pos": pos,
            "Team": team,
            "Gms": len(g),
            "Opp": opp,
        }

        # ----------------------------------
        # Opponent defensive rankings
        # ----------------------------------
#        if "nfl_def" in globals() and opp in nfl_def.index:
#            row["Pa"] = nfl_def.loc[opp, "Pa"]
#            row["Pa_R"] = int(nfl_def.loc[opp, "Pa_R"])
#            row["RuYdsa"] = nfl_def.loc[opp, "RuYdsa"]
#            row["RuYdsa_R"] = int(nfl_def.loc[opp, "RuYdsa_R"])
#            row["PaYdsa"] = nfl_def.loc[opp, "PaYdsa"]
#            row["PaYdsa_R"] = int(nfl_def.loc[opp, "PaYdsa_R"])
#        else:
#            row["Pa"] = row["Pa_R"] = None
#            row["RuYdsa"] = row["RuYdsa_R"] = None
#            row["PaYdsa"] = row["PaYdsa_R"] = None

        # ----------------------------------
        # Hit-rate calculations
        # ----------------------------------
        recent = g if recent_n is None else g.tail(recent_n)

        for col, abbr in stat_cols.items():
            if col not in g.columns:
                continue

            vals_all = pd.to_numeric(g[col], errors="coerce").dropna().tolist()
            vals_recent = pd.to_numeric(recent[col], errors="coerce").dropna().tolist()

            for pct in percentages:
                row[f"{abbr}@{pct}"] = hit_rate_threshold(vals_all, pct)

                if recent_n is not None:
                    row[f"L{recent_n}{abbr}@{pct}"] = hit_rate_threshold(vals_recent, pct)

        results.append(row)

    return pd.DataFrame(results)



