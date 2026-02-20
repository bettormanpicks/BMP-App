import os
import pandas as pd
from datetime import datetime, timedelta
from time import sleep
from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.library.http import NBAStatsHTTP
from curl_cffi import requests as curl_requests

print("=== NBA PLAYER GAME LOGS START ===")

# ==================================================
# CONFIG
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(DATA_DIR, "nbaplayergamelogs.csv")
SEASON = "2025-26"
SEASON_START = datetime(2025, 10, 22)  # opening night
SLEEP_TIME = 1.8   # CRITICAL (Cloudflare threshold ~35 req/min)

# ==================================================
# SESSION (keep yours — it's good)
# ==================================================
session = curl_requests.Session(impersonate="chrome120")
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

NBAStatsHTTP()._session = session
NBAStatsHTTP._session = session

# ==================================================
# PRIME CLOUDLFARE SESSION (CRITICAL)
# ==================================================
print("[INFO] Priming NBA session...")

try:
    session.get("https://www.nba.com", timeout=15)
    session.get("https://stats.nba.com", timeout=15)
    print("[INFO] Session primed.")
except Exception as e:
    print("[WARNING] Session priming failed:", e)

# ==================================================
# RESUME LOGIC
# ==================================================
if os.path.exists(OUTPUT_CSV):
    existing = pd.read_csv(OUTPUT_CSV, parse_dates=["GAME_DATE"])
    last_date = existing["GAME_DATE"].max()
    start_date = last_date + timedelta(days=1)
    all_games = [existing]
    print(f"[RESUME] Continuing from {start_date.date()}")
else:
    start_date = SEASON_START
    all_games = []

today = datetime.today()

# ==================================================
# DAILY INGEST LOOP
# ==================================================
current = start_date

while current <= today:
    date_str = current.strftime("%m/%d/%Y")
    print(f"[PULL] {date_str}")

    try:
        gamelog = leaguegamelog.LeagueGameLog(
            date_from_nullable=date_str,
            date_to_nullable=date_str,
            season=SEASON,
            season_type_all_star="Regular Season",
            player_or_team_abbreviation="P",
            timeout=30
        )

        df = gamelog.get_data_frames()[0]

        if not df.empty:

            # normalize columns BEFORE append
            df.rename(columns={
                "PLAYER_ID": "player_id",
                "PLAYER_NAME": "player_name",
                "SEASON_ID": "Season"
            }, inplace=True)

            df["Season"] = SEASON
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

            # convert minutes immediately
            def convert_min_to_float(min_str):
                try:
                    m, s = min_str.split(":")
                    return float(m) + float(s)/60
                except:
                    return 0.0

            df["MIN"] = df["MIN"].apply(convert_min_to_float)

            all_games.append(df)

            print(f"   -> {len(df)} rows")

    except Exception as e:
        print(f"   !! skipped {date_str}: {e}")

    current += timedelta(days=1)
    sleep(SLEEP_TIME)

# ==================================================
# COMBINE
# ==================================================
df = pd.concat(all_games, ignore_index=True)

desired_columns = [
    "Season","player_id","player_name","TEAM_ID","TEAM_ABBREVIATION",
    "GAME_ID","GAME_DATE","MATCHUP","WL","MIN",
    "FGM","FGA","FG3M","FG3A","FTM","FTA",
    "OREB","DREB","REB","AST","STL","BLK","TOV","PF",
    "PTS","PLUS_MINUS"
]

df = df[desired_columns]
df = df.drop_duplicates(subset=["player_id","GAME_ID"], keep="last")
df = df.sort_values(["player_id","GAME_DATE"])
df.to_csv(OUTPUT_CSV, index=False)

print(f"\nSaved {len(df)} rows -> {OUTPUT_CSV}")
print("=== NBA PLAYER GAME LOGS FINISHED ===")