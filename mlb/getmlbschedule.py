import pandas as pd
import requests
import csv
import json
import time
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
API_KEY = "sbf0cxa6scw0hrykgk0c4cu"
BASE_URL = "https://api.sportsblaze.com/mlb/v1"
START_DATE = "2026-04-09"
END_DATE = "2026-04-11"
OUTPUT_CSV = "data/2026_mlb_schedule.csv"

last_request_time = 0
MIN_DELAY = 6.2  # respect 10 req/min

# -------------------------
# RATE LIMIT
# -------------------------
def rate_limit():
    global last_request_time
    now = time.time()
    elapsed = now - last_request_time

    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)

    last_request_time = time.time()

# -------------------------
# DATE LOOP
# -------------------------
def daterange(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

# -------------------------
# FETCH DAILY SCHEDULE
# -------------------------
def fetch_schedule(date_str):
    url = f"{BASE_URL}/schedule/daily/{date_str}.json?key={API_KEY}"

    while True:
        rate_limit()
        resp = requests.get(url)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("games", [])

        elif resp.status_code == 429:
            print(f"⏳ Rate limited on {date_str}, sleeping 60s...")
            time.sleep(60)

        elif resp.status_code == 404:
            print(f"No schedule for {date_str}")
            return []

        else:
            print(f"❌ Error fetching {date_str}: {resp.status_code}")
            return []

# -------------------------
# EXTRACT GAME DATA
# -------------------------
def extract_schedule_games(games):
    rows = []

    for game in games:
        game_id = game.get("id")

        # Convert date (same fix as boxscores)
        raw_date = game.get("date")
        game_datetime = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

        home_team = game["teams"]["home"]["name"]
        away_team = game["teams"]["away"]["name"]

        # Probable pitchers (may not exist)
        home_pitcher = None
        away_pitcher = None

        if "starters" in game:
            home_pitcher = game["starters"].get("home", {}).get("name")
            away_pitcher = game["starters"].get("away", {}).get("name")

        status = game.get("status")

        row = {
            "date": game_datetime,
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_pitcher": home_pitcher,
            "away_pitcher": away_pitcher,
            "status": status
        }

        rows.append(row)

    return rows

# -------------------------
# SAVE CSV
# -------------------------
def save_csv(file_path, data):
    if not data:
        return

    df = pd.DataFrame(data)
    df["date"] = df["date"].apply(lambda x: x.isoformat())  # explicit ISO format
    df.to_csv(file_path, index=False, encoding="utf-8")

# -------------------------
# MAIN
# -------------------------
all_games = []

for single_date in daterange(START_DATE, END_DATE):
    date_str = single_date.strftime("%Y-%m-%d")
    print(f"Fetching schedule for {date_str}...")

    games = fetch_schedule(date_str)

    if not games:
        continue

    rows = extract_schedule_games(games)
    all_games.extend(rows)

# Save
save_csv(OUTPUT_CSV, all_games)
print(f"Saved {len(all_games)} games to {OUTPUT_CSV}")