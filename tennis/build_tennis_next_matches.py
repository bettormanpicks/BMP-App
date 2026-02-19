import pandas as pd
from datetime import datetime
from fetch_atp_live import fetch_data

OUTPUT_FILE = "data/tennis_next_matches.csv"


def clean_name(name):
    if not name:
        return ""
    return name.split("(")[0].strip()


def parse_matches(data):
    matches = []

    events = data.get("Events", [])

    if not events:
        print("No tournaments found in ATP schedule")
        return matches

    today = datetime.today().strftime("%Y-%m-%d")

    for event in events:
        tournament_name = event.get("EventTitle", "Unknown")

        days = event.get("Days", [])

        for day in days:
            courts = day.get("Courts", [])

            for court in courts:
                matches_list = court.get("Matches", [])

                for match in matches_list:
                    players = match.get("Competitors", [])

                    if len(players) != 2:
                        continue

                    p1 = clean_name(players[0].get("PlayerName"))
                    p2 = clean_name(players[1].get("PlayerName"))

                    if not p1 or not p2:
                        continue

                    matches.append({
                        "player": p1,
                        "opponent": p2,
                        "tournament": tournament_name,
                        "date": today
                    })

                    matches.append({
                        "player": p2,
                        "opponent": p1,
                        "tournament": tournament_name,
                        "date": today
                    })

    return matches


def main():
    data = fetch_data()
    matches = parse_matches(data)

    if not matches:
        print("ATP feed reachable — but no live matches currently scheduled.")
        return

    df = pd.DataFrame(matches)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"SUCCESS: saved {len(df)} player matchups to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
