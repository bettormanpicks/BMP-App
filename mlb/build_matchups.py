import pandas as pd

# -------------------------
# CONFIG
# -------------------------
SCHEDULE_CSV = "data/2026_mlb_schedule.csv"
OUTPUT_CSV = "data/mlb_matchups.csv"

# -------------------------
# LOAD DATA
# -------------------------
box_2025 = pd.read_csv("data/2025boxscores.csv")
box_2026 = pd.read_csv("data/2026boxscores.csv")

# Combine both seasons
box = pd.concat([box_2025, box_2026], ignore_index=True)
schedule = pd.read_csv(SCHEDULE_CSV)

# Get all starting pitchers
starters = box[
    (box["is_pitcher"] == True) &
    (box["is_starter"] == True)
][["game_id", "team", "player"]]

# Rename for clarity
starters = starters.rename(columns={"player": "starting_pitcher"})

# Merge to attach opponent starter
box = box.merge(
    starters,
    left_on=["game_id", "opponent"],
    right_on=["game_id", "team"],
    how="left",
    suffixes=("", "_opp")
)

# Clean up column name
box.rename(columns={"starting_pitcher": "opposing_pitcher"}, inplace=True)

# Drop extra merge column
box.drop(columns=["team_opp"], inplace=True)

# Ensure consistent types
box["date"] = pd.to_datetime(box["date"])
schedule["date"] = pd.to_datetime(schedule["date"])

# -------------------------
# HELPER: Aggregate stats vs opponent
# -------------------------
def get_player_vs_opponent_stats(player_df, opponent):
    df = player_df[player_df["opponent"] == opponent]

    if df.empty:
        return {
            "games_vs_opp": 0,
            "hits_vs_opp": 0,
            "hr_vs_opp": 0,
            "hrr_vs_opp": 0,
            "k_rate_vs_opp": None
        }

    games = df["game_id"].nunique()
    hits = df["hits"].sum()
    hr = df["home_runs"].sum()
    hrr = df["hrr"].sum()
    hrr_per_game = hrr / games if games else 0
    hits_per_game = hits / games if games else 0
    hr_per_game = hr / games if games else 0

    # Strikeout rate (batters)
    pa = df["plate_appearances"].sum()
    k = df["strikeouts"].sum()
    k_rate = (k / pa) if pa else None

    return {
        "games_vs_opp": games,
        "hits_vs_opp": hits,
        "hr_vs_opp": hr,
        "hrr_vs_opp": hrr,
        "hrr_per_game": hrr_per_game,
        "hits_per_game": hits_per_game,
        "hr_per_game": hr_per_game,
        "k_rate_vs_opp": k_rate
    }

# -------------------------
# BUILD PITCHER STATS
# -------------------------
def get_pitcher_vs_opponent_stats(player_df, opponent):
    df = player_df[player_df["opponent"] == opponent]

    if df.empty:
        return {
            "games_vs_opp": 0,
            "ip_vs_opp": 0,
            "k_vs_opp": 0,
            "era_vs_opp": None,
            "whip_vs_opp": None
        }

    games = df["game_id"].nunique()
    outs = df["outs"].sum()
    ip = outs / 3 if outs else 0

    k = df["strikeouts_pitching"].sum()
    er = df["earned_runs"].sum()
    walks = df["walks_pitching"].sum()
    hits = df["hits_allowed"].sum()

    k_per_9 = (k * 9 / ip) if ip else None
    era = (er * 9 / ip) if ip else None
    whip = ((walks + hits) / ip) if ip else None

    return {
        "games_vs_opp": games,
        "ip_vs_opp": ip,
        "k_vs_opp": k,
        "k_per_9_vs_opp": k_per_9,
        "era_vs_opp": era,
        "whip_vs_opp": whip
    }

# -------------------------
# MATCHUP VS PITCHER
# -------------------------
def get_player_vs_pitcher_stats(player_df, pitcher_name):
    df = player_df[player_df["opposing_pitcher"] == pitcher_name]

    if df.empty:
        return {
            "games_vs_pitcher": 0,
            "hits_vs_pitcher": 0,
            "hr_vs_pitcher": 0,
            "hrr_vs_pitcher": 0
        }

    games = df["game_id"].nunique()
    hits = df["hits"].sum()
    hr = df["home_runs"].sum()
    hrr = df["hrr"].sum()

    return {
        "games_vs_pitcher": games,
        "hits_vs_pitcher": hits,
        "hr_vs_pitcher": hr,
        "hrr_vs_pitcher": hrr
    }

# -------------------------
# BUILD MATCHUPS
# -------------------------
rows = []

for _, game in schedule.iterrows():
    game_date = game["date"]
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_pitcher = game["home_pitcher"]
    away_pitcher = game["away_pitcher"]

    # Get all players for each team
    home_players = box[
        (box["team"] == home_team) &
        (box["date"] >= game_date - pd.Timedelta(days=30))
    ]["player"].unique()
    away_players = box[
        (box["team"] == away_team) &
        (box["date"] >= game_date - pd.Timedelta(days=30))
    ]["player"].unique()

    # -------------------------
    # HOME TEAM PLAYERS
    # -------------------------
    for player in home_players:
        player_df = box[
            (box["player"] == player) &
            (box["date"] >= game_date - pd.Timedelta(days=30))
        ]

        if player_df.empty:
            continue

        is_pitcher = player_df["is_pitcher"].iloc[0]

        if is_pitcher:
            stats = get_pitcher_vs_opponent_stats(player_df, away_team)
        else:
            stats = get_player_vs_opponent_stats(player_df, away_team)

            pitcher_stats = get_player_vs_pitcher_stats(player_df, away_pitcher)
            stats.update(pitcher_stats)

        if stats["games_vs_opp"] < 5:
            stats["small_sample"] = True
        else:
            stats["small_sample"] = False

        rows.append({
            "date": game_date,
            "player": player,
            "team": home_team,
            "opponent": away_team,
            "opposing_pitcher": away_pitcher,
            "is_pitcher": is_pitcher,
            **stats
        })

    # -------------------------
    # AWAY TEAM PLAYERS
    # -------------------------
    for player in away_players:
        player_df = box[
            (box["player"] == player) &
            (box["date"] >= game_date - pd.Timedelta(days=30))
        ]

        if player_df.empty:
            continue

        is_pitcher = player_df["is_pitcher"].iloc[0]

        if is_pitcher:
            stats = get_pitcher_vs_opponent_stats(player_df, home_team)
        else:
            stats = get_player_vs_opponent_stats(player_df, home_team)

            pitcher_stats = get_player_vs_pitcher_stats(player_df, home_pitcher)
            stats.update(pitcher_stats)

        if stats["games_vs_opp"] < 5:
            stats["small_sample"] = True
        else:
            stats["small_sample"] = False

        rows.append({
            "date": game_date,
            "player": player,
            "team": away_team,
            "opponent": home_team,
            "opposing_pitcher": home_pitcher,
            "is_pitcher": is_pitcher,
            **stats
        })

# -------------------------
# SAVE
# -------------------------
df = pd.DataFrame(rows)
df.to_csv(OUTPUT_CSV, index=False)

print(f"Saved {len(df)} matchup rows to {OUTPUT_CSV}")