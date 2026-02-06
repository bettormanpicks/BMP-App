# data/nba_defense.py

import pandas as pd

def add_opp_from_matchup(df):
    """
    Derive OPP_TEAM from MATCHUP for team totals.
    """
    if "OPP_TEAM" in df.columns:
        return df

    if "MATCHUP" not in df.columns:
        raise ValueError("MATCHUP column not found for opponent derivation")

    df["OPP_TEAM"] = (
        df["MATCHUP"]
        .astype(str)
        .str.extract(r"(?:@|vs\.)\s+([A-Z]{3})", expand=False)
    )

    return df

STATS = [
    "PTS", "REB", "AST", "PRA",
    "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A",
    "FTM", "FTA", "OREB", "DREB"
]

def get_team_def_ranks(team_totals_df=None, window="ALL"):
    """
    Compute defensive rankings based on opponent-allowed stats.
    """
    if team_totals_df is None:
        df = pd.read_csv("nba/data/nbateamgametotals.csv")
    else:
        df = team_totals_df.copy()

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = add_opp_from_matchup(df)
    
    if {"PTS","REB","AST"}.issubset(df.columns):
        df["PRA"] = df["PTS"] + df["REB"] + df["AST"]

    if window != "ALL":
        n_games = int(window[1:])
        df = df.sort_values("GAME_DATE").groupby("OPP_TEAM", group_keys=False).tail(n_games)

    rows = []
    for stat in STATS:
        stat_df = df.groupby("OPP_TEAM")[stat].mean().reset_index(name="AVG_ALLOWED")
        stat_df["STAT"] = stat
        stat_df["RANK"] = stat_df["AVG_ALLOWED"].rank(method="min", ascending=True).astype(int)
        rows.append(stat_df)

    return pd.concat(rows, ignore_index=True)

def get_team_def_ranks_by_position(player_logs_df, window="ALL"):
    """
    Compute opponent defensive averages and ranks
    broken out by player position bucket.
    """

    # Work ONLY from player logs
    df = player_logs_df.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

    # Sanity checks (important)
    required = {"Opp", "PosBucket"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # PRA
    if {"PTS", "REB", "AST"}.issubset(df.columns):
        df["PRA"] = df["PTS"] + df["REB"] + df["AST"]

    # Apply window per opponent + position
    if window != "ALL":
        n_games = int(window[1:])
        df = (
            df.sort_values("GAME_DATE")
              .groupby(["Opp", "PosBucket"], group_keys=False)
              .tail(n_games)
        )

    rows = []

    for stat in STATS:
        stat_df = (
            df
            .groupby(["Opp", "PosBucket"])[stat]
            .mean()
            .reset_index(name="AVG_ALLOWED")
        )

        stat_df["STAT"] = stat

        # Rank WITHIN position bucket
        stat_df["RANK"] = (
            stat_df
            .groupby("PosBucket")["AVG_ALLOWED"]
            .rank(method="min", ascending=True)
            .astype(int)
        )

        rows.append(stat_df)

    return pd.concat(rows, ignore_index=True)
