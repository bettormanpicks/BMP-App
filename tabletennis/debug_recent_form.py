import pandas as pd

logs = pd.read_csv("data/tt_czech_matchlogs.csv", parse_dates=["date"])

player = "Lukas Zeman"

matches = logs[
    (logs["player1"] == player) | (logs["player2"] == player)
].sort_values("date")

last10 = matches.tail(10)

print(last10[["date","player1","player2","sets1","sets2","four_plus"]])
print()
print("4+ sets:", last10["four_plus"].sum(), "/ 10")