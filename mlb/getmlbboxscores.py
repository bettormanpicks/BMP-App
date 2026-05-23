import os
import pandas as pd
import requests
import time
import json
import csv
import pytz
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
API_KEY = "sbfz4jp8sasou2ux1wrov7w"
BASE_URL = "https://api.sportsblaze.com/mlb/v1"
OUTPUT_CSV = "data/2026boxscores.csv"

def get_date_range(csv_path):
    """
    Determine start and end dates automatically.
    - Start: day after the most recent date already in the CSV.
             Falls back to the current season opener if CSV doesn't exist.
    - End: yesterday (today's games aren't finished yet).
    """
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    if os.path.exists(csv_path):
        try:
            existing = pd.read_csv(csv_path, usecols=["date"])
            if not existing.empty:
                latest = pd.to_datetime(existing["date"]).max().date()
                start = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
                return start, yesterday
        except Exception:
            pass

    # Fallback: start of 2026 MLB season
    return "2026-03-26", yesterday

START_DATE, END_DATE = get_date_range(OUTPUT_CSV)

total_requests = 0
last_request_time = 0
MIN_DELAY = 6.2  # seconds (10 req/min = 6 sec, add buffer)

# -------------------------
# HELPER FUNCTIONS
# -------------------------
def rate_limit():
    global last_request_time
    now = time.time()
    elapsed = now - last_request_time

    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)

    last_request_time = time.time()

def append_to_csv(file_path, data):
    if not data:
        return

    file_exists = False
    try:
        with open(file_path, "r"):
            file_exists = True
    except FileNotFoundError:
        pass

    with open(file_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())

        # Only write header if file is new
        if not file_exists:
            writer.writeheader()

        writer.writerows(data)

def daterange(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    for n in range(int((end - start).days) + 1):
        yield start + timedelta(n)

def fetch_daily_games(date_str):
    global total_requests
    url = f"{BASE_URL}/boxscores/daily/{date_str}.json?key={API_KEY}"

    while True:
        rate_limit()
        resp = requests.get(url)
        total_requests += 1

        if resp.status_code == 200:
            data = resp.json()
            return data.get("games", [])

        elif resp.status_code == 429:
            print(f"⏳ Rate limited on {date_str}, sleeping 60s...")
            time.sleep(60)

        else:
            print(f"❌ Error fetching {date_str}: {resp.status_code}")
            return []

def extract_players_from_game(game_data):
    players_list = []
    game_id = game_data["id"]

    # Skip if game_data is missing 'rosters'
    if "rosters" not in game_data:
        print(f"⚠️ Skipping game {game_id}: no rosters available")
        return []

    # Fix date here (correct place)
    raw_date = game_data["date"]  # e.g., "2025-10-29T20:00:00Z"
    game_date_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

    # Convert to EST
    eastern = pytz.timezone("US/Eastern")
    game_date_local = game_date_utc.astimezone(eastern).date()

    for side in ["home", "away"]:
        opponent_side = "away" if side == "home" else "home"
        team_name = game_data["teams"][side]["name"]
        opponent_name = game_data["teams"][opponent_side]["name"]

        for player in game_data["rosters"][side]:
            if not player.get("played"):
                continue

            stats = player.get("stats", {})

            # Define these FIRST
            hits = stats.get("batting_hits")
            runs = stats.get("batting_runs")
            rbi = stats.get("batting_rbi")

            # Now compute HRR
            hrr = (hits or 0) + (runs or 0) + (rbi or 0) if hits is not None else None

            # Batter stats
            batter_stats = {
                "singles": None,
                "doubles": stats.get("batting_doubles"),
                "triples": stats.get("batting_triples"),
                "home_runs": stats.get("batting_home_runs"),
                "plate_appearances": stats.get("batting_plate_appearances"),
                "hits": hits,
                "walks": stats.get("batting_base_on_balls"),
                "strikeouts": stats.get("batting_strikeouts"),
                "stolen_bases": stats.get("batting_stolen_bases"),
                "runs": runs,
                "rbi": rbi,
                "hrr": hrr,
                "total_bases": stats.get("batting_total_bases"),
            }

            # Compute singles
            if hits is not None:
                singles = hits - (batter_stats["doubles"] or 0) - (batter_stats["triples"] or 0) - (batter_stats["home_runs"] or 0)
                batter_stats["singles"] = singles

            outs = stats.get("pitching_outs")
            strikeouts_pitching = stats.get("pitching_strikeouts")

            k_per_out = (strikeouts_pitching / outs) if outs else None
            k_per_9 = (strikeouts_pitching * 9 / (outs / 3)) if outs else None

            # Pitcher Stats
            pitcher_stats = {
                "innings_pitched": stats.get("pitching_innings_pitched"),
                "outs": outs,
                "strikeouts_pitching": strikeouts_pitching,
                "walks_pitching": stats.get("pitching_base_on_balls"),
                "hits_allowed": stats.get("pitching_hits"),
                "home_runs_allowed": stats.get("pitching_home_runs"),
                "earned_runs": stats.get("pitching_earned_runs"),
                "whip": stats.get("pitching_whip"),
                "pitches": stats.get("pitching_pitches_thrown"),
                "runs_allowed": stats.get("pitching_runs"),
                "k_per_out": k_per_out,
                "k_per_9": k_per_9,
            }

            row = {
                "date": game_date_local,
                "game_id": game_id,
                "player": player["name"],
                "player_id": player["id"],
                "position": player["position"],
                "is_pitcher": player["position"] == "P",
                "is_starter": player.get("started"),
                "team": team_name,
                "opponent": opponent_name,
                "side": side,
                **batter_stats,
                **pitcher_stats
            }

            players_list.append(row)

    return players_list

# -------------------------
# LOAD EXISTING GAME IDs
# -------------------------
existing_game_ids = set()
if os.path.exists(OUTPUT_CSV):
    try:
        existing = pd.read_csv(OUTPUT_CSV, usecols=["game_id"])
        existing_game_ids = set(existing["game_id"].dropna().unique())
        print(f"Loaded {len(existing_game_ids)} existing game IDs from CSV.")
    except Exception as e:
        print(f"⚠️ Could not load existing game IDs: {e}")

print(f"Fetching from {START_DATE} to {END_DATE}...")

# -------------------------
# MAIN SCRIPT
# -------------------------
all_players = []

for single_date in daterange(START_DATE, END_DATE):
    date_str = single_date.strftime("%Y-%m-%d")
    print(f"Fetching games for {date_str}...")
    
    games = fetch_daily_games(date_str)

    # total_requests increment happens inside fetch_daily_games
    print(f"{date_str} → {len(games)} games")

    # Skip the day if no games
    if not games:
        print(f"No games found for {date_str}, skipping day.")
        continue

    for game in games:
        game_id = game.get("id")

        # Skip games already in the CSV
        if game_id in existing_game_ids:
            print(f"⏭️ Skipping game {game_id}: already in CSV.")
            continue

        game_url = f"{BASE_URL}/boxscores/game/{game_id}.json?key={API_KEY}"

        game_data = None  # initialize cleanly

        while True:
            rate_limit()
            game_resp = requests.get(game_url)
            total_requests += 1

            if game_resp.status_code == 200:
                game_data = game_resp.json()
                break

            elif game_resp.status_code == 429:
                print(f"⏳ Rate limited on game {game_id}, sleeping 60s...")
                time.sleep(60)

            else:
                print(f"❌ Error fetching game {game_id}: {game_resp.status_code}")
                break

        # Skip if we never got valid data or rosters are missing
        rosters = game_data.get("rosters", {})
        if not rosters.get("home") or not rosters.get("away"):
            print(f"⚠️ Skipping game {game_id}: rosters not ready")
            continue

        players_list = extract_players_from_game(game_data)
        all_players.extend(players_list)

        # Checkpoint save every 200 requests
        if total_requests % 200 == 0:
            print(f"Checkpoint reached ({total_requests} requests). Saving progress...")
            append_to_csv(OUTPUT_CSV, all_players)
            all_players = []  # clear memory

# Save all to CSV
if all_players:
    print("Final save...")
    append_to_csv(OUTPUT_CSV, all_players)
    print(f"Saved {len(all_players)} player rows to {OUTPUT_CSV}")
else:
    print("No player data collected.")