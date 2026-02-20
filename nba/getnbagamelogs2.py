import os
import pandas as pd
from nba_api.stats.endpoints import leaguegamelog
from nba_api.stats.library.http import NBAStatsHTTP
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

print("=== NBA PLAYER GAME LOGS START ===")

# ==================================================
# CONFIG
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # folder of this script
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)  # create data folder if missing

OUTPUT_CSV = os.path.join(DATA_DIR, "nbaplayergamelogs.csv")
SEASON = "2025-26"
TIMEOUT = 180  # seconds

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
# FETCH LEAGUE PLAYER GAME LOGS
# ==================================================
print(f"[INFO] Requesting full-season league game logs...")
gamelog = leaguegamelog.LeagueGameLog(
    season=SEASON,
    player_or_team_abbreviation="P",
    season_type_all_star="Regular Season",
    timeout=TIMEOUT
)
df = gamelog.get_data_frames()[0]

if df.empty:
    raise RuntimeError("NBA returned empty league gamelog dataset.")

print(f"[INFO] Retrieved {len(df)} player-game rows")

# ==================================================
# CLEAN + MATCH YOUR OLD STRUCTURE
# ==================================================
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

df.rename(columns={
    "PLAYER_ID": "player_id",
    "PLAYER_NAME": "player_name",
    "SEASON_ID": "Season"
}, inplace=True)

df["Season"] = SEASON

# Convert MIN from "MM:SS" to decimal
def convert_min_to_float(min_str):
    if pd.isna(min_str):
        return 0.0
    try:
        minutes, seconds = min_str.split(":")
        return float(minutes) + float(seconds)/60.0
    except:
        return 0.0

df["MIN"] = df["MIN"].apply(convert_min_to_float)

df = df.sort_values(["player_id", "GAME_DATE"])

# Keep only columns your app uses
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
print(f"\nSaved {len(df)} rows -> {OUTPUT_CSV}")

if len(df) < 10000:
    raise RuntimeError(f"NBA download incomplete — only {len(df)} rows collected.")

print("=== NBA PLAYER GAME LOGS FINISHED ===")
