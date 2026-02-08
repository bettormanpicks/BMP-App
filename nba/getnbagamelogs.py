import pandas as pd
from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.library.http import NBAStatsHTTP
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import random

print("=== NBA PLAYER GAME LOGS START ===")

# ==================================================
# CONFIG
# ==================================================
OUTPUT_CSV = "data/nbaplayergamelogs.csv"
SEASON = "2025-26"
MAX_ATTEMPTS = 3        # retries per request
TIMEOUT = 180           # seconds

# ==================================================
# RESILIENT SESSION
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
# FETCH FULL-SEASON LEAGUE PLAYER GAME LOG
# ==================================================
dfs = []

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        print(f"[INFO] Requesting full-season league game logs (attempt {attempt})...")
        gamelog = leaguegamelog.LeagueGameLog(
            season=SEASON,
            player_or_team_abbreviation="P",
            season_type_all_star="Regular Season",
            timeout=TIMEOUT
        )
        df = gamelog.get_data_frames()[0]
        dfs.append(df)
        print(f"[INFO] Retrieved {len(df)} player-game rows")
        break
    except Exception as e:
        if attempt < MAX_ATTEMPTS:
            wait = 10 * attempt
            print(f"   ⚠️ Retry {attempt}/{MAX_ATTEMPTS} due to {e}, waiting {wait}s")
            time.sleep(wait)
        else:
            raise RuntimeError(f"NBA API failed after {MAX_ATTEMPTS} attempts: {e}")

if not dfs:
    raise RuntimeError("NBA returned empty league gamelog dataset.")

df = pd.concat(dfs, ignore_index=True)

# ==================================================
# CLEAN + MATCH YOUR OLD STRUCTURE
# ==================================================
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

# Column renaming
df.rename(columns={
    "PLAYER_ID": "player_id",
    "PLAYER_NAME": "player_name",
    "SEASON_ID": "Season"
}, inplace=True)

df["Season"] = SEASON

# --- Convert MIN from "MM:SS" to decimal minutes ---
def convert_min_to_float(min_str):
    if pd.isna(min_str):
        return 0.0
    try:
        minutes, seconds = min_str.split(":")
        return float(minutes) + float(seconds)/60.0
    except:
        return 0.0

df["MIN"] = df["MIN"].apply(convert_min_to_float)

# --- Sort for consistency ---
df = df.sort_values(["player_id", "GAME_DATE"])

# --- Keep only columns your app uses ---
desired_columns = [
    "Season",
    "player_id",
    "player_name",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "GAME_ID",
    "GAME_DATE",
    "MATCHUP",
    "WL",
    "MIN",
    "FGM","FGA","FG3M","FG3A","FTM","FTA",
    "OREB","DREB","REB",
    "AST","STL","BLK","TOV","PF",
    "PTS","PLUS_MINUS"
]
df = df[desired_columns]

# ==================================================
# SAVE
# ==================================================
df.to_csv(OUTPUT_CSV, index=False)
print(f"\n💾 Saved {len(df)} rows → {OUTPUT_CSV}")

# ==================================================
# DATA INTEGRITY CHECK
# ==================================================
if len(df) < 10000:
    raise RuntimeError(f"NBA download incomplete — only {len(df)} rows collected.")

print("=== NBA PLAYER GAME LOGS FINISHED ===")
