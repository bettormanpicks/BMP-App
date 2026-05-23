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

@st.cache_data
def load_tennis_players():
    """Static lookup table — cached with no TTL (never changes mid-session)."""
    players_path = os.path.join(DATA_DIR, "tennisplayers.csv")
    return pd.read_csv(players_path, dtype=str)

@st.cache_data(ttl=3600)
def load_tennis_schedule():
    """TTL raised from 300s to 3600s — schedule is updated manually via bat file,
    not mid-session, so a 5-min TTL was causing unnecessary disk reads."""
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

    # --- Load gamelogs ---
    df = pd.read_csv(gamelog_path, dtype=str)

    # Ensure numeric stats
    numeric_cols = ["games_won", "games_lost", "game_diff", "total_games", "match_win"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- Load players for display names (reuse the cached loader) ---
    players = load_tennis_players()
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
    """
    Compute tennis percentiles for players.

    Performance notes vs original:
    - Surface pre-filtering and player-ID filtering now happen BEFORE groupby so
      we only copy and iterate the rows we actually need.
    - df.copy() is deferred until after filtering so the copied object is as
      small as possible.
    - The per-player surface filter inside the loop is eliminated for historical
      mode when a specific surface is selected.
    """

    # Normalize surface_filter: treat None/''/'All' as no filter
    def _no_surface_filter(val):
        if val is None:
            return True
        if isinstance(val, str) and val.strip().lower() in {"", "all"}:
            return True
        return False

    # --- Resolve the date column name once (tolerant to CSV casing) ---
    date_col = next((c for c in df.columns if c.lower() == "game_date"), None)

    # --- PRE-FILTER: keep only players who appear in today's schedule ---
    if upcoming_only:
        if schedule_df is None:
            raise ValueError("schedule_df is required when upcoming_only=True")
        scheduled_ids = set(schedule_df["player_id"]).union(set(schedule_df["opponent_id"]))
        df = df[df["player_id"].isin(scheduled_ids)]

    # --- PRE-FILTER: surface (historical mode only, when a specific surface is chosen) ---
    if not upcoming_only and not _no_surface_filter(surface_filter):
        surface_col = "PosBucket" if "PosBucket" in df.columns else ("surface" if "surface" in df.columns else None)
        if surface_col:
            df = df[df[surface_col].astype(str).str.strip().str.casefold() == str(surface_filter).strip().casefold()]

    # --- Copy only the filtered subset (much cheaper than copying the full DF) ---
    df = df.copy()

    if date_col is not None:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    results = []

    for pid, group in df.groupby("player_id", sort=False):
        if date_col is not None:
            group = group.sort_values(date_col, ascending=False)
        if group.empty:
            continue

        # --- Determine surface & opponent ---
        if upcoming_only:
            match = schedule_df[(schedule_df["player_id"] == pid) |
                                (schedule_df["opponent_id"] == pid)]
            if match.empty:
                continue

            match = match.iloc[0]
            opponent_id = match["opponent_id"] if match["player_id"] == pid else match["player_id"]
            next_surface = normalize_surface(match["Surface"])

            # Filter this player's rows to the upcoming surface
            surface_col = "PosBucket" if "PosBucket" in group.columns else ("surface" if "surface" in group.columns else None)
            if surface_col:
                surface_group = group[group[surface_col].astype(str).str.strip().str.casefold() == str(next_surface).strip().casefold()]
            else:
                surface_group = group

            if surface_group.empty:
                continue
        else:
            # Historical mode — surface already pre-filtered above for specific surfaces
            opponent_id = None
            next_surface = None
            surface_group = group
            display_surface = "All" if _no_surface_filter(surface_filter) else surface_filter

        row = {
            "player_id": pid,
            "Player": group["Player"].iloc[0] if "Player" in group.columns else pid,
            "Surface": next_surface if upcoming_only else display_surface,
            "Gms": len(surface_group),
        }
        if upcoming_only:
            row["opponent_id"] = opponent_id

        # --- Compute stats ---
        for stat in stats_selected:
            col = TENNIS_STAT_MAP.get(stat)
            if col not in surface_group.columns:
                continue

            vals_all = pd.to_numeric(surface_group[col], errors="coerce").dropna()
            if vals_all.empty:
                continue

            vals_recent = (
                pd.to_numeric(surface_group.head(recent_n)[col], errors="coerce").dropna()
                if recent_n else None
            )

            #   Special handling for Match Wins
            if stat == "MW":
                # Season / Surface MW%
                row["MW%"] = round(vals_all.mean() * 100, 1)

                # Recent window MW%
                if recent_n and vals_recent is not None and not vals_recent.empty:
                    row[f"L{recent_n}MW%"] = round(vals_recent.mean() * 100, 1)

                continue  # skip hit rate logic for MW

            #   All other stats use hit rate logic
            for pct in percentages:
                row[f"{stat}@{pct}"] = hit_rate_threshold(vals_all, pct)
                if recent_n and vals_recent is not None:
                    row[f"L{recent_n}{stat}@{pct}"] = hit_rate_threshold(vals_recent, pct)

        results.append(row)

    return pd.DataFrame(results)