#nba/helpers.py


import pandas as pd
from datetime import timedelta
import json
import streamlit as st
from shared.utils import hit_rate_threshold, get_nba_today  # if needed
from nba.nbadefense import get_team_def_ranks, get_team_def_ranks_by_position

DEF_STAT_MAP = {
    "PTS": ("PaA", "PaR"),
    "REB": ("RaA", "RaR"),
    "AST": ("AaA", "AaR"),
    "PRA": ("PRAaA", "PRAaR"),
    "FG3M": ("3PMaA", "3PMaR"),
    "FG3A": ("3PAaA", "3PAaR"),
    "STL": ("SaA", "SaR"),
    "BLK": ("BaA", "BaR"),
    "TOV": ("TOaA", "TOaR"),
    "FGM": ("FGMaA", "FGMaR"),
    "FGA": ("FGAaA", "FGAaR"),
    "FTM": ("FTMaA", "FTMaR"),
    "FTA": ("FTAaA", "FTAaR"),
    "OREB": ("ORaA", "ORaR"),
    "DREB": ("DRaA", "DRaR"),
}

@st.cache_data(ttl=3600)
def load_nba_schedule(path="nba/data/nbaschedule.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data(ttl=3600)
def load_today_matchups(path="nba/data/nbaschedule.json"):
    from nba.helpers_schedule import load_todays_schedule  # if you keep that helper separate
    return load_todays_schedule(path)

@st.cache_data(ttl=300)
def load_nba_injury_status():
    try:
        df = pd.read_csv("nba/data/nbaplayerstatus.csv", dtype={"player_id": str})
        return dict(zip(df["player_id"], df["Status_norm"]))
    except Exception:
        return {}

def parse_nba_matchup(matchup):
    """
    Extract team and opponent from the MATCHUP column, e.g. "LAL @ BOS"
    Returns: (team, opponent) in uppercase
    """
    if pd.isna(matchup):
        return None, None
    parts = str(matchup).split()
    if len(parts) < 3:
        return None, None
    team = parts[0].strip().upper()
    opp = parts[2].strip().upper()
    return team, opp

def add_team_opponent_columns(df):
    """
    Extract Team and Opp from MATCHUP.
    MATCHUP format:
      'LAL @ DEN'  -> Team=LAL, Opp=DEN
      'DEN vs LAL' -> Team=DEN, Opp=LAL
    """

    if "MATCHUP" not in df.columns:
        raise ValueError("MATCHUP column not found")

    matchup = df["MATCHUP"].astype(str)

    df["Team"] = matchup.str.slice(0, 3)

    df["Opp"] = matchup.str.extract(
        r"(?:@|vs.)\s+([A-Z]{3})",
        expand=False
    )

    return df

def compute_player_percentiles(
    df,
    stats,
    percentages,
    recent_n,
    opponent_def,
    today_matchups,
    show_positional_def=False,
    pos_def_df=None,
):
    df = df.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    results = []

    for pid, group in df.groupby("player_id", sort=False):

        group = group.sort_values("GAME_DATE", ascending=False).head(82)
        if group.empty:
            continue

        player_name = group["player_name"].iloc[0]
        team = group["Team"].iloc[0]
        pos_bucket = group["PosBucket"].iloc[0]
        pos_display = group["Pos"].iloc[0]

        row = {
            "player_id": pid,
            "Player": player_name,
            "Team": team,
            "Pos": pos_display,
            "Gms": len(group),
        }

        # ===== TODAY'S OPPONENT =====
        opp = today_matchups.get(team)
        row["Opp"] = opp

        # ===== DEFENSIVE MATCHUPS =====
        if opp and opponent_def is not None and opp in opponent_def.index:

            for stat in stats:
                if stat not in DEF_STAT_MAP:
                    continue

                avg_col, rank_col = DEF_STAT_MAP[stat]

                avg_val = opponent_def.loc[opp, avg_col]
                rank_val = opponent_def.loc[opp, rank_col]

                if (
                    show_positional_def
                    and pos_def_df is not None
                ):
                    pos_row = pos_def_df[
                        (pos_def_df["Opp"] == opp)
                        & (pos_def_df["PosBucket"] == pos_bucket)
                        & (pos_def_df["STAT"] == stat)
                    ]

                    if not pos_row.empty:
                        avg_val = pos_row["AVG_ALLOWED"].iloc[0]
                        rank_val = pos_row["RANK"].iloc[0]

                row[avg_col] = round(avg_val, 1)
                row[rank_col] = int(rank_val)

        # ===== PLAYER HIT RATE PERCENTILES =====
        for stat in stats:

            vals_all = pd.to_numeric(group[stat], errors="coerce").dropna()

            if vals_all.empty:
                continue

            vals_recent = (
                pd.to_numeric(group.head(recent_n)[stat], errors="coerce").dropna()
                if recent_n
                else None
            )

            for pct in percentages:
                row[f"{stat}@{int(pct)}"] = hit_rate_threshold(vals_all, pct)

                if recent_n and vals_recent is not None:
                    row[f"L{recent_n}{stat}@{int(pct)}"] = hit_rate_threshold(
                        vals_recent, pct
                    )

        results.append(row)

    return pd.DataFrame(results)

def load_todays_schedule(schedule_path="nba/data/nbaschedule.json"):
    try:
        with open(schedule_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.warning(f"Could not load {schedule_path}: {e}")
        return set(), {}

    nba_today = get_nba_today()
    today_str = nba_today.strftime("%Y-%m-%d")

    todays_teams = set()
    today_matchups = {}

    # ---- Simple format ----
    if "games" in data:
        for g in data["games"]:
            game_date = g.get("date") or g.get("gameDate")
            if not game_date:
                continue

            try:
                parsed = pd.to_datetime(game_date).strftime("%Y-%m-%d")
            except:
                continue

            if parsed != today_str:
                continue

            home = g.get("home", "").upper()
            away = g.get("away", "").upper()

            if home and away:
                todays_teams.add(home)
                todays_teams.add(away)
                today_matchups[home] = away
                today_matchups[away] = home

        return todays_teams, today_matchups

    # ---- NBA API format ----
    try:
        for day in data["leagueSchedule"]["gameDates"]:
            raw = day.get("gameDate", "")
            try:
                parsed = pd.to_datetime(raw)
                date_str = parsed.strftime("%Y-%m-%d")
            except:
                continue

            if date_str != today_str:
                continue

            # Extract today's games
            for g in day.get("games", []):
                home = g["homeTeam"]["teamTricode"].upper()
                away = g["awayTeam"]["teamTricode"].upper()
                todays_teams.add(home)
                todays_teams.add(away)
                today_matchups[home] = away
                today_matchups[away] = home
    except:
        pass

    return todays_teams, today_matchups

def compute_team_b2b_from_schedule(schedule_data):
    today = get_nba_today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    today_teams = get_teams_playing_on_date(schedule_data, today)
    yesterday_teams = get_teams_playing_on_date(schedule_data, yesterday)
    tomorrow_teams = get_teams_playing_on_date(schedule_data, tomorrow)

    b2b = {}

    for team in today_teams:
        if team in yesterday_teams:
            b2b[team] = "2"
        elif team in tomorrow_teams:
            b2b[team] = "1"
        else:
            b2b[team] = "N"

    return b2b

NBA_POSITION_MAP = {
    "Guard": ("G", "G"),
    "Forward": ("F", "F"),
    "Center": ("C", "C"),
    "Guard-Forward": ("Wing", "G/F"),
    "Forward-Guard": ("Wing", "F/G"),
    "Center-Forward": ("Big", "C/F"),
    "Forward-Center": ("Big", "F/C"),
}

def normalize_nba_position(pos):
    if not isinstance(pos, str):
        return None
    return NBA_POSITION_MAP.get(pos.strip(), (None, None))[0]

def normalize_nba_position_display(pos):
    if not isinstance(pos, str):
        return None
    return NBA_POSITION_MAP.get(pos.strip(), (None, pos))[1]

def add_combo_stats(df):
    """
    Derive combination stats (shared by NBA standalone)
    """
    df = df.copy()

    def get(col):
        return next((c for c in df.columns if c.lower() == col.lower()), None)

    pts = get("pts")
    reb = get("reb")
    ast = get("ast")

    if pts and reb and ast:
        df["PRA"] = df[pts] + df[reb] + df[ast]
    if pts and reb:
        df["PR"] = df[pts] + df[reb]
    if pts and ast:
        df["PA"] = df[pts] + df[ast]
    if reb and ast:
        df["RA"] = df[reb] + df[ast]

    return df

@st.cache_data(ttl=3600)
def load_nba_raw_data():
    # --- Load raw CSVs ---
    player_logs_df = pd.read_csv("nba/data/nbaplayergamelogs.csv")
    team_totals_df = pd.read_csv("nba/data/nbateamgametotals.csv")
    pos_df = pd.read_csv("nba/data/nbaplayerspositions.csv")

    # --- Normalize IDs on RAW dataframes ---
    player_logs_df["player_id"] = player_logs_df.get(
        "player_id", player_logs_df.get("Player_ID")
    ).astype(str)

    player_logs_df["season"] = player_logs_df.get(
        "season", player_logs_df.get("Season", player_logs_df.get("SEASON_ID"))
    ).astype(str)

    player_logs_df["season"] = player_logs_df["season"].replace({
        "22025": "2025-26",
        "22024": "2024-25",
    })

    pos_df["player_id"] = pos_df["player_id"].astype(str)

    # --- Merge player positions ---
    df = player_logs_df.merge(
        pos_df[["player_id", "Position"]],
        on="player_id",
        how="left"
    )

    # --- Add position buckets & display ---
    df["PosBucket"] = df["Position"].apply(normalize_nba_position)
    df = df[df["PosBucket"].notna()]
    df["Pos"] = df["Position"].apply(normalize_nba_position_display)

    # --- Add matchup columns ---
    df = add_team_opponent_columns(df)
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    # --- Add combo stats ---
    df = add_combo_stats(df)

    return df, team_totals_df, pos_df

@st.cache_data(ttl=3600)
def load_defense_tables(window):
    # Load raw data
    player_logs_df, team_totals_df, pos_df = load_nba_raw_data()

    # --- Defensive stats REQUIRE Opp column ---
    if "Opp" not in player_logs_df.columns:
        player_logs_df = add_team_opponent_columns(player_logs_df)

    # --- Drop rows where position is unknown ---
    player_logs_df = player_logs_df[player_logs_df["PosBucket"].notna()]

    # --- Compute defense tables ---
    overall_def = get_team_def_ranks(team_totals_df, window)  # <--- pass team_totals_df
    positional_def = get_team_def_ranks_by_position(player_logs_df, window)

    return overall_def, positional_def
