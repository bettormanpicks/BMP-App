# tennis/helpers.py

import pandas as pd
import streamlit as st
from shared.utils import hit_rate_threshold, trim_df_to_recent_82

# --- Surface / positional mapping ---
SURFACE_BUCKET_MAP = {
    "Hard": ("Hard", "H"),
    "Clay": ("Clay", "C"),
    "Grass": ("Grass", "G"),
    "Carpet": ("Carpet", "P"),
}

# --- Stat map for hit rate calculations ---
TENNIS_STAT_MAP = {
    "GW": "games_won",
    "GL": "games_lost",
    "GD": "game_diff",
    "TG": "total_games",
    "MW": "match_win"
}



@st.cache_data(ttl=3600)
def load_tennis_raw_data(tour="WTA"):
    """
    Load tennis gamelogs (WTA or ATP) and prepare a 'raw-data' dataframe
    compatible with the NBA pipeline in app.py.
    
    Parameters
    ----------
    tour : str
        "WTA" or "ATP". Determines which gamelog CSV to load.
    """
    gamelog_path = f"{tour.lower()}_player_gamelogs.csv"
    players_path = "tennisplayers.csv"

    # --- Load gamelogs ---
    df = pd.read_csv(gamelog_path, dtype=str)

    # Ensure numeric stats
    numeric_cols = ["games_won", "games_lost", "game_diff", "total_games", "match_win"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- Load players for display names ---
    players = pd.read_csv(players_path, dtype=str)
    players_lookup = dict(zip(players["player_id"], players["player_name"]))

    df["Player"] = df["player_id"].map(players_lookup).fillna(df["player_id"])
    df["Opp"] = df["opponent"].map(players_lookup).fillna(df["opponent"])

    # --- Positional / surface mapping ---
    df["PosBucket"] = df["surface"].map(lambda s: SURFACE_BUCKET_MAP.get(s, (None, None))[0])
    df["Pos"] = df["surface"].map(lambda s: SURFACE_BUCKET_MAP.get(s, (None, None))[1])

    # --- GAME_DATE for chronology ---
    df["GAME_DATE"] = pd.to_datetime(df["game_date"], errors="coerce")

    # --- Add combo-style stats for hit rate / betting props ---
    df["GW"] = df["games_won"]
    df["GL"] = df["games_lost"]
    df["TG"] = df["total_games"]
    df["GD"] = df["game_diff"]
    df["MW"] = df["match_win"]

    # --- Team placeholder for consistency with NBA pipeline ---
    df["Team"] = tour.upper()

    # --- Filter out rows without dates or surfaces ---
    df = df[df["GAME_DATE"].notna() & df["PosBucket"].notna()]

    return df

def compute_tennis_percentiles(df: pd.DataFrame, stats_selected: list, percentages: list, recent_n=None):
    """
    Compute hit rate thresholds for tennis players, filtered by the surface of their next match.
    Only past games on the same surface are considered for percentiles.

    Parameters
    ----------
    df : pd.DataFrame
        Raw tennis gamelogs, must have 'player_id', 'GAME_DATE', and 'PosBucket' (surface)
    stats_selected : list
        List of stats to compute, e.g. ["GW","GL","GD","TG","MW"]
    percentages : list
        List of hit rate percentages, e.g. [80] for 80%
    recent_n : int | None
        Number of most recent games to consider. None = all games on same surface.

    Returns
    -------
    pd.DataFrame
        Player-level summary with thresholds per stat
    """

    df = df.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    results = []

    for pid, group in df.groupby("player_id", sort=False):
        group = group.sort_values("GAME_DATE", ascending=False)
        if group.empty:
            continue

        # Identify next match surface
        next_surface = group["PosBucket"].iloc[0]
        surface_group = group[group["PosBucket"] == next_surface]

        if surface_group.empty:
            continue

        row = {
            "player_id": pid,
            "Player": surface_group["Player"].iloc[0],
            "Opp": surface_group["Opp"].iloc[0],
            "Surface": next_surface,
            "Gms": len(surface_group),
        }

        for stat in stats_selected:
            col = TENNIS_STAT_MAP.get(stat)
            if col not in surface_group.columns:
                row[stat] = None
                continue

            vals_all = pd.to_numeric(surface_group[col], errors="coerce").dropna()
            if vals_all.empty:
                row[stat] = None
                continue

            vals_recent = (
                pd.to_numeric(surface_group.head(recent_n)[col], errors="coerce").dropna()
                if recent_n else None
            )

            for pct in percentages:
                row[f"{stat}@{pct}"] = hit_rate_threshold(vals_all, pct)

                if recent_n and vals_recent is not None:
                    row[f"L{recent_n}{stat}@{pct}"] = hit_rate_threshold(vals_recent, pct)

        results.append(row)

    return pd.DataFrame(results)
