# nhl/data/CSVclean.py
import pandas as pd
from pathlib import Path

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
CSV_FILE = Path(__file__).parent / "nhlteamgames.csv"

# -------------------------------------------------
# LOAD CSV
# -------------------------------------------------
df = pd.read_csv(CSV_FILE)

# -------------------------------------------------
# CLEAN GAME_DATE
# -------------------------------------------------
# If GAME_DATE has a space (YYYY-MM-DD HH:MM:SS), keep only the YYYY-MM-DD part
df["GAME_DATE"] = df["GAME_DATE"].astype(str).str.strip().str.split(" ").str[0]

# -------------------------------------------------
# SAVE CLEAN CSV
# -------------------------------------------------
df.to_csv(CSV_FILE, index=False)
print(f"[DONE] Stripped HH:MM:SS from GAME_DATE for {len(df)} rows in:\n{CSV_FILE}")
