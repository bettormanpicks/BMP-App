import pandas as pd

FILE = "data/tt_elite_matchlogs.csv"

df = pd.read_csv(FILE)

# Parse as UTC to standardize everything
df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

# Drop bad rows
df = df.dropna(subset=["date"])

# Remove timezone awareness (store clean naive UTC)
df["date"] = df["date"].dt.tz_convert(None)

# Sort newest first
df = df.sort_values("date", ascending=False)

# Save in consistent ISO format
df["date"] = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

df.to_csv(FILE, index=False)

print("Matchlogs fully normalized and sorted.")