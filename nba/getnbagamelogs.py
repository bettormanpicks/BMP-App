import pandas as pd
from nba_api.stats.endpoints import playergamelog
from time import sleep
import requests
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from nba_api.stats.library.http import NBAStatsHTTP

print("=== NBA PLAYER GAME LOGS START ===")

# ==================================================
# CONFIG
# ==================================================
PLAYERS_FILE = "data/nbaplayers.txt"
OUTPUT_CSV = "data/nbaplayergamelogs.csv"
SEASON = "2025-26"
SLEEP_BETWEEN_PLAYERS = 0.6   # conservative but fast

# ==================================================
# RESILIENT SESSION (critical for GitHub Actions)
# ==================================================
session = requests.Session()

session.headers.update({
    "Host": "stats.nba.com",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br"
})

retries = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
)

adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)

NBAStatsHTTP._session = session

# ==================================================
# LOAD PLAYERS
# ==================================================
players = []
with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        name, pid = line.strip().split(",")
        players.append({"player_name": name.strip(), "player_id": pid.strip()})

print(f"[INFO] Loaded {len(players)} players")

# ==================================================
# FETCH ALL GAME LOGS
# ==================================================
rows = []
failed_players = 0

for i, p in enumerate(players, start=1):
    name = p["player_name"]
    pid = p["player_id"]

    attempts = 0
    success = False

    while attempts < 3 and not success:
        try:
            logs = playergamelog.PlayerGameLog(
                player_id=pid,
                season=SEASON,
                timeout=60
            )

            df = logs.get_data_frames()[0]

            if df.empty:
                print(f"   ℹ️ {name}: no games")
                success = True
                break

            df["player_name"] = name
            df["player_id"] = pid
            df["Season"] = SEASON

            rows.append(df)
            print(f"   ✅ {name}: {len(df)} games")

            sleep(SLEEP_BETWEEN_PLAYERS + random.uniform(0.2, 0.8))
            success = True

        except Exception as e:
            attempts += 1
            print(f"   ⚠️ Retry {attempts}/3 for {name} ({e})")
            sleep(5)

if not success:
    failed_players += 1
    print(f"   ❌ Failed after retries: {name}")

if failed_players > 20:
    raise RuntimeError(
        f"Too many players failed ({failed_players}). Aborting save."
    )

# ==================================================
# SAVE CSV
# ==================================================
if rows:
    final_df = pd.concat(rows, ignore_index=True)
    final_df["GAME_DATE"] = pd.to_datetime(final_df["GAME_DATE"], errors="coerce")

    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n💾 Saved {len(final_df)} rows → {OUTPUT_CSV}")
else:
    print("\n⚠️ No data fetched.")

print("=== NBA PLAYER GAME LOGS FINISHED ===")
