import os
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # folder of this script
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PLAYER_CSV = os.path.join(DATA_DIR, "nbaplayergamelogs.csv")
TEAM_CSV = os.path.join(DATA_DIR, "nbateamgametotals.csv")

STATS = [
    "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
]

# ==================================================
# LOAD PLAYER GAME LOGS
# ==================================================
df = pd.read_csv(PLAYER_CSV)
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Extract TEAM from MATCHUP
def parse_matchup(row):
    parts = row.split()
    if "@" in parts:
        return parts[0], parts[2]  # TEAM, OPP
    else:  # "SAC vs. DET"
        return parts[0], parts[2]

df[["TEAM", "OPP_TEAM"]] = df["MATCHUP"].apply(lambda x: pd.Series(parse_matchup(x)))

# ==================================================
# AGGREGATE TO TEAM TOTALS
# ==================================================
team_totals = df.groupby(["GAME_ID", "GAME_DATE", "TEAM", "OPP_TEAM"])[STATS].sum().reset_index()

# ==================================================
# SAVE
# ==================================================
team_totals.to_csv(TEAM_CSV, index=False)
print(f"💾 Saved {len(team_totals)} rows → {TEAM_CSV}")
