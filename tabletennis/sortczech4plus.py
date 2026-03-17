import pandas as pd

# Load CSV
df = pd.read_csv("data/tt_czech_4plus_predictions.csv", parse_dates=["date"])

# Filter: only keep matches where head-to-head count is at least 10
df_filtered = df[df["h2h_L10_count"] >= 10]

# Sort by R_4plus descending
df_sorted = df_filtered.sort_values(by="R_4plus", ascending=False)

# Display top 30
print(df_sorted.head(30))

# Optional: save to a new CSV
#df_sorted.to_csv("tt_czech_4plus_predictions_sorted_filtered.csv", index=False)