# tennis/tennishelpers.py

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from shared.utils import hit_rate_threshold

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --- Surface / positional mapping ---
SURFACE_BUCKET_MAP = {
    "Hard": ("Hard", "H"),
    "Clay": ("Clay", "C"),
    "Grass": ("Grass", "G"),
}

# --- Stat map for hit rate calculations ---
TENNIS_STAT_MAP = {
    "GW": "games_won",
    "GL": "games_lost",
    "GD": "game_diff",
    "TG": "total_games",
    "MW": "match_win"
}

DEFENSE_FILE = os.path.join(DATA_DIR, "tennis_opponent_defense_normalized.csv")

@st.cache_data
def load_tennis_defense():
    return pd.read_csv(DEFENSE_FILE)

def get_opponent_return_tier(opponent_id, surface):
    df = load_tennis_defense()
    row = df[(df["player_id"] == opponent_id) & (df["surface"] == surface)]

    if row.empty:
        return "Unknown"

    return row.iloc[0]["return_tier"]

def load_tennis_players():
    players_path = os.path.join(DATA_DIR, "tennisplayers.csv")
    return pd.read_csv(players_path, dtype=str)

@st.cache_data(ttl=300)
def load_tennis_schedule():
    schedule_path = os.path.join(DATA_DIR, "tennis_schedule_resolved.csv")
    df = pd.read_csv(schedule_path, dtype=str)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    return df

@st.cache_data(ttl=3600)
def load_tennis_raw_data(tour="ATP"):
    """
    Load tennis gamelogs (ATP or WTA) and prepare a 'raw-data' dataframe
    compatible with the NBA pipeline in app.py.
    
    Parameters
    ----------
    tour : str
        "ATP" or "WTA". Determines which gamelog CSV to load.
    """
    gamelog_path = os.path.join(DATA_DIR, f"{tour.lower()}_player_gamelogs.csv")
    players_path = os.path.join(DATA_DIR, "tennisplayers.csv")

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

def normalize_surface(s):
    if pd.isna(s):
        return None
    s = str(s).strip().lower()
    if "hard" in s:
        return "Hard"
    if "clay" in s:
        return "Clay"
    if "grass" in s:
        return "Grass"
    return None

def compute_tennis_percentiles(df: pd.DataFrame, stats_selected: list, percentages: list,
                               recent_n=None, upcoming_only=True, schedule_df=None, surface_filter=None):

    #st.write("Incoming DF rows:", len(df))
    #st.write("Unique players in DF:", df["player_id"].nunique())

    """
    Compute tennis percentiles for players.
    """
    df = df.copy()

    # Be tolerant to column casing from CSVs (e.g., 'game_date' vs 'GAME_DATE')
    date_col = None
    for c in df.columns:
        if c.lower() == "game_date":
            date_col = c
            break
    if date_col is not None:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        # fallback – do nothing if not present
        pass

    # Normalize surface_filter: treat None/''/'All' as no filter
    def _no_surface_filter(val):
        if val is None:
            return True
        if isinstance(val, str) and val.strip().lower() in {"", "all"}:
            return True
        return False

    results = []

    for pid, group in df.groupby("player_id", sort=False):
        if date_col is not None:
            group = group.sort_values(date_col, ascending=False)
        if group.empty:
            continue

        # --- Determine surface & opponent ---
        if upcoming_only:
            if schedule_df is None:
                raise ValueError("schedule_df is required when upcoming_only=True")

            match = schedule_df[(schedule_df["player_id"] == pid) |
                                (schedule_df["opponent_id"] == pid)]
            if match.empty:
                continue

            match = match.iloc[0]
            opponent_id = match["opponent_id"] if match["player_id"] == pid else match["player_id"]
            next_surface = normalize_surface(match["Surface"])

            # Prefer PosBucket if present, else fall back to 'surface'
            if "PosBucket" in group.columns:
                surface_group = group[group["PosBucket"].astype(str).str.strip().str.casefold() == str(next_surface).strip().casefold()]
            elif "surface" in group.columns:
                surface_group = group[group["surface"].astype(str).str.strip().str.casefold() == str(next_surface).strip().casefold()]
            else:
                surface_group = group

            if surface_group.empty:
                continue
        else:
            # Historical mode
            opponent_id = None
            next_surface = None

            if _no_surface_filter(surface_filter):
                # 'All' -> use every row for the player
                surface_group = group
                display_surface = "All"
            else:
                # Filter by the selected surface (case-insensitive)
                if "PosBucket" in group.columns:
                    surface_group = group[group["PosBucket"].astype(str).str.strip().str.casefold() == str(surface_filter).strip().casefold()]
                elif "surface" in group.columns:
                    surface_group = group[group["surface"].astype(str).str.strip().str.casefold() == str(surface_filter).strip().casefold()]
                else:
                    surface_group = group
                display_surface = surface_filter

        row = {
            "player_id": pid,
            "Player": group["Player"].iloc[0] if "Player" in group.columns else pid,
            "Surface": next_surface if upcoming_only else display_surface,
            "Gms": len(surface_group),
        }
        if upcoming_only:
            row["opponent_id"] = opponent_id

        # --- Compute percentiles ---
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
