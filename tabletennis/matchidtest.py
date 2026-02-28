import pandas as pd

df = pd.read_csv("tt_elite_matches.csv")
print(df.shape)
print(df["match_id"].nunique())

print(df["date"].min())
print(df["date"].max())