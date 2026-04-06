import requests
import time
import json
import csv
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
API_KEY = "sbf0cxa6scw0hrykgk0c4cu"
BASE_URL = "https://api.sportsblaze.com/mlb/v1"
START_DATE = "2025-03-27"  # YYYY-MM-DD
END_DATE = "2025-06-30"    # YYYY-MM-DD
OUTPUT_CSV = "data/2025boxscores.csv"

# -------------------------
# HELPER FUNCTIONS
# -------------------------
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
    url = f"{BASE_URL}/boxscores/daily/{date_str}.json?key={API_KEY}"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Error fetching {date_str}: {resp.status_code}")
        return []
    data = resp.json()
    return data.get("games", [])

def extract_players_from_game(game_data):
    players_list = []
    game_id = game_data["id"]

    # Fix date here (correct place)
    raw_date = game_data["date"]
    game_date = datetime.fromisoformat(raw_date.replace("Z", "")).date()

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
            }

            row = {
                "date": game_date,
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
# MAIN SCRIPT
# -------------------------
all_players = []
request_count = 0

for single_date in daterange(START_DATE, END_DATE):
    date_str = single_date.strftime("%Y-%m-%d")
    print(f"Fetching games for {date_str}...")
    games = fetch_daily_games(date_str)
    request_count += 1

    if not games:
        print(f"No games found for {date_str}")
        continue

    for game in games:
        game_id = game["id"]
        game_url = f"{BASE_URL}/boxscores/game/{game_id}.json?key={API_KEY}"
        game_resp = requests.get(game_url)
        request_count += 1

        if game_resp.status_code != 200:
            print(f"Error fetching game {game_id}: {game_resp.status_code}")
            continue

        game_data = game_resp.json()
        players_list = extract_players_from_game(game_data)
        all_players.extend(players_list)

        # Checkpoint save every 200 requests
        if request_count % 200 == 0:
            print(f"Checkpoint reached ({request_count} requests). Saving progress...")
            append_to_csv(OUTPUT_CSV, all_players)
            all_players = []  # clear memory

        # Respect API limit
        if request_count >= 10:
            print("Reached 10 requests, sleeping 60 seconds...")
            time.sleep(60)
            request_count = 0
        else:
            time.sleep(6)  # small buffer to avoid hitting limit

# Save all to CSV
if all_players:
    print("Final save...")
    append_to_csv(OUTPUT_CSV, all_players)

    print(f"Saved {len(all_players)} player rows to {OUTPUT_CSV}")
else:
    print("No player data collected.")