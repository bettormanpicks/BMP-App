import pandas as pd
import os

INPUT = os.path.join(DATA_DIR, "tennis_opponent_defense.csv")
OUTPUT = os.path.join(DATA_DIR, "tennis_opponent_defense_normalized.csv")

df = pd.read_csv(INPUT)

# --- Split tours ---
atp = df[df["tour"] == "ATP"].copy()
wta = df[df["tour"] == "WTA"].copy()

def normalize(tour_df):

    # Tour averages
    avg_games = tour_df["avg_games_allowed"].mean()
    avg_total = tour_df["avg_total_games"].mean()
    avg_win = tour_df["win_allowed_rate"].mean()

    # Relative to tour
    tour_df["games_allowed_plus"] = tour_df["avg_games_allowed"] / avg_games
    tour_df["total_games_plus"] = tour_df["avg_total_games"] / avg_total
    tour_df["win_allowed_plus"] = tour_df["win_allowed_rate"] / avg_win

    # Scaled index (100 = average)
    tour_df["defense_index"] = 100 - ((tour_df["games_allowed_plus"] - 1) * 100)

    return tour_df

atp_norm = normalize(atp)
wta_norm = normalize(wta)

def add_return_labels(tour_df):

    mean = tour_df["avg_games_allowed"].mean()
    std = tour_df["avg_games_allowed"].std()

    tour_df["z_score"] = (tour_df["avg_games_allowed"] - mean) / std

    def classify(z):
        if z <= -1:
            return "Elite Returner"
        elif z <= -0.3:
            return "Strong Returner"
        elif z < 0.3:
            return "Average Returner"
        elif z < 1:
            return "Weak Returner"
        else:
            return "Poor Returner"

    tour_df["return_tier"] = tour_df["z_score"].apply(classify)

    return tour_df

atp_norm = add_return_labels(atp_norm)
wta_norm = add_return_labels(wta_norm)

final = pd.concat([atp_norm, wta_norm], ignore_index=True)
final.to_csv(OUTPUT, index=False)

print("Normalized defense created.")
