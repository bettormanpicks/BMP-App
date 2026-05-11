import streamlit as st
import base64
import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime, timedelta, timezone
import pytz
import re

import sys
import os

# Ensure project root is on Python path (Streamlit Cloud fix)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ============================================================
# Shared utilities — always needed regardless of sport
# ============================================================
from shared.utils import (
    get_central_today, get_league_today, hit_rate_threshold,
    trim_df_to_recent_82, dedupe_columns, strip_display_ids,
    norm_name, get_teams_playing_on_date, sidebar_footer
)

# ============================================================
# Sport-specific imports are deferred to each sport's block
# below to avoid loading all helpers on every session.
# ============================================================

import streamlit_analytics2 as streamlit_analytics

with streamlit_analytics.track():

    # ============================================================
    # PAGE CONFIG
    # ============================================================
    st.set_page_config(
        page_title="Bettor Man Picks Stat Analyzer",
        layout="wide"
    )

    st.html("""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-DG3DDELFYK"></script>
    <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-DG3DDELFYK');
    </script>
    """)

    ############################################################
    # SPORT SELECTION
    ############################################################
    sport_choice = st.sidebar.selectbox("Select Sport", ["MLB", "NBA", "NHL", "Table Tennis", "Tennis"]) #, "NFL", "NHL"])

    nba_today = get_league_today()
    nhl_date = get_league_today()
    central_today = get_central_today()
    central_dt = datetime.strptime(central_today, "%Y-%m-%d")

    # Determine the title and date based on sport
    if sport_choice == "MLB":
        hero_title = "MLB — Player Analyzer"
        hero_date = f"MLB date: {central_dt.strftime('%b %d')} (rolls over at 3:00 AM CT)"
    elif sport_choice == "NBA":
        hero_title = "NBA — Player Hit Rates"
        hero_date = f"NBA date: {nba_today.strftime('%b %d')} (rolls over at 3:00 AM CT)"
    elif sport_choice == "NHL":
        hero_title = "NHL — Player Hit Rates"
        hero_date = f"NHL date: {nhl_date.strftime('%b %d')} (rolls over at 3:00 AM CT)"
    elif sport_choice == "Table Tennis":
        hero_title = "Table Tennis - H2H History"
        hero_date = f"{sport_choice} date: {central_dt.strftime('%b %d')} (rolls over at 3:00 AM CT)"
    else:
        hero_title = f"{sport_choice} — Player Hit Rates"
        hero_date = f"{sport_choice} date: {central_dt.strftime('%b %d')} (rolls over at 3:00 AM CT)"

    # ============================================================
    # HEADER BANNER (hero header with title + date)
    # ============================================================
    @st.cache_data
    def _encode_banner(image_path):
        """Read and base64-encode the banner once per session."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def set_header_banner(image_path, image_width=1500, image_height=150):
        """
        Sets a full-width hero banner at the top of the page, preserving the entire image.

        image_width / image_height: the actual pixel dimensions of your banner image
        """
        aspect_ratio_pct = (image_height / image_width) * 100  # padding-top % to preserve aspect ratio

        data = _encode_banner(image_path)  # cached — only reads disk once per session

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
                padding: 0px 0px;
                border-radius: 2px;
                margin-top: -15px;
                margin-bottom: 5px;
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

    # Sidebar logo
    st.sidebar.image("assets/logo.png", width=170)

    # Additional CSS tweaks


    ############################################################
    # ===== MLB SECTION =====
    ############################################################

    # Module-level constant — built once, not on every submit
    MLB_TEAM_TRICODES = {
        "Los Angeles Dodgers": "LAD",
        "Toronto Blue Jays": "TOR",
        "New York Yankees": "NYY",
        "Baltimore Orioles": "BAL",
        "Boston Red Sox": "BOS",
        "Chicago White Sox": "CWS",
        "Chicago Cubs": "CHC",
        "San Francisco Giants": "SF",
        "St. Louis Cardinals": "STL",
        "Houston Astros": "HOU",
        "Atlanta Braves": "ATL",
        "Philadelphia Phillies": "PHI",
        "Washington Nationals": "WSH",
        "Arizona Diamondbacks": "ARI",
        "Miami Marlins": "MIA",
        "New York Mets": "NYM",
        "Cincinnati Reds": "CIN",
        "Pittsburgh Pirates": "PIT",
        "Milwaukee Brewers": "MIL",
        "Minnesota Twins": "MIN",
        "Kansas City Royals": "KC",
        "Tampa Bay Rays": "TB",
        "Athletics": "ATH",
        "Los Angeles Angels": "LAA",
        "Seattle Mariners": "SEA",
        "Texas Rangers": "TEX",
        "Colorado Rockies": "COL",
        "San Diego Padres": "SD",
        "Detroit Tigers": "DET",
        "Cleveland Guardians": "CLE",
    }

    if sport_choice == "MLB":

        # --- Lazy imports: only loaded when MLB is selected ---
        from mlb.helpers import load_mlb_raw_data, get_today_schedule, get_player_game_log

        # --- Load MLB data ---
        try:
            box_df, schedule_df = load_mlb_raw_data()

        except Exception as e:
            st.error(f"Could not load MLB data: {e}")
            box_df = pd.DataFrame()
            schedule_df = pd.DataFrame()

        # --- Player Type ---
        player_type_choice = st.sidebar.radio(
            "Player Type",
            ["Batters", "Pitchers"],
            key="mlb_player_type",
            horizontal=True
        )

        # --- Sidebar Form ---
        with st.sidebar.form(key="mlb_form"):

            # --- Performance Window ---
            performance_window = st.radio(
                "Performance Window",
                ["L5", "L10", "L30", "ALL"],
                horizontal=True, index=1
            )

            # --- Hit Rate ---
            hit_rate_pct = st.slider(
                "Hit Rate %",
                min_value=40,
                max_value=100,
                value=80,
                step=5
            )

            vs_today_pitcher = st.checkbox("Stats vs Today's Pitcher", value=False)

            mlb_filter_today = st.checkbox("View Today's Games", value=False)

            submit_btn = st.form_submit_button("Calculate")

        sidebar_footer()

        if submit_btn:

            if mlb_filter_today:
                games_to_show = get_today_schedule(schedule_df)
            else:
                games_to_show = schedule_df

            if games_to_show.empty:
                st.warning("No games found in schedule.")
            else:

                # -------------------------
                # STAT MAPS
                # -------------------------
                BATTER_STAT_MAP = {
                    "H":    "hits",
                    "1B":    "singles",
                    "2B":    "doubles",
                    "3B":    "triples",
                    "HR":   "home_runs",
                    "TB":   "total_bases",
                    "RBI":  "rbi",
                    "R":    "runs",
                    "SB":   "stolen_bases",
                    "HRR":  "hrr",
                    "W(B)": "walks",
                    "K(B)": "strikeouts",
                }

                PITCHER_STAT_MAP = {
                    "O": "outs",
                    "K":  "strikeouts_pitching",
                    "HA": "hits_allowed",
                    "ER": "earned_runs",
                    "W":  "walks_pitching",
                }

                rows = []

                # --- LOOP OVER GAMES AND PLAYERS ---
                for _, game in games_to_show.iterrows():
                    home_team = game["home_team"]
                    away_team = game["away_team"]
                    home_pitcher = game["home_pitcher"]
                    away_pitcher = game["away_pitcher"]

                    for player, team, opp, opp_pitcher in [
                        *[(p, home_team, away_team, away_pitcher) for p in box_df[box_df["team"] == home_team]["player"].unique()],
                        *[(p, away_team, home_team, home_pitcher) for p in box_df[box_df["team"] == away_team]["player"].unique()],
                    ]:
                        player_df = box_df[box_df["player"] == player]
                        if player_df.empty:
                            continue

                        is_pitcher = player_df["is_pitcher"].iloc[0]
                        if player_type_choice == "Batters" and is_pitcher:
                            continue
                        if player_type_choice == "Pitchers" and not is_pitcher:
                            continue

                        game_log = get_player_game_log(
                            box_df=box_df,
                            player=player,
                            window=performance_window,
                            opponent=opp if (vs_today_pitcher and player_type_choice == "Pitchers") else None,
                            pitcher=opp_pitcher if (vs_today_pitcher and player_type_choice == "Batters") else None,
                            all_opponents=not vs_today_pitcher
                        )

                        if game_log.empty:
                            continue

                        # For pitchers, skip non-starters
                        if player_type_choice == "Pitchers":
                            if not game_log["is_starter"].any():
                                continue
                            game_log = game_log[game_log["is_starter"] == True]

                        # EBH is derived — add it to the game log
                        if player_type_choice == "Batters":
                            game_log = game_log.copy()
                            game_log["ebh"] = game_log["doubles"] + game_log["triples"] + game_log["home_runs"]

                        stat_map = BATTER_STAT_MAP if player_type_choice == "Batters" else PITCHER_STAT_MAP
                        gms = game_log["game_id"].nunique()

                        stat_floors = {}
                        for stat, col in stat_map.items():
                            if col in game_log.columns:
                                stat_floors[stat] = hit_rate_threshold(game_log[col], hit_rate_pct)
                            else:
                                stat_floors[stat] = 0

                        # Handle EBH separately for batters
                        if player_type_choice == "Batters":
                            stat_floors["EBH"] = hit_rate_threshold(game_log["ebh"], hit_rate_pct)

                        row = {
                            "DateUTC": game["date"],
                            "Player": player,
                            "Team": team,
                            "Opp": opp,
                            "Gms": gms,
                            **stat_floors
                        }

                        if player_type_choice == "Batters":
                            row["Pitcher"] = opp_pitcher

                        rows.append(row)

                # -------------------------
                # --- BUILD DATAFRAME ---
                # -------------------------
                df = pd.DataFrame(rows)

                if df.empty:
                    st.warning("No players found.")
                else:
                    # Ensure DateUTC is timezone-aware UTC
                    df["DateUTC"] = pd.to_datetime(df["DateUTC"], utc=True)

                    # Convert to Chicago time for display only
                    local_tz = pytz.timezone("America/Chicago")
                    df["DateLocal"] = df["DateUTC"].dt.tz_convert(local_tz)
                    df["Date / Time"] = df["DateLocal"].dt.strftime("%Y-%m-%d %H:%M")

                    df["Team"] = df["Team"].map(MLB_TEAM_TRICODES).fillna(df["Team"])
                    df["Opp"] = df["Opp"].map(MLB_TEAM_TRICODES).fillna(df["Opp"])

                    # -------------------------
                    # --- Display Table ---
                    # -------------------------
                    if player_type_choice == "Pitchers":
                        display_cols = [
                            "Date / Time", "Player", "Team", "Opp",
                            "Gms", "O", "K", "HA", "ER", "W"
                        ]
                        sort_col = "K"
                    else:  # Batters
                        display_cols = [
                            "Date / Time", "Player", "Team", "Opp", "Pitcher",
                            "Gms", "H", "1B", "2B", "3B", "HR", "TB",
                            "RBI", "R", "SB", "EBH", "HRR", "W(B)", "K(B)"
                        ]
                        sort_col = "HRR"

                    df_to_display = df[[c for c in display_cols if c in df.columns]]

                    st.dataframe(
                        df_to_display.sort_values(sort_col, ascending=False),
                        hide_index=True
                    )

    ############################################################
    # ===== NBA SECTION (Multi-sport compatible) =====
    ############################################################
    elif sport_choice == "NBA":

        # --- Lazy imports: only loaded when NBA is selected ---
        from nba.helpers import (
            DEF_STAT_MAP, load_nba_schedule, load_today_matchups,
            load_nba_injury_status, parse_nba_matchup,
            add_team_opponent_columns, compute_player_percentiles,
            load_todays_schedule, compute_team_b2b_from_schedule,
            normalize_nba_position, normalize_nba_position_display,
            add_combo_stats, load_nba_raw_data, load_defense_tables
        )
        from nba.nbadefense import get_team_def_ranks, get_team_def_ranks_by_position

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
                "Select Stats",
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

        sidebar_footer()

        # --- Calculate button ---
        if calculate:

            # Trim to most recent 82 games per player
            df_calc = trim_df_to_recent_82(df)

            # --- Cached Defense Tables ---
            # Pass the already-loaded DataFrames so load_defense_tables never
            # re-reads the CSVs internally.
            overall_def, pos_def_df = load_defense_tables(defense_window, df, team_totals_df)

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
            # schedule_data is still loaded for load_today_matchups; B2B now
            # uses the path-based signature so no dict is passed to the cache.
            schedule_data = load_nba_schedule()
            todays_teams, today_matchups = load_today_matchups()
            team_b2b_map = compute_team_b2b_from_schedule()

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

            #csv_bytes = strip_display_ids(summary_df).to_csv(index=False).encode()
            #st.download_button("Download CSV", csv_bytes, "player_stats.csv")

    ############################################################
    # ===== NHL SECTION =====
    ############################################################
    elif sport_choice == "NHL":

        # --- Lazy imports: only loaded when NHL is selected ---
        from nhl.helpers import (
            load_nhl_raw_data, load_nhl_injuries, get_nhl_todays_schedule,
            compute_nhl_b2b, analyze_nhl_players, get_nhl_teams_on_date,
            get_nhl_injuries
        )

        # --- Load NHL static data (game logs + team games, no TTL) ---
        try:
            nhl_df, nhlteamgames_df = load_nhl_raw_data()
            nhl_df.columns = dedupe_columns(nhl_df.columns)
        except Exception as e:
            st.error(f"Could not load NHL data: {e}")
            nhl_df = pd.DataFrame()
            nhlteamgames_df = pd.DataFrame()

        # --- Load NHL injuries separately (TTL=900 so it refreshes mid-session) ---
        try:
            injuries_df = load_nhl_injuries()
        except Exception as e:
            st.warning(f"Could not load NHL injuries: {e}")
            injuries_df = pd.DataFrame()

        # --- Player Type (REACTIVE) ---
        player_type_choice = st.sidebar.radio(
            "Player Type",
            ["Skaters", "Goalies"],
            key="nhl_player_type"
        )

        # --- Stat mapping based on player type ---
        if player_type_choice == "Skaters":
            all_stats = ["TOI","G","A","P","S","H","B","PPP","FOW"]
            default_stats = ["G","A","P","S","H"]
            stat_map = {
                "TOI": "toi_minutes",
                "G": "goals",
                "A": "assists",
                "P": "points",
                "S": "shots",
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

            nhl_percent_slider = st.slider(
                "Hit Rate Percentage",
                min_value=40, max_value=100, step=5, value=80
            )

            nhl_player_window = st.radio(
                "Player Performance Window",
                ["L5", "L10", "ALL"],
                index=0
            )

            # --- Opponent Window (dynamic label) ---
            opp_window_label = "Opponent Defensive Window" if player_type_choice == "Skaters" else "Opponent Offensive Window"
            nhl_opp_window = st.radio(
                opp_window_label,
                ["L5", "L10", "ALL"],
                index=0
            )

            nhl_filter_today = st.checkbox("Filter To Today's Teams", value=False)

            submit_btn = st.form_submit_button("Calculate")

        sidebar_footer()

        # --- Only run analysis after submit ---
        if submit_btn and not nhl_df.empty:

            nhl_recent_pct = nhl_percent_slider / 100.0

            # Map windows to recent_n
            recent_map = {"L5": 5, "L10": 10, "ALL": None}
            nhl_recent_n = recent_map[nhl_player_window]
            opp_recent_n = recent_map[nhl_opp_window]

            # Today's schedule
            nhl_todays, nhl_opp_map = get_nhl_todays_schedule()

            # Team defense/offense (optional CSV fallback)
            try:
                team_def = pd.read_csv("nhl/data/nhlteamgametotals.csv").set_index("Team")
            except:
                team_def = pd.DataFrame()

            # B2B mapping
            import pytz
            central = pytz.timezone("America/Chicago")
            now_ct = datetime.now(central)

            today_str = now_ct.strftime("%Y-%m-%d")
            yesterday = (now_ct - timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow = (now_ct + timedelta(days=1)).strftime("%Y-%m-%d")
            nhl_b2b_map = compute_nhl_b2b(
                get_nhl_teams_on_date(today_str),
                get_nhl_teams_on_date(yesterday),
                get_nhl_teams_on_date(tomorrow)
            )

            inj_status_map = {norm_name(row["Player"]): row["Status_norm"] for _, row in injuries_df.iterrows()}

            # --- Player Analysis: ALL season stats ---
            nhl_all = analyze_nhl_players(
                nhl_df=nhl_df,
                nhl_stats_selected=nhl_stats_selected,
                stat_map=stat_map,
                recent_n=nhl_recent_n,
                recent_pct=nhl_recent_pct,
                filter_teams=nhl_todays if nhl_filter_today else None,
                nhlteamgames_df=nhlteamgames_df,
                player_type=player_type_choice,
                opp_recent_n=opp_recent_n,
                b2b_map=nhl_b2b_map,
                inj_status_map=inj_status_map,
                opp_map=nhl_opp_map           # ← add this line
            )

            # --- Merge ALL + Recent (player stats only) ---
            key_cols = ["Player","Pos","Team","Gms","Opp","B2B","Status"]
            nhl_out = nhl_all  # analyze_nhl_players already returns ALL + recent

            if nhl_out.empty:
                st.warning("No NHL players matched the criteria.")
            else:

                # Base + opponent columns
                base_cols = ["Player","Pos","Team","Gms","Opp","B2B","Status"]
                if player_type_choice == "Skaters":
                    opp_cols = ["GA_A","GA_R","SA_A","SA_R"]
                else:
                    opp_cols = ["GF_A","GF_R","SF_A","SF_R"]

                # Interleave player stats (ALL + recent)
                ordered_cols = base_cols + opp_cols
                for stat in nhl_stats_selected:
                    all_col = f"{stat}@{int(nhl_recent_pct*100)}"
                    if all_col in nhl_out.columns:
                        ordered_cols.append(all_col)
                    if nhl_recent_n:
                        recent_col = f"L{nhl_recent_n}{stat}@{int(nhl_recent_pct*100)}"
                        if recent_col in nhl_out.columns:
                            ordered_cols.append(recent_col)

                nhl_out = nhl_out[[c for c in ordered_cols if c in nhl_out.columns]]

                # --- Force opponent averages to display 2 decimals ---
                float_opp_cols = ["GA_A","SA_A","GF_A","SF_A"]

                for col in float_opp_cols:
                    if col in nhl_out.columns:
                        nhl_out[col] = nhl_out[col].apply(
                            lambda x: f"{x:.2f}" if pd.notnull(x) else ""
                        )

                # Column pinning
                col_config = {
                    "Player": st.column_config.Column(pinned="left"),
                    "Pos": st.column_config.Column(pinned="left"),
                    "Team": st.column_config.Column(pinned="left"),
                    "Opp": st.column_config.Column(pinned="left"),
                }

                st.dataframe(
                    nhl_out,
                    width="stretch",
                    hide_index=True,
                    column_config=col_config
                )


    ############################################################
    # ===== Table Tennis Section =====
    ############################################################
    if sport_choice == "Table Tennis":

        # --- Lazy imports: only loaded when Table Tennis is selected ---
        from tabletennis.helpers import (
            load_tt_raw_data,
            load_tt_all_leagues,
            build_h2h_index,
            compute_h2h_stats
        )

        # --- League selector (outside form so we know which CSVs to load) ---
        league = st.sidebar.radio(
            "Select League",
            ["TT Elite", "Czech", "TT Cup", "Setka", "All"],
            horizontal=True
        )

        # --- Sidebar Filters ---
        with st.sidebar.form("TT Filters"):

            recency_window = st.radio(
                "Recency Window", ["L25", "L50", "ALL"], index=0, horizontal=True
            )

            min_matches = st.slider(
                "Minimum H2H Matches",
                min_value=5,
                max_value=60,
                step=5,
                value=20
            )

            # --- Stat Selection ---
            stat_options = [
                "NS%",
                "1ALL%",
                "P1 BB%",
                "P1 BB#",
                "P2 BB%",
                "P2 BB#",
                "P1 SR%",
                "P1 SR#",
                "P2 SR%",
                "P2 SR#",
                "P1 S",
                "P2 S",
                "P1 W",
                "P2 W",
                "P1 W%",
                "3Set%",
                "4Set%",
                "5Set%",
                "ATS",
                "SS",
                "ATP",
                "PS",
                "P1 SlowS",
                "P1 Rec%",
                "P1 Rec#",
                "P2 SlowS",
                "P2 Rec%",
                "P2 Rec#",
            ]

            selected_stats = st.multiselect(
                "Advanced Filters",
                stat_options,
                key="Advanced Filters"
            )

            st.markdown("Filter Thresholds (optional)")

            stat_thresholds = {}

            for stat in selected_stats:
                col1, col2 = st.columns([2, 1])

                col1.write(stat)
                val = col2.text_input(
                    "min_input",
                    key=f"min_{stat}",
                    label_visibility="collapsed"
                )

                if val.strip() != "":
                    try:
                        stat_thresholds[stat] = float(val)
                    except ValueError:
                        pass  # ignore bad input

            col1, col2 = st.columns(2)

            with col1:
                calculate = st.form_submit_button("Calculate")

            with col2:
                reset = st.form_submit_button("Reset")

        if reset:
            # Remove stat selection
            if "Advanced Filters" in st.session_state:
                del st.session_state["Advanced Filters"]

            # Clear all threshold inputs
            for stat in stat_options:
                key = f"min_{stat}"
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()

        sidebar_footer()

        # --- Show info if user hasn't clicked Calculate yet ---
        if not calculate:
            st.info("Select a league and click Calculate to load upcoming matches.")
        else:
            # --- Load data inside Calculate (cached, safe, on-demand) ---
            with st.spinner("Loading and processing data..."):
                if league == "All":
                    schedule, matchlogs, h2h, h2h_index = load_tt_all_leagues()
                else:
                    schedule, matchlogs, h2h, h2h_index = load_tt_raw_data(league)

                schedule = schedule.copy()
                if matchlogs is not None:
                    matchlogs = matchlogs.copy()

            # --- Parse CSV dates and drop bad rows ---
            schedule["date"] = pd.to_datetime(schedule["date"], errors="coerce")
            schedule = schedule.dropna(subset=["date"])

            # --- Localize schedule dates to CST ---
            central = pytz.timezone("America/Chicago")
            schedule["date"] = schedule["date"].dt.tz_localize("UTC").dt.tz_convert(central)

            # --- Current CST time ---
            now_ct = pd.Timestamp.now(central)

            # --- Filter upcoming matches ---
            grace_period = pd.Timedelta(minutes=20)
            upcoming = schedule[schedule["date"] + grace_period >= now_ct]

            rows = []
            for _, row in upcoming.iterrows():
                p1, p2 = row["player1"], row["player2"]
                p1_display, p2_display = row["player1_display"], row["player2_display"]

                stats = compute_h2h_stats(h2h_index, p1, p2, window=recency_window)
                if stats is None:
                    stats = {
                        "matches": 0,
                        "a_wins": 0,
                        "b_wins": 0,
                        "win_pct": 0,
                        "last_played": None,
                        "sweeps_a": 0,
                        "sweeps_b": 0,
                        "non_sweep_pct": 0,
                        "avg_total_sets": 0,
                        "ATP": 0,
                        "PS": 0,
                        "SS": 0
                    }

                row_dict = {
                    "Date": row["date"].strftime("%Y-%m-%d %H:%M"),
                    "Player 1": p1_display,
                    "Player 2": p2_display,
                    "Matches": stats["matches"],
                    "Non Sweep %": round(stats.get("non_sweep_pct", 0) * 100, 1),
                    "One-All %": round(stats.get("one_all_pct", 0) * 100, 1),
                    "P1 B%": round(stats.get("a_bounce_pct", 0) * 100, 1),
                    "P1 BB#": stats.get("a_bounce_n", 0),
                    "P2 B%": round(stats.get("b_bounce_pct", 0) * 100, 1),
                    "P2 BB#": stats.get("b_bounce_n", 0),
                    "P1 SR%": round(stats.get("a_sr_pct", 0) * 100, 1),
                    "P1 SR#": stats.get("a_sr_n", 0),
                    "P2 SR%": round(stats.get("b_sr_pct", 0) * 100, 1),
                    "P2 SR#": stats.get("b_sr_n", 0),
                    "P1 Sweeps": stats.get("sweeps_a", 0),
                    "P2 Sweeps": stats.get("sweeps_b", 0),
                    "P1 Wins": stats["a_wins"],
                    "P2 Wins": stats["b_wins"],
                    "Win % (P1)": round(stats["win_pct"] * 100, 1),
                    "3Set %":  round(stats.get("pct_3sets", 0) * 100, 1),
                    "4Set %":  round(stats.get("pct_4sets", 0) * 100, 1),
                    "5Set %":  round(stats.get("pct_5sets", 0) * 100, 1),
                    "Avg Total Sets": round(stats.get("avg_total_sets", 0), 2),
                    "SS": round(stats.get("SS", 0), 2),
                    "ATP": round(stats.get("ATP", 0), 2),
                    "PS": round(stats.get("PS", 0), 2),
                    "P1 SS":    round(stats.get("a_ss_score", 0) * 100, 1),
                    "P1 Rec%":  round(stats.get("a_recovery_pct", 0) * 100, 1),
                    "P1 Rec#":  stats.get("a_recovery_n", 0),
                    "P2 SS":    round(stats.get("b_ss_score", 0) * 100, 1),
                    "P2 Rec%":  round(stats.get("b_recovery_pct", 0) * 100, 1),
                    "P2 Rec#":  stats.get("b_recovery_n", 0),
                    "Last Played": stats["last_played"]
                }

                if league == "All":
                    row_dict["League"] = row["league"]

                rows.append(row_dict)

            df = pd.DataFrame(rows)

            # --- Apply minimum match filter ---
            if df.empty or "Matches" not in df.columns:
                st.info("No upcoming matches meet the filter criteria.")
                st.stop()

            df = df[df["Matches"] >= min_matches]
            if df.empty:
                st.info("No upcoming matches meet the filter criteria.")
                st.stop()

            DISPLAY_NAMES = {
                "Date": "Match Start",
                "League": "League",
                "Matches": "Ms",
                "Non Sweep %": "NS%",
                "One-All %": "1ALL%",
                "P1 B%": "P1 BB%",
                "P1 BB#": "P1 BB#",
                "P2 B%": "P2 BB%",
                "P2 BB#": "P2 BB#",
                "P1 SR%": "P1 SR%",
                "P1 SR#": "P1 SR#",
                "P2 SR%": "P2 SR%",
                "P2 SR#": "P2 SR#",
                "P1 Sweeps": "P1 S",
                "P2 Sweeps": "P2 S",
                "P1 Wins": "P1 W",
                "P2 Wins": "P2 W",
                "Win % (P1)": "P1 W%",
                "3Set %": "3Set%",
                "4Set %": "4Set%",
                "5Set %": "5Set%",
                "Avg Total Sets": "ATS",
                "SS": "SS",
                "ATP": "ATP",
                "PS": "PS",
                "P1 SS": "P1 SlowS",
                "P1 Rec%": "P1 Rec%",
                "P1 Rec#": "P1 Rec#",
                "P2 SS": "P2 SlowS",
                "P2 Rec%": "P2 Rec%",
                "P2 Rec#": "P2 Rec#",
            }

            df_display = df.rename(columns=DISPLAY_NAMES)

            if league == "All":
                cols = df_display.columns.tolist()
                cols.remove("League")
                cols.insert(1, "League")
                df_display = df_display[cols]

            if stat_thresholds:
                mask = pd.Series(True, index=df_display.index)

                for stat, threshold in stat_thresholds.items():
                    if stat in df_display.columns:
                        mask &= df_display[stat] >= threshold

                df_display = df_display[mask]

                if df_display.empty:
                    st.warning("All rows filtered out — try lowering thresholds.")
                    st.stop()

            always_keep = ["Match Start", "Player 1", "Player 2", "Ms"]
            pinned_cols = ["Match Start", "Player 1", "Player 2", "Ms"]

            if league == "All":
                always_keep = ["Match Start", "League", "Player 1", "Player 2", "Ms"]
                pinned_cols = ["Match Start", "League", "Player 1", "Player 2", "Ms"]

            if selected_stats:
                display_cols = always_keep + [c for c in selected_stats if c in df_display.columns]
                st.caption(f"Showing {len(display_cols)} columns (filtered view)")
            else:
                display_cols = df_display.columns.tolist()
                st.caption("Showing all columns")

            # Only pin columns that actually exist in the current display
            col_config = {
                c: st.column_config.Column(pinned="left")
                for c in pinned_cols
                if c in display_cols
            }

            st.dataframe(
                df_display[display_cols].sort_values("Match Start"),
                width="stretch",
                height=350,
                hide_index=True,
                column_config=col_config
            )


    ############################################################
    # ===== Tennis Section =====
    ############################################################
    if sport_choice == "Tennis":

        # --- Lazy imports: only loaded when Tennis is selected ---
        from tennis.tennishelpers import (
            load_tennis_raw_data,
            load_tennis_schedule,
            load_tennis_players,
            compute_tennis_percentiles,
            load_tennis_defense
        )

        # --- ATP / WTA selection ---
        tour_choice = st.sidebar.radio("Tour", ["ATP", "WTA"])

        # --- Load gamelogs ---
        df = load_tennis_raw_data(tour=tour_choice)

        # --- Sidebar Filters ---
        with st.sidebar.form("Tennis Filters"):

            stats_available = ["GW", "GL", "GD", "TG", "MW"]
            stats_selected = st.multiselect(
                "Select Stats", stats_available, default=stats_available
            )

            percentages = [st.slider("Hit Rate %", 40, 100, 80, 5)]

            player_window = st.radio("Player Performance Window", ["L5", "L10", "ALL"], index=0)
            recent_n = 5 if player_window == "L5" else 10 if player_window == "L10" else None

            players_with_match = st.checkbox("Players With A Match Soon", value=True)

            # --- Only show surface filter if historical mode ---
            surface_choice = None
            if not players_with_match:
                surface_choice = st.selectbox("Surface Filter (historical)", ["All", "Hard", "Clay", "Grass"])

            calculate = st.form_submit_button("Calculate")

        sidebar_footer()

        # --- Calculate ---
        if calculate:

            df_calc = df.copy()

            # Load schedule only once
            schedule_df = load_tennis_schedule()
            today = datetime.today().date()
            tomorrow = today + timedelta(days=1)

            if players_with_match:
                # Filter schedule to today/tomorrow
                schedule_upcoming = schedule_df[schedule_df["Date"].isin([today, tomorrow])]
                scheduled_ids = set(schedule_upcoming["player_id"]).union(set(schedule_upcoming["opponent_id"]))

                # Keep only players in upcoming matches
                df_calc = df_calc[df_calc["player_id"].isin(scheduled_ids)]
            else:
                schedule_upcoming = None  # Not used in historical mode

            # --- Compute percentiles ---
            summary_df = compute_tennis_percentiles(
                df_calc,
                stats_selected,
                percentages,
                recent_n=recent_n,
                upcoming_only=players_with_match,
                schedule_df=schedule_upcoming if players_with_match else None,
                surface_filter=surface_choice if not players_with_match else None
            )

            if summary_df.empty:
                st.warning("No data available for the selected players/surface.")
            else:
                if players_with_match:
                    # --- Attach opponent return tier and display names ---
                    defense_df = load_tennis_defense()
                    summary_df = summary_df.merge(
                        defense_df[["player_id", "surface", "return_tier"]],
                        left_on=["opponent_id", "Surface"],
                        right_on=["player_id", "surface"],
                        how="left",
                        suffixes=("", "_opp")
                    )

                    players_df = load_tennis_players()
                    name_lookup = dict(zip(players_df["player_id"], players_df["player_name"]))
                    summary_df["Opponent"] = summary_df["opponent_id"].map(name_lookup).fillna(summary_df["opponent_id"])

                    summary_df.rename(columns={"return_tier": "Opponent Strength"}, inplace=True)
                    summary_df.drop(columns=["player_id_opp", "surface"], errors="ignore", inplace=True)

                    if players_with_match:
                        # --- Prepare schedule info for merging ---
                        schedule_info_cols = ["player_id", "opponent_id", "Date", "Time", "Tournament"]
                        schedule_merge_df = schedule_upcoming[schedule_info_cols].copy()

                        # --- Duplicate each match row to cover inverse ordering ---
                        schedule_inverse = schedule_merge_df.rename(
                            columns={"player_id": "opponent_id", "opponent_id": "player_id"}
                        )
                        schedule_expanded = pd.concat([schedule_merge_df, schedule_inverse], ignore_index=True)

                        # --- Merge with summary_df ---
                        summary_df = summary_df.merge(
                            schedule_expanded,
                            on=["player_id", "opponent_id"],
                            how="left"
                        )

                        # --- Rename Time → Status for display ---
                        summary_df.rename(columns={"Time": "Status"}, inplace=True)

                # --- Rename Gms → Ms for matches played ---
                summary_df.rename(columns={"Gms": "Ms"}, inplace=True)

                # --- Build display column order explicitly ---
                display_cols = ["Player"]

                if players_with_match:
                    display_cols.extend([
                        "Opponent",
                        "Opponent Strength",
                        "Date",
                        "Status",
                        "Tournament"
                    ])

                display_cols.extend(["Surface", "Ms"])

                # --- Collect stat columns in correct order ---
                stat_cols = []
                for stat in stats_selected:
                    if stat == "MW":
                        if "MW%" in summary_df.columns:
                            stat_cols.append("MW%")
                        if recent_n and f"L{recent_n}MW%" in summary_df.columns:
                            stat_cols.append(f"L{recent_n}MW%")
                    else:
                        for pct in percentages:
                            col_all = f"{stat}@{pct}"
                            col_recent = f"L{recent_n}{stat}@{pct}" if recent_n else None
                            if col_all in summary_df.columns:
                                stat_cols.append(col_all)
                            if col_recent and col_recent in summary_df.columns:
                                stat_cols.append(col_recent)

                display_cols.extend(stat_cols)

                # --- Keep only intended columns (prevents ID leakage) ---
                summary_df = summary_df[[c for c in display_cols if c in summary_df.columns]]

                # --- Sorting ---
                first_stat = stats_selected[0]
                if first_stat == "MW":
                    sort_col = f"L{recent_n}MW%" if recent_n else "MW%"
                else:
                    sort_col = f"{first_stat}@{percentages[0]}"

                if sort_col in summary_df.columns:
                    summary_df = summary_df.sort_values(sort_col, ascending=False)

                # --- Display in Streamlit ---
                st.dataframe(
                    summary_df,
                    width="stretch",
                    hide_index=True
                )