import streamlit as st
import base64
import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime, timedelta
import pytz
import re

# ============================================================
# Remaining imports for your app logic
# ============================================================
from shared.utils import (
    get_nba_today, hit_rate_threshold, trim_df_to_recent_82,
    dedupe_columns, strip_display_ids, norm_name,
    get_teams_playing_on_date
)
from nba.helpers import (
    DEF_STAT_MAP, load_nba_schedule, load_today_matchups,
    load_nba_injury_status, parse_nba_matchup,
    add_team_opponent_columns, compute_player_percentiles,
    load_todays_schedule, compute_team_b2b_from_schedule,
    normalize_nba_position, normalize_nba_position_display,
    add_combo_stats, load_nba_raw_data, load_defense_tables
)
from nba.nbadefense import get_team_def_ranks, get_team_def_ranks_by_position

# NHL helper functions
from nhl.helpers import get_nhl_todays_schedule, compute_nhl_b2b, analyze_nhl_players, get_nhl_teams_on_date, get_nhl_injuries
from shared.utils import compute_hit_rates

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Bettor Man Picks Stat Analyzer",
    layout="wide"
)

############################################################
# SPORT SELECTION
############################################################
sport_choice = st.sidebar.selectbox("Select Sport", ["NBA", "NHL"]) #, "NFL", "NHL"])

nba_today = get_nba_today()

# Determine the title and date based on sport
if sport_choice == "NBA":
    hero_title = "NBA — Player Hit Rates"
    hero_date = f"NBA date: {nba_today.strftime('%b %d')} (rolls over at 3:00 AM CT)"
elif sport_choice == "NHL":
    hero_title = "NHL — Player Hit Rates"
    hero_date = f"NHL date: {datetime.now().strftime('%b %d')} (rolls over at 3:00 AM CT)"
else:
    hero_title = f"{sport_choice} — Player Hit Rates"
    hero_date = f"{sport_choice} date: {datetime.now().strftime('%b %d')}"

# ============================================================
# HEADER BANNER (hero header with title + date)
# ============================================================
def set_header_banner(image_path, image_width=1500, image_height=150):
    """
    Sets a full-width hero banner at the top of the page, preserving the entire image.

    image_width / image_height: the actual pixel dimensions of your banner image
    """
    aspect_ratio_pct = (image_height / image_width) * 100  # padding-top % to preserve aspect ratio

    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    st.markdown(f"""
    <style>
    /* ===== REMOVE STREAMLIT FULLSCREEN TOOLBAR (GLOBAL) ===== */

    /* Hide the floating media toolbar entirely */
    div[data-testid="stElementToolbar"] {{
        display: none !important;
    }}

    /* Extra safety — remove the fullscreen button specifically */
    button[aria-label="View fullscreen"] {{
        display: none !important;
    }}

    /* Prevent hover activation area */
    [data-testid="stElementToolbar"] * {{
        display: none !important;
    }}

    /* --- HERO HEADER --- */
    .hero-header {{
        position: relative;
        width: 100%;
        height: 0;
        padding-top: {aspect_ratio_pct:.2f}%;
        background-image: url("data:image/png;base64,{data}");
        background-size: contain;       /* scale image fully inside container */
        background-repeat: no-repeat;
        background-position: center top;
        margin-top: -2rem;
    }}

    /* Overlay text (hero title) */
    .hero-text {{
        position: absolute;
        bottom: 8px;
        left: 12px;
        color: #e6edf3;
        z-index: 2;
    }}

    .hero-title {{
        font-size: 20px;
        font-weight: 700;
        margin: 0;
        line-height: 1.15;
    }}

    .hero-date {{
        font-size: 13px;
        color: #8b949e;
        margin-top: 0px;
        line-height: 1.1;
    }}

    /* Sidebar width */
    section[data-testid="stSidebar"] {{
        width: 280px !important;
    }}

    /* Center items inside sidebar (affects the logo) */
    section[data-testid="stSidebar"] .stImage {{
        text-align: center;
        margin-left: 25px;
        margin-top: -140px;
    }}

    /* Remove empty space below the page */
    .block-container {{
        padding-bottom: 0rem !important;
    }}

    /* Hide Streamlit chrome */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* =========================================================
       STREAMLIT MOBILE FIX — move hero text below banner
       ========================================================= */

    /* When Streamlit content area becomes narrow (mobile/app) */
    @media (max-width: 1000px) {{

        /* Stop overlay behavior */
        .hero-text {{
            position: relative !important;
            bottom: auto !important;
            left: auto !important;
            margin-top: 8px;
            margin-left: 6px;
        }}

        /* Banner becomes just an image */
        .hero-header {{
            padding-top: 10% !important;
        }}

        /* Comfortable readable sizes */
        .hero-title {{
            font-size: 18px !important;
        }}

        .hero-date {{
            font-size: 13px !important;
            margin-bottom: 12px;
        }}
    }}

    /* Add space below banner ONLY on mobile */
    @media (max-width: 1000px) {{

        .hero-header {{
            margin-bottom: 70px !important;
        }}

    }}

    /* Mobile-only instruction banner */
    @media (max-width: 768px) {{
        .mobile-hint {{
            background: #111827;
            color: #e5e7eb;
            padding: 5px 7px;
            border-radius: 4px;
            margin-top: 4px;
            margin-bottom: 7px;
            font-size: 14px;
            text-align: center;
            border: 1px solid #374151;
            animation: pulseHint 1.8s ease-in-out infinite alternate;
        }}

        @keyframes pulseHint {{
            from {{ opacity: 0.65; }}
            to   {{ opacity: 1.0; }}
        }}
    }}

    /* Hide on desktop */
    @media (min-width: 769px) {{
        .mobile-hint {{
            display: none;
        }}
    }}
    </style>

    <div class="hero-header">
        <div class="hero-text">
            <div class="hero-title">{hero_title}</div>
            <div class="hero-date">{hero_date}</div>
        </div>
    </div>

    <div class="mobile-hint">
    ⬅ Tap the arrow in the top-left to open filters
    </div>
    """, unsafe_allow_html=True)

set_header_banner("assets/banner.png", image_width=1500, image_height=150)

nba_today = get_nba_today()

# Sidebar logo
st.sidebar.image("assets/logo.png", width=170)

# Additional CSS tweaks



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

############################################################
# ===== NBA SECTION (Multi-sport compatible) =====
############################################################
if sport_choice == "NBA":

    #st.subheader("NBA — Player Hit Rate Analysis")
    #nba_today = get_nba_today()
    #st.caption(f"NBA date: {nba_today.strftime('%b %d')} (rolls over at 3:00 AM CT)")

    # --- Load core NBA data (cached) ---
    df, team_totals_df, pos_df = load_nba_raw_data()

    # --- Sidebar Filters ---
    with st.sidebar.form("NBA Filters"):

        allowed_stats = [
            "PTS", "REB", "AST", "FGM", "FGA",
            "FG3M", "FG3A", "FTM", "FTA",
            "BLK", "STL", "TOV", "OREB", "DREB",
            "PRA", "PR", "PA", "RA"
        ]
        name_map = {"FG3M": "3PM", "FG3A": "3PA"}
        default_display = ["PTS", "REB", "AST", "PRA", "3PM", "3PA", "STL", "TOV"]

        stats_selected_display = st.multiselect(
            "Choose stats",
            [name_map.get(c, c) for c in allowed_stats],
            default_display
        )
        reverse_lookup = {v: k for k, v in name_map.items()}
        stats_selected = [reverse_lookup.get(d, d) for d in stats_selected_display]

        percentages = [st.slider("Hit Rate Percentage", 40, 100, 80, 5)]

        player_window = st.radio("Player Performance Window", ["L5", "L10", "ALL"], index=0)
        recent_n = 5 if player_window == "L5" else 10 if player_window == "L10" else None

        defense_window = st.radio("Opponent Defensive Window", ["L5", "L10", "ALL"], index=0)

        show_positional_def = st.checkbox("Show Positional Defense", value=False)

        filter_today = st.checkbox("Filter To Today's Teams", value=False)

        #debug_defense_csv = st.checkbox("Export Defensive Rankings", value=False)

        calculate = st.form_submit_button("Calculate")

    # --- Calculate button ---
    if calculate:

        # Trim to most recent 82 games per player
        df_calc = trim_df_to_recent_82(df)

        # --- Cached Defense Tables ---
        overall_def, pos_def_df = load_defense_tables(defense_window)

        # Pivot overall_def to create lookup table by opponent
        opponent_def = pd.DataFrame(index=overall_def["OPP_TEAM"].unique())

        for stat in DEF_STAT_MAP:
            avg_col, rank_col = DEF_STAT_MAP[stat]

            stat_df = overall_def[overall_def["STAT"] == stat].set_index("OPP_TEAM")
            opponent_def[avg_col] = stat_df["AVG_ALLOWED"]
            opponent_def[rank_col] = stat_df["RANK"]

        # Export debug CSVs if requested
        #if debug_defense_csv:
            #opponent_def.to_csv("debug_nba_defense_overall.csv", index=True)
            #pos_def_df.to_csv("debug_nba_defense_positional.csv", index=False)

        # --- Load schedule & compute B2B map ---
        schedule_data = load_nba_schedule()
        todays_teams, today_matchups = load_today_matchups()
        team_b2b_map = compute_team_b2b_from_schedule(schedule_data)

        # Filter players to today's teams if selected
        if filter_today and todays_teams:
            latest_team = (
                df_calc.sort_values(["player_id", "GAME_DATE"], ascending=[True, False])
                       .groupby("player_id")["Team"]
                       .first()
            )
            eligible = latest_team[latest_team.isin(todays_teams)].index
            df_calc = df_calc[df_calc["player_id"].isin(eligible)]

        # --- Compute Hit Rate Percentiles ---
        summary_df = compute_player_percentiles(
            df_calc,
            stats_selected,
            percentages,
            recent_n,
            opponent_def=opponent_def,
            today_matchups=today_matchups,
            show_positional_def=show_positional_def,
            pos_def_df=pos_def_df,
        )

        # --- Rename stat columns for display ---
        stat_abbrev_map = {
            "PTS": "P", "REB": "R", "AST": "A", "OREB": "OR", "DREB": "DR",
            "PRA": "PRA", "PR": "PR", "PA": "PA", "RA": "RA",
            "BLK": "BLK", "STL": "S", "TOV": "TO",
            "FG3M": "3PM", "FG3A": "3PA"
        }

        def rename_stat_columns(col):
            for stat, short in stat_abbrev_map.items():
                if col.startswith(stat):
                    return col.replace(stat, short, 1)
                if col.startswith("L") and stat in col:
                    return col.replace(stat, short, 1)
            return col

        summary_df = summary_df.rename(columns=rename_stat_columns)

        # --- Add B2B and injury status ---
        summary_df["B2B"] = summary_df["Team"].map(team_b2b_map).fillna("N")

        # --- Load NBA injury statuses robustly ---
        try:
            # Load the injuries CSV
            inj_df = pd.read_csv("nba/data/nbaplayerstatus.csv")

            # Convert player_id to int first (to remove any .0) then to str for mapping
            inj_df["player_id"] = inj_df["player_id"].fillna(0).astype(int).astype(str)
            summary_df["player_id"] = summary_df["player_id"].astype(int).astype(str)

            # Create mapping dict
            inj_map = dict(zip(inj_df["player_id"], inj_df["Status_norm"]))

            # Map Status to summary_df
            summary_df["Status"] = summary_df["player_id"].map(inj_map).fillna("A")

        except Exception as e:
            st.warning(f"Unable to load NBA injuries: {e}")
            summary_df["Status"] = "A"

        # --- Column order ---
        base_cols = ["Player", "Pos", "Team", "Opp", "B2B", "Status", "Gms"]
        ordered_stat_cols = []

        for stat in stats_selected:
            display_stat = stat_abbrev_map.get(stat, stat)
            pct_col = f"{display_stat}@{int(percentages[-1])}"
            if pct_col in summary_df.columns:
                ordered_stat_cols.append(pct_col)

            if recent_n:
                recent_col = f"L{recent_n}{display_stat}@{int(percentages[-1])}"
                if recent_col in summary_df.columns:
                    ordered_stat_cols.append(recent_col)

            if stat in DEF_STAT_MAP:
                a_col, r_col = DEF_STAT_MAP[stat]
                if a_col in summary_df.columns:
                    ordered_stat_cols.append(a_col)
                if r_col in summary_df.columns:
                    ordered_stat_cols.append(r_col)

        cols_ordered = [c for c in base_cols + ordered_stat_cols if c in summary_df.columns]
        summary_df = summary_df[cols_ordered]

        # --- Sort & display ---
        sort_col = f"{stat_abbrev_map.get(stats_selected[0], stats_selected[0])}@{int(percentages[-1])}"
        if sort_col in summary_df.columns:
            summary_df = summary_df.sort_values(sort_col, ascending=False)

        col_config = {
            "Player": st.column_config.Column(pinned="left"),
            "Pos": st.column_config.Column(pinned="left"),
            "Team": st.column_config.Column(pinned="left"),
            "Opp": st.column_config.Column(pinned="left"),
        }

        st.dataframe(strip_display_ids(summary_df), width='stretch', hide_index=True, column_config=col_config)

        csv_bytes = strip_display_ids(summary_df).to_csv(index=False).encode()
        #st.download_button("Download CSV", csv_bytes, "player_stats.csv")

############################################################
# ===== NFL SECTION (PFR CLEAN DATA ONLY) =====
############################################################
elif sport_choice == "NFL":

    st.subheader("NFL — Player Hit Rate Analysis")

    # ---------- Upload ----------
    uploaded_nfl = st.file_uploader(
        "Upload NFL Game Logs CSV",
        type=["csv"],
        key="nfl"
    )

    if uploaded_nfl is None:
        st.stop()

    # ---------- Load CSV ----------
    nfl_df = pd.read_csv(uploaded_nfl, low_memory=False)

    nfl_df["Team"] = nfl_df["Team"].apply(normalize_team_code)
    nfl_df["Opp"] = nfl_df["Opp"].apply(normalize_team_code)

    # ---------- Required columns (CANONICAL) ----------
    required_cols = {"Name", "Team", "Opp", "Week"}
    missing = required_cols - set(nfl_df.columns)
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    st.caption(f"Loaded {len(nfl_df):,} game rows")

# ---------- Stat configuration (CANONICAL NFL) ----------
    default_stat_config = {
        # passing
        "PaCmp": "PaCmp",
        "PaAtt": "PaAtt",
        "PaYds": "PaYds",
        "PaTD": "PaTD",

        # rushing
        "RuAtt": "RuAtt",
        "RuYds": "RuYds",
        "RuTD": "RuTD",

        # receiving
        "Rec": "Rec",
        "RecYds": "RecYds",
        "RecTD": "RecTD",

        # defense
        "DefSk": "Sk",
        "TckComb": "Tck",

        # kicking
        "Fgm": "Fgm",
        "Fga": "Fga",
    }

    #------------Stat Types--------------
    STAT_TYPE_TO_STATS = {
        "Passing": {"PaCmp", "PaAtt", "PaYds", "PaTD"},
        "Rushing": {"RuAtt", "RuYds", "RuTD"},
        "Receiving": {"Rec", "RecYds", "RecTD"},
        "Defense": {"DefSk", "TckComb"},
        "Kicking": {"Fgm", "Fga"},
    }

    # Only keep stats that exist in CSV
    stat_config = {
        col: abbr
        for col, abbr in default_stat_config.items()
        if col in nfl_df.columns
    }

    if not stat_config:
        st.error("No known NFL stat columns found in this CSV.")
        st.stop()

    # ---------- Sidebar controls ----------
    stat_type = st.sidebar.radio(
        "Stat Type",
        ["Passing", "Rushing", "Receiving", "Defense", "Kicking"],
        horizontal=True
    )

    allowed_stats = STAT_TYPE_TO_STATS[stat_type]

    stat_config = {
        col: abbr
        for col, abbr in default_stat_config.items()
        if col in nfl_df.columns and col in allowed_stats
    }

    stats_selected = st.sidebar.multiselect(
        "Stats to include",
        list(stat_config.values()),
        default=list(stat_config.values())
    )

    stat_config = {
        col: abbr
        for col, abbr in stat_config.items()
        if abbr in stats_selected
    }

    if not stat_config:
        st.error(f"No {stat_type} stats found in this CSV.")
        st.stop()

    # Percentile thresholds
    pct_input = st.sidebar.text_input("Hit Rate Percentage", "80")
    try:
        percentages = sorted({float(x) for x in pct_input.split()})
    except Exception:
        percentages = [75.0, 80.0, 85.0]

    player_window = st.sidebar.radio("Player Performance Window", ["L5", "L10", "ALL"], index=0)
    recent_n = 5 if player_window == "L5" else 10 if player_window == "L10" else None

    filter_today = st.sidebar.checkbox("Only upcoming games (next 3 days)", value=False)
    schedule_path = st.sidebar.text_input("Local NFL schedule JSON", "nflschedule.json")
    teams_window, opp_map_window, _ = load_nfl_games_next_3_days(schedule_path)

    show_debug = st.sidebar.checkbox("Show recent-game debug table", value=False)

    if not stat_config:
        st.warning("Select at least one stat.")
        st.stop()

    # ---------- Calculate ----------
    if st.sidebar.button("Calculate NFL Hit Rates"):

        if "Pos" not in nfl_df.columns:
            st.error("CSV is missing 'Pos' column required for stat-type filtering.")
            st.stop()

        allowed_positions = STAT_TYPE_TO_POSITIONS[stat_type]
        nfl_df_filtered = nfl_df[nfl_df["Pos"].isin(allowed_positions)]

        restrict_to = set(teams_window) if filter_today else None

#        nfl_def = compute_nfl_defensive_rankings(nfl_df)
#
#        globals()["nfl_def"] = nfl_def

        results = calc_nfl_pfr_hit_rates(
            df=nfl_df_filtered,
            stat_cols=stat_config,
            percentages=percentages,
            recent_n=recent_n,
            restrict_to_teams=restrict_to,
            opp_map=opp_map_window
        )

        if results.empty:
            st.warning("No players matched the current filters.")
            st.stop()

        base_cols = ["Player", "Pos", "Team", "Gms", "Opp"]

#        opp_cols = [
#            "Pa", "Pa_R",
#            "RuYdsa", "RuYdsa_R",
#            "PaYdsa", "PaYdsa_R"
#        ]

        stat_cols = [c for c in results.columns if "@" in c]

        ordered_cols = base_cols + stat_cols
        ordered_cols = [c for c in ordered_cols if c in results.columns]

        results = results[ordered_cols]

        # ---------- Determine primary sort column ----------
        top_pct = int(percentages[-1])
        first_abbr = next(iter(stat_config.values()))
        sort_col = f"{first_abbr}@{top_pct}"

        # ---------- Drop players with no contribution ----------
        if sort_col in results.columns:
            results = results[results[sort_col] > 0]
            results = results.sort_values(sort_col, ascending=False)

        st.subheader("NFL Player Hit-Rate Thresholds")

        st.data_editor(
            results.head(200),
            width='stretch',
            hide_index=True,
            disabled=True,
            column_config={
                "Player": st.column_config.TextColumn(pinned=True),
                "Pos": st.column_config.TextColumn(pinned=True),
                "Team": st.column_config.TextColumn(pinned=True),
            },
        )

        # ✅ MUST be aligned with st.data_editor (same indentation)
        st.download_button(
            "Download NFL Results CSV",
            results.to_csv(index=False).encode("utf-8"),
            "nfl_hit_rates.csv"
        )

        # ---------- Debug recent games ----------
        if show_debug:
            debug_rows = []
            for player, g in nfl_df_filtered.groupby("Name", sort=False):
                if player not in set(results["Player"]):
                    continue
                g = g.sort_values("Week").tail(recent_n)
                for _, r in g.iterrows():
                    row = {
                        "Player": player,
                        "Team": r.get("Team"),
                        "Week": r.get("Week"),
                        "Opp": r.get("Opp"),
                    }
                    for c in stat_config.keys():
                        row[c] = r.get(c)
                    debug_rows.append(row)

            if debug_rows:
                dbg = pd.DataFrame(debug_rows)
                st.subheader("Debug — Games Used in Calculation")
                st.dataframe(dbg, width='stretch')

                st.download_button(
                    "Download Debug CSV",
                    dbg.to_csv(index=False).encode("utf-8"),
                    "nfl_debug_recent_games.csv"
                )

############################################################
# ===== NHL SECTION =====
############################################################
elif sport_choice == "NHL":

    # --- Load NHL CSV automatically from repo ---
    try:
        nhl_df = pd.read_csv("nhl/data/nhlplayergamelogs.csv").fillna(0)
        nhl_df.columns = dedupe_columns(nhl_df.columns)
    except Exception as e:
        st.error(f"Could not load nhlplayergamelogs.csv: {e}")
        nhl_df = pd.DataFrame()

    # --- Player Type (REACTIVE) ---
    player_type_choice = st.sidebar.radio(
        "Player Type",
        ["Skaters", "Goalies"],
        key="nhl_player_type"
    )

    # Skater / Goalie selection
    if player_type_choice == "Skaters":

        all_stats = ["TOI","G","A","P","SOG","H","B","PPP","FOW"]
        default_stats = ["G","A","P","SOG","H"]

        stat_map = {
            "TOI": "toi_minutes",
            "G": "goals",
            "A": "assists",
            "P": "points",
            "SOG": "shots",
            "H": "hits",
            "B": "blocks",
            "PPP": "pp_points",
            "FOW": "faceoffs_won"
        }

    else:

        all_stats = ["SA","GA","SV","SV%"]
        default_stats = ["SA","GA","SV","SV%"]

        stat_map = {
            "SA": "shots_against",
            "GA": "goals_against",
            "SV": "saves",
            "SV%": "save_pct"
        }

    # --- Sidebar Form ---
    with st.sidebar.form(key="nhl_form"):
        
        nhl_stats_selected = st.multiselect(
            "Select Stats",
            options=all_stats,
            default=default_stats,
            key=f"nhl_stats_{player_type_choice}"
        )

        # Hit Rate Percentage slider (like NBA)
        nhl_percent_slider = st.slider("Hit Rate Percentage", min_value=40, max_value=100, step=5, value=80)

        # Game Window
        nhl_player_window = st.radio("Player Performance Window", ["L5", "L10", "ALL"], index=0)
        nhl_recent_n = 5 if nhl_player_window == "L5" else 10 if nhl_player_window == "L10" else None

        # Filter to today's teams
        nhl_filter_today = st.checkbox("Filter to today's teams", value=False)

        # --- Submit button ---
        submit_btn = st.form_submit_button("Calculate")

    # --- Only run analysis after button click ---
    if submit_btn and not nhl_df.empty:

        nhl_recent_pct = nhl_percent_slider / 100.0

        # Today's schedule
        today_str = datetime.now().strftime("%Y-%m-%d")
        nhl_todays, nhl_opp_map = get_nhl_todays_schedule(today_str)

        # Team defense
        try:
            team_def = pd.read_csv("nhl/data/nhlteamgametotals.csv").set_index("Team")
        except:
            team_def = pd.DataFrame()

        # B2B
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        nhl_b2b_map = compute_nhl_b2b(
            get_nhl_teams_on_date(today_str),
            get_nhl_teams_on_date(yesterday),
            get_nhl_teams_on_date(tomorrow)
        )

        # injuries (optional for now)
        inj_status_map = {}

        # --- ALL stats (full season) ---
        nhl_all = analyze_nhl_players(
            nhl_df,
            nhl_stats_selected,
            stat_map,
            recent_n=None,
            recent_pct=nhl_recent_pct,
            filter_teams=nhl_todays if nhl_filter_today else None,
            team_def_df=team_def,
            player_type=player_type_choice,
            b2b_map=nhl_b2b_map,
            inj_status_map=inj_status_map
        )

        # --- Recent window stats ---
        recent_map = {"L5": 5, "L10": 10, "ALL": None}
        recent_n = recent_map[nhl_player_window]

        if recent_n:
            nhl_recent = analyze_nhl_players(
                nhl_df,
                nhl_stats_selected,
                stat_map,
                recent_n=recent_n,
                recent_pct=nhl_recent_pct,
                filter_teams=nhl_todays if nhl_filter_today else None,
                team_def_df=team_def,
                player_type=player_type_choice,
                b2b_map=nhl_b2b_map,
                inj_status_map=inj_status_map
            )

        # --- Merge ALL + recent side by side ---
        key_cols = ["Player", "Pos", "Team", "Gms", "Opp", "B2B", "Status"]

        if recent_n:
            nhl_out = nhl_all.merge(
                nhl_recent,
                on=key_cols,
                how="left",
                suffixes=("", f"_L{recent_n}")  # keeps ALL columns as stat@XX, recent as L5stat@XX
            )
        else:
            nhl_out = nhl_all

        if nhl_out.empty:
            st.warning("No NHL players matched the criteria.")
        else:
            # Base + opponent columns
            base_cols = ["Player", "Pos", "Team", "Gms", "Opp", "B2B", "Status"]
            if player_type_choice == "Skaters":
                opp_cols = ["GA_A", "GA_R", "SA_A", "SA_R"]
            else:
                opp_cols = ["GF_A", "GF_R", "SF_A", "SF_R"]

            # --- Build interleaved stat columns (ALL + recent side by side) ---
            ordered_cols = base_cols + opp_cols
            for stat in nhl_stats_selected:
                # Full season / ALL
                all_col = f"{stat}@{int(nhl_recent_pct*100)}"   # G@80, A@80
                if all_col in nhl_out.columns:
                    ordered_cols.append(all_col)
                # Recent window (L5 / L10)
                if recent_n:
                    recent_col = f"L{recent_n}{stat}@{int(nhl_recent_pct*100)}"  # L5G@80, L5A@80
                    if recent_col in nhl_out.columns:
                        ordered_cols.append(recent_col)

            # Apply final column order
            nhl_out = nhl_out[[c for c in ordered_cols if c in nhl_out.columns]]

            # Column pinning
            col_config = {
                "Player": st.column_config.Column(pinned="left"),
                "Pos": st.column_config.Column(pinned="left"),
                "Team": st.column_config.Column(pinned="left"),
                "Opp": st.column_config.Column(pinned="left"),
            }

            # Display dataframe
            st.dataframe(
                nhl_out,
                width="stretch",
                hide_index=True,
                column_config=col_config
            )
