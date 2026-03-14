import pandas as pd

df = pd.read_csv("data/tt_czech_features_weighted.csv")

print(df["match_balance_L10"].describe())