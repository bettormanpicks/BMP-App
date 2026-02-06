from nba_api.stats.endpoints import commonallplayers, commonplayerinfo
import pandas as pd
import time

print("[INFO] Fetching active NBA players...")
players_df = commonallplayers.CommonAllPlayers(
    is_only_current_season=1
).get_data_frames()[0]

active_players = players_df[players_df["ROSTERSTATUS"] == 1][
    ["DISPLAY_FIRST_LAST", "PERSON_ID"]
]

rows = []

for _, row in active_players.iterrows():
    player_name = row["DISPLAY_FIRST_LAST"]
    player_id = row["PERSON_ID"]

    try:
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        info_df = info.get_data_frames()[0]

        position = info_df.loc[0, "POSITION"]

    except Exception as e:
        print(f"[WARN] Failed for {player_name}: {e}")
        position = None

    rows.append({
        "Player": player_name,
        "player_id": player_id,
        "Position": position
    })

    time.sleep(0.6)  # IMPORTANT: NBA API rate limit safety

players_out = pd.DataFrame(rows)

output_file = "data/nbaplayerspositions.csv"
players_out.to_csv(output_file, index=False, encoding="utf-8")

print(f"[INFO] Wrote {len(players_out)} players to {output_file}")
