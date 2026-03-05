import pandas as pd
import os

ATP_FILE = os.path.join(DATA_DIR, "atp_player_gamelogs.csv")
WTA_FILE = os.path.join(DATA_DIR, "wta_player_gamelogs.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "tennis_opponent_defense.csv")

def build_defense(df, tour):

    defense = (
        df.groupby(["opponent", "surface"])
        .agg(
            matches_faced=("opponent", "count"),
            avg_games_allowed=("games_won", "mean"),
            avg_total_games=("total_games", "mean"),
            win_allowed_rate=("match_win", "mean"),
            avg_game_diff_allowed=("game_diff", lambda x: (-x).mean())
        )
        .reset_index()
    )

    defense["tour"] = tour
    defense = defense.rename(columns={"opponent": "player_id"})
    return defense

atp = pd.read_csv(ATP_FILE)
wta = pd.read_csv(WTA_FILE)

atp_def = build_defense(atp, "ATP")
wta_def = build_defense(wta, "WTA")

final = pd.concat([atp_def, wta_def], ignore_index=True)

final = final[final["matches_faced"] >= 1]

final.to_csv(OUTPUT_FILE, index=False)

print("Tennis opponent defense built.")
