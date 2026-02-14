import requests
import pandas as pd
import time
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
OUTPUT_CSV = "nhl/data/nhlplayergamelogs.csv"

API_BASE = "https://api-web.nhle.com/v1/gamecenter/{}/boxscore"
SLEEP_SECONDS = 0.25
PRINT_EVERY = 25

# -------------------------------------------------
# Load game IDs
# -------------------------------------------------
def fetch_game_ids(start_date, end_date):
    game_ids = set()
    d = start_date

    while d <= end_date:
        date_str = d.strftime("%Y-%m-%d")
        try:
            r = requests.get(
                f"https://api-web.nhle.com/v1/schedule/{date_str}",
                timeout=15
            )
            r.raise_for_status()
            data = r.json()

            for block in data.get("gameWeek", []):
                for g in block.get("games", []):
                    gid = g.get("id")
                    if gid:
                        game_ids.add(gid)

        except Exception as e:
            print(f"[WARN] Schedule fetch failed for {date_str}: {e}")

        d += timedelta(days=1)
        time.sleep(0.2)

    return sorted(game_ids)

SEASON_START = datetime(2025, 10, 7)   # adjust if needed
TODAY = datetime.now()

game_ids = fetch_game_ids(SEASON_START, TODAY)
print(f"Discovered {len(game_ids)} games via schedule API.")

# -------------------------------------------------
# Resume support (skip games already written)
# -------------------------------------------------
processed_games = set()

if os.path.exists(OUTPUT_CSV):
    existing = pd.read_csv(OUTPUT_CSV, usecols=["game_id"])
    processed_games = set(existing["game_id"].unique())
    print(f"Resuming — {len(processed_games)} games already processed.")

game_ids = [
    gid for gid in game_ids
    if gid not in processed_games
]

print(f"{len(game_ids)} new games to process.")

write_header = (
    not os.path.exists(OUTPUT_CSV)
    or os.path.getsize(OUTPUT_CSV) == 0
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def fetch_boxscore(game_id):
    try:
        r = requests.get(API_BASE.format(game_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[WARN] Failed game {game_id}: {e}")
        return None


def toi_to_minutes(toi_str):
    if not toi_str or ":" not in str(toi_str):
        return 0.0
    m, s = toi_str.split(":")
    return round(int(m) + int(s) / 60, 2)


rows = []

# -------------------------------------------------
# Main loop
# -------------------------------------------------
for i, game_id in enumerate(game_ids, 1):

    total_games = len(game_ids)

    if i == 1 or i % PRINT_EVERY == 0:
        print(f"Processing game {i} / {total_games}...")

    data = fetch_boxscore(game_id)
    if not data:
        continue

    game_date = data.get("gameDate", "")[:10]
    season = int(str(game_id)[:4])

    pbs = data.get("playerByGameStats", {})

    for side in ("homeTeam", "awayTeam"):

        team_data = pbs.get(side)
        opp_data = pbs.get("awayTeam" if side == "homeTeam" else "homeTeam")

        if not team_data or not opp_data:
            continue

        team = data.get(side, {}).get("abbrev")
        opponent = data.get("awayTeam" if side == "homeTeam" else "homeTeam", {}).get("abbrev")
        home_away = "H" if side == "homeTeam" else "A"

        # ---------------- SKATERS ----------------
        for group in ("forwards", "defense"):
            for s in team_data.get(group, []):

                rows.append({
                    "game_id": game_id,
                    "game_date": game_date,
                    "season": season,
                    "team": team,
                    "opponent": opponent,
                    "home_away": home_away,

                    "player_id": s.get("playerId"),
                    "player_name": s.get("name", {}).get("default"),
                    "position": s.get("position"),
                    "is_goalie": False,

                    "goals": s.get("goals", 0),
                    "assists": s.get("assists", 0),
                    "points": s.get("points", 0),
                    "shots": s.get("sog", 0),

                    "hits": s.get("hits", 0),
                    "blocks": s.get("blockedShots", 0),
                    "pp_points": s.get("powerPlayGoals", 0),

                    "faceoffs_won": 0,
                    "faceoffs_taken": 0,

                    "shots_against": 0,
                    "goals_against": 0,
                    "saves": 0,
                    "save_pct": 0.0,

                    "toi_minutes": toi_to_minutes(s.get("toi"))
                })

        # ---------------- GOALIES ----------------
        for g in team_data.get("goalies", []):

            shots_against = g.get("shotsAgainst", 0)
            goals_against = g.get("goalsAgainst", 0)
            saves = g.get("saves", 0)
            save_pct = round(saves / shots_against, 3) if shots_against else 0.0

            rows.append({
                "game_id": game_id,
                "game_date": game_date,
                "season": season,
                "team": team,
                "opponent": opponent,
                "home_away": home_away,

                "player_id": g.get("playerId"),
                "player_name": g.get("name", {}).get("default"),
                "position": "G",
                "is_goalie": True,

                "goals": 0,
                "assists": 0,
                "points": 0,
                "shots": 0,

                "hits": 0,
                "blocks": 0,
                "pp_points": 0,

                "faceoffs_won": 0,
                "faceoffs_taken": 0,

                "shots_against": shots_against,
                "goals_against": goals_against,
                "saves": saves,
                "save_pct": save_pct,

                "toi_minutes": toi_to_minutes(g.get("toi"))
            })

    # Flush rows periodically (safer for long runs)
    if len(rows) >= 1000:
        pd.DataFrame(rows).to_csv(
            OUTPUT_CSV,
            mode="a",
            header=write_header,
            index=False
        )
        write_header = False
        rows.clear()

    time.sleep(SLEEP_SECONDS)

print(f"Rows remaining to write: {len(rows)}")

# -------------------------------------------------
# Final flush
# -------------------------------------------------
if rows:
    pd.DataFrame(rows).to_csv(
        OUTPUT_CSV,
        mode="a",
        header=write_header,
        index=False
    )

print(f"\n[SUCCESS] NHL player game data written to:\n{OUTPUT_CSV}")

import os
print("File exists:", os.path.exists(OUTPUT_CSV))
print("Absolute path:", os.path.abspath(OUTPUT_CSV))