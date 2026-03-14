import pandas as pd

logs = pd.read_csv("data/tt_elite_matchlogs.csv", parse_dates=["date"])

player = "Marcin Marchlewski"

matches = logs[
    (logs["player1"] == player) | (logs["player2"] == player)
].sort_values("date")

last30 = matches.tail(30)

print(last30[["date","player1","player2","sets1","sets2","four_plus"]])
print()
print("4+ sets:", last30["four_plus"].sum(), "/ 30")