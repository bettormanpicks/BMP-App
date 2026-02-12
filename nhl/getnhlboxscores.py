import pandas as pd

# -----------------------------
# INPUT / OUTPUT
# -----------------------------
INPUT_CSV = r"data\nhlplayergamelogs.csv"
OUTPUT_CSV = r"data\nhlteamgametotals.csv"

# -----------------------------
# Load NHL player games
# -----------------------------
df = pd.read_csv(INPUT_CSV)

# Only include real games (exclude DNPs / scratches / reliefs)
df = df[df["toi_minutes"] > 0].copy()

# -----------------------------
# Aggregate per game
# -----------------------------
# Total goals and shots for each team in each game
df_team_game = df.groupby(["game_id", "team", "opponent"]).agg({
    "goals": "sum",
    "shots": "sum"
}).reset_index()

# -----------------------------
# Compute offensive stats
# -----------------------------
team_offense = df_team_game.groupby("team").agg({
    "goals": "mean",  # GF_A
    "shots": "mean"   # SF_A
}).rename(columns={"goals": "GF_A", "shots": "SF_A"}).round(2)

team_offense["GF_R"] = team_offense["GF_A"].rank(method="min", ascending=False).astype(int)
team_offense["SF_R"] = team_offense["SF_A"].rank(method="min", ascending=False).astype(int)

# -----------------------------
# Compute defensive stats
# -----------------------------
# Defensive totals are goals/shots allowed per team
team_defense = df_team_game.groupby("opponent").agg({
    "goals": "mean",  # GA_A
    "shots": "mean"   # SA_A
}).rename(columns={"goals": "GA_A", "shots": "SA_A"}).round(2)

team_defense["GA_R"] = team_defense["GA_A"].rank(method="min", ascending=True).astype(int)
team_defense["SA_R"] = team_defense["SA_A"].rank(method="min", ascending=True).astype(int)

# -----------------------------
# Combine offense + defense
# -----------------------------
teams = sorted(set(df["team"].unique()))
records = []
for team in teams:
    rec = {"Team": team}
    # Offense
    if team in team_offense.index:
        rec.update(team_offense.loc[team].to_dict())
    else:
        rec.update({"GF_A": None, "GF_R": None, "SF_A": None, "SF_R": None})
    # Defense
    if team in team_defense.index:
        rec.update(team_defense.loc[team].to_dict())
    else:
        rec.update({"GA_A": None, "GA_R": None, "SA_A": None, "SA_R": None})
    records.append(rec)

df_out = pd.DataFrame(records)

# Sort by team name
df_out = df_out.sort_values("Team").reset_index(drop=True)

# -----------------------------
# Save CSV
# -----------------------------
df_out.to_csv(OUTPUT_CSV, index=False)
print(f"[DONE] Team offense + defense stats saved to:\n{OUTPUT_CSV}")