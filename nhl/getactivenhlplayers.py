import requests
import csv

def get_active_players_with_ids(filename="nhlplayers.csv"):
    """Fetch all active NHL players with team abbreviations, positions, and player IDs."""
    teams_url = "https://api-web.nhle.com/v1/standings/now"
    resp = requests.get(teams_url, timeout=20)
    resp.raise_for_status()
    teams = resp.json()["standings"]

    players = []

    for team in teams:
        team_abbrev = team["teamAbbrev"]["default"]
        roster_url = f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current"
        try:
            r = requests.get(roster_url, timeout=20)
            r.raise_for_status()
            data = r.json()

            # Combine all player groups
            groups = []
            groups.extend(data.get("forwards", []))
            groups.extend(data.get("defensemen", []))
            groups.extend(data.get("goalies", []))

            for p in groups:
                player_id = p.get("id")
                first = p["firstName"]["default"]
                last = p["lastName"]["default"]
                position = p.get("positionCode") or p.get("position", {}).get("code", "")
                full_name = f"{first} {last}"
                players.append({
                    "player_id": player_id,
                    "player_name": full_name,
                    "team": team_abbrev,
                    "position": position
                })

        except Exception as e:
            print("[WARN] Failed to fetch roster for {}: {}".format(team_abbrev, e))

    # Remove duplicates and sort
    unique_players = {p["player_id"]: p for p in players}.values()
    sorted_players = sorted(unique_players, key=lambda x: (x["team"], x["player_name"]))

    # Write to CSV
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["player_id", "player_name", "team", "position"])
        writer.writeheader()
        writer.writerows(sorted_players)

    print("[DONE] Saved {} active players to {}".format(len(sorted_players), filename))


if __name__ == "__main__":
    print("[INFO] Fetching active NHL players with IDs...")
    get_active_players_with_ids()
