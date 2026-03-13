import pandas as pd

# Path to your matchlogs CSV
file_path = "data/tt_czech_matchlogs.csv"

# Load the CSV
matchlogs = pd.read_csv(file_path)

# Create the four_plus column
matchlogs["four_plus"] = (matchlogs["sets1"] + matchlogs["sets2"] >= 4).astype(int)

# Save the updated CSV
matchlogs.to_csv(file_path, index=False)

print("four_plus column successfully added to tt_czech_matchlogs.csv")