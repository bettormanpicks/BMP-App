import pandas as pd
from nba_api.stats.endpoints import playergamelog
from time import sleep

print("=== NBA PLAYER GAME LOGS START ===")

# ==================================================
# CONFIG
# ==================================================
PLAYERS_FILE = "data/nbaplayers.txt"
OUTPUT_CSV = "data/nbaplayergamelogs.csv"
SEASON = "2025-26"
SLEEP_BETWEEN_PLAYERS = 0.6   # conservative but fast

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

for i, p in enumerate(players, start=1):
    name = p["player_name"]
    pid = p["player_id"]

    try:
        logs = playergamelog.PlayerGameLog(
            player_id=pid,
            season=SEASON
        )

        df = logs.get_data_frames()[0]

        if df.empty:
            print(f"   ℹ️ {name}: no games")
            continue

        df["player_name"] = name
        df["player_id"] = pid
        df["Season"] = SEASON

        rows.append(df)
        print(f"   ✅ {name}: {len(df)} games")

        sleep(SLEEP_BETWEEN_PLAYERS)

    except Exception as e:
        print(f"   ❌ {name}: {e}")

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
