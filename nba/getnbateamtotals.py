import pandas as pd

# Columns we care about for defensive impact
STATS = [
    "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
]

# Load raw game logs
df = pd.read_csv("data/nbaplayergamelogs.csv")
# LeagueGameLog uses GAME_ID, old script expects Game_ID
df["Game_ID"] = df["GAME_ID"]
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Extract TEAM from MATCHUP
# Extract opponent based on the team on the row
def parse_matchup(row):
    matchup = row["MATCHUP"]
    team = row["TEAM_ABBREVIATION"]

    if "@" in matchup:
        away, home = matchup.split(" @ ")
        opp = home if team == away else away
    else:  # "vs."
        home, away = matchup.split(" vs. ")
        opp = away if team == home else home

    return team, opp

df[["TEAM", "OPP_TEAM"]] = df.apply(lambda row: pd.Series(parse_matchup(row)), axis=1)

# Aggregate player stats to team totals per game
team_totals = df.groupby(["Game_ID", "GAME_DATE", "TEAM", "OPP_TEAM"])[STATS].sum().reset_index()

# Optional: save to CSV for quick reuse
team_totals.to_csv("data/nbateamgametotals.csv", index=False)
