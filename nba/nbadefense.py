# data/nba_defense.py

import pandas as pd

def ensure_opp_column(df):
    """
    Returns a tuple: (df, column_name) where column_name can be used as the opponent team.
    - Uses 'OPP_TEAM' if present
    - Uses 'Opp' if present
    - Uses 'MATCHUP' to derive OPP_TEAM if present
    Raises ValueError if none found.
    """
    if "OPP_TEAM" in df.columns:
        return df, "OPP_TEAM"
    elif "Opp" in df.columns:
        return df, "Opp"
    elif "MATCHUP" in df.columns:
        df = add_opp_from_matchup(df)
        return df, "OPP_TEAM"
    else:
        raise ValueError("No column found to represent opponent team")

def add_opp_from_matchup(df):
    """
    Adds 'OPP_TEAM' column from 'MATCHUP' if it exists.
    Compatible with ensure_opp_column:
      - If 'OPP_TEAM' already exists, does nothing.
      - If 'MATCHUP' exists, extracts opponent team.
      - Otherwise, creates 'OPP_TEAM' with None values.
    """
    if "OPP_TEAM" in df.columns:
        return df

    if "MATCHUP" in df.columns:
        df["OPP_TEAM"] = (
            df["MATCHUP"]
            .astype(str)
            .str.extract(r"(?:@|vs\.)\s*([A-Z]{3})", expand=False)
        )
    else:
        # Safe fallback: create empty column
        df["OPP_TEAM"] = None

    return df

STATS = [
    "PTS", "REB", "AST", "PRA",
    "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A",
    "FTM", "FTA", "OREB", "DREB"
]

def get_team_def_ranks(team_totals_df=None, window="ALL"):
    """
    Compute defensive rankings based on opponent-allowed stats from team totals.
    Expects team_totals_df with 'OPP_TEAM' or 'MATCHUP'.
    """
    if team_totals_df is None:
        df = pd.read_csv("nba/data/nbateamgametotals.csv")
    else:
        df = team_totals_df.copy()

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

    # Ensure we have an opponent column
    df, opp_col = ensure_opp_column(df)

    # Combo stat
    if {"PTS","REB","AST"}.issubset(df.columns):
        df["PRA"] = df["PTS"] + df["REB"] + df["AST"]

    # Apply window (e.g., "L5")
    if window != "ALL":
        n_games = int(window[1:])
        df = df.sort_values("GAME_DATE").groupby(opp_col, group_keys=False).tail(n_games)

    rows = []
    for stat in STATS:
        stat_df = df.groupby(opp_col)[stat].mean().reset_index(name="AVG_ALLOWED")
        stat_df["STAT"] = stat
        stat_df["RANK"] = stat_df["AVG_ALLOWED"].rank(method="min", ascending=True).astype(int)
        rows.append(stat_df)

    return pd.concat(rows, ignore_index=True)

def get_team_def_ranks_by_position(player_logs_df, window="ALL"):
    """
    Compute defensive averages and ranks by opponent + position bucket.
    Expects player_logs_df with 'Opp' column.
    """
    df = player_logs_df.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

    # Ensure we have an opponent column
    df, opp_col = ensure_opp_column(df)

    # Required columns
    required = {opp_col, "PosBucket"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Combo stat
    if {"PTS","REB","AST"}.issubset(df.columns):
        df["PRA"] = df["PTS"] + df["REB"] + df["AST"]

    # Apply window per opponent + position
    if window != "ALL":
        n_games = int(window[1:])
        df = df.sort_values("GAME_DATE").groupby([opp_col, "PosBucket"], group_keys=False).tail(n_games)

    rows = []

    for stat in STATS:
        stat_df = df.groupby([opp_col, "PosBucket"])[stat].mean().reset_index(name="AVG_ALLOWED")
        stat_df["STAT"] = stat
        # Rank within position bucket
        stat_df["RANK"] = stat_df.groupby("PosBucket")["AVG_ALLOWED"].rank(method="min", ascending=True).astype(int)
        rows.append(stat_df)

    return pd.concat(rows, ignore_index=True)
