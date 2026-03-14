import pandas as pd

df = pd.read_csv("data/tt_czech_features_weighted.csv")

print((df["match_balance_L10"] == 0).sum())
print(df.sort_values("match_balance_L10").head(10))
print()
print(df.sort_values("match_balance_L10").tail(10))