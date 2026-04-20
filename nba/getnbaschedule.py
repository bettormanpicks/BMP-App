import requests
import json
from datetime import datetime
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------
API_KEY = "sbfgsoclqrtd9vpifqmxcyz"

BASE_URL = "https://api.sportsblaze.com/nba/v1/schedule/daily/{date}.json?key={key}"

OUTPUT_PATH = Path("data/nbaschedule.json")


def get_today_str():
    # Use local date (consistent with your app logic)
    return datetime.now().strftime("%Y-%m-%d")


def fetch_schedule(date_str):
    url = BASE_URL.format(date=date_str, key=API_KEY)

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def save_schedule(data, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Saved schedule → {path}")


def main():
    date_str = get_today_str()

    print(f"Fetching NBA schedule for {date_str}...")

    data = fetch_schedule(date_str)

    save_schedule(data)


if __name__ == "__main__":
    main()