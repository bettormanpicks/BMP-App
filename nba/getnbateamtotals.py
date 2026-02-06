import pandas as pd

# Columns we care about for defensive impact
STATS = [
    "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
]

# Load raw game logs
df = pd.read_csv("data/nbaplayergamelogs.csv")
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Extract TEAM from MATCHUP
# Example: "SAC @ DET" → SAC is TEAM, DET is OPPONENT
def parse_matchup(row):
    parts = row.split()
    if "@" in parts:
        return parts[0], parts[2]  # TEAM, OPP
    else:  # "SAC vs. DET"
        return parts[0], parts[2]

df[["TEAM", "OPP_TEAM"]] = df["MATCHUP"].apply(lambda x: pd.Series(parse_matchup(x)))

# Aggregate player stats to team totals per game
team_totals = df.groupby(["Game_ID", "GAME_DATE", "TEAM", "OPP_TEAM"])[STATS].sum().reset_index()

# Optional: save to CSV for quick reuse
team_totals.to_csv("data/nbateamgametotals.csv", index=False)
