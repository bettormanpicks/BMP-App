import requests

LIVE_FEED_URL = "https://app.atptour.com/api/v2/gateway/livematches/website?scoringTournamentLevel=tour"
DAILY_SCHEDULE_URL = "https://app.atptour.com/api/v2/gateway/dailyschedule/website?scoringTournamentLevel=tour"


def fetch_data():
    """
    Fetch ATP live matches first. If none are live, fallback to the daily schedule feed.
    Returns a dict with 'LiveMatchesTournamentsOrdered'.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    print("Requesting official ATP live match feed...")
    response = requests.get(LIVE_FEED_URL, headers=headers, timeout=10)

    if response.status_code != 200:
        raise Exception(f"Failed to reach ATP live feed ({response.status_code})")

    try:
        data = response.json()
    except Exception as e:
        raise Exception("Failed to parse JSON from ATP live feed") from e

    tournaments = data.get("Data", {}).get("LiveMatchesTournamentsOrdered", [])
    if tournaments:
        print("ATP live feed captured successfully.")
        return {"LiveMatchesTournamentsOrdered": tournaments}

    # No live matches — try daily schedule feed
    print("No live tournaments found — fetching daily schedule feed...")
    response = requests.get(DAILY_SCHEDULE_URL, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to reach ATP daily schedule feed ({response.status_code})")

    try:
        schedule_data = response.json()
    except Exception as e:
        raise Exception("Failed to parse JSON from ATP daily schedule feed") from e

    tournaments = schedule_data.get("Data", {}).get("LiveMatchesTournamentsOrdered", [])
    if not tournaments:
        print("ATP feed reachable — but no live matches currently scheduled.")
        return {"LiveMatchesTournamentsOrdered": []}

    print("Daily schedule feed captured successfully.")
    return {"LiveMatchesTournamentsOrdered": tournaments}
