import pandas as pd
import requests
import time
from datetime import datetime

# -------------------------
# CONFIG
# -------------------------
API_KEY = "sbfz4jp8sasou2ux1wrov7w"
BASE_URL = "https://api.sportsblaze.com/mlb/v1"
OUTPUT_CSV = "data/2026_mlb_schedule.csv"

TODAY = datetime.utcnow().strftime("%Y-%m-%d")

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
# FETCH TODAY'S SCHEDULE
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

        raw_date = game.get("date")
        game_datetime = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

        home_team = game["teams"]["home"]["name"]
        away_team = game["teams"]["away"]["name"]

        home_pitcher = None
        away_pitcher = None

        if "starters" in game:
            home_pitcher = game["starters"].get("home", {}).get("name")
            away_pitcher = game["starters"].get("away", {}).get("name")

        status = game.get("status")

        rows.append({
            "date": game_datetime,
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_pitcher": home_pitcher,
            "away_pitcher": away_pitcher,
            "status": status
        })

    return rows

# -------------------------
# SAVE CSV (overwrites each run)
# -------------------------
def save_csv(file_path, data):
    if not data:
        print("No games found, CSV not updated.")
        return

    df = pd.DataFrame(data)
    df["date"] = df["date"].apply(lambda x: x.isoformat())
    df.to_csv(file_path, index=False, encoding="utf-8")

# -------------------------
# MAIN
# -------------------------
print(f"Fetching schedule for {TODAY}...")

games = fetch_schedule(TODAY)

if not games:
    print("No games found.")
else:
    rows = extract_schedule_games(games)
    save_csv(OUTPUT_CSV, rows)
    print(f"Saved {len(rows)} games to {OUTPUT_CSV}")