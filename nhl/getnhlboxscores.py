from pathlib import Path
import pandas as pd

# ==================================================
# PATH SETUP (GitHub + Windows safe)
# ==================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

INPUT_CSV = DATA_DIR / "nhlplayergamelogs.csv"
OUTPUT_CSV = DATA_DIR / "nhlteamgames.csv"

# ==================================================
# LOAD PLAYER GAME LOGS
# ==================================================
print("Loading NHL player game logs...")
df = pd.read_csv(INPUT_CSV)

# Only include real games (exclude scratches / DNPs)
df = df[df["toi_minutes"] > 0].copy()

# Ensure date is datetime
df["game_date"] = pd.to_datetime(df["game_date"])

# ==================================================
# BUILD TEAM GAME TOTALS (PER GAME, PER TEAM)
# ==================================================
# Sum all player stats to create team boxscore
df_team_game = (
    df.groupby(["game_id", "team", "opponent"])
      .agg({
          "goals": "sum",
          "shots": "sum"
      })
      .reset_index()
)

# Attach game date
game_dates = df.groupby("game_id")["game_date"].first().reset_index()
df_team_game = df_team_game.merge(game_dates, on="game_id", how="left")

# ==================================================
# CREATE GOALS ALLOWED / SHOTS ALLOWED
# (self-join to opponent row)
# ==================================================
opp = df_team_game.rename(columns={
    "team": "opponent",
    "opponent": "team",
    "goals": "GA",
    "shots": "SA"
})[["game_id", "team", "GA", "SA"]]

df_team_game = df_team_game.merge(opp, on=["game_id", "team"], how="left")

# ==================================================
# FINAL COLUMN FORMAT
# ==================================================
df_team_game = df_team_game.rename(columns={
    "game_id": "GAME_ID",
    "game_date": "GAME_DATE",
    "team": "TEAM",
    "opponent": "OPP_TEAM",
    "goals": "GF",
    "shots": "SF"
})

df_team_game = df_team_game[
    ["GAME_ID", "GAME_DATE", "TEAM", "OPP_TEAM", "GF", "GA", "SF", "SA"]
]

# Sort chronologically
df_team_game = df_team_game.sort_values(["GAME_DATE", "GAME_ID", "TEAM"])

# ==================================================
# PREVENT DUPLICATES (Incremental Updating)
# ==================================================
if OUTPUT_CSV.exists():
    print("Existing team game file found — appending new games only...")
    existing = pd.read_csv(OUTPUT_CSV)

    existing_keys = set(
        zip(existing["GAME_ID"].astype(str), existing["TEAM"])
    )

    df_team_game["key"] = list(zip(df_team_game["GAME_ID"].astype(str), df_team_game["TEAM"]))
    df_team_game = df_team_game[~df_team_game["key"].isin(existing_keys)]
    df_team_game = df_team_game.drop(columns="key")

    df_team_game = pd.concat([existing, df_team_game], ignore_index=True)

# ==================================================
# SAVE
# ==================================================
df_team_game.to_csv(OUTPUT_CSV, index=False)

print(f"[DONE] Saved {len(df_team_game)} team game rows -> {OUTPUT_CSV}")
