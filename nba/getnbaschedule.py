import requests
import json
from datetime import datetime
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------
API_KEY = "sbfz4jp8sasou2ux1wrov7w"

# Season endpoint returns ALL games for the season (or filtered by type).
# Much better than the daily endpoint for B2B detection, which needs
# yesterday + today + tomorrow — impossible with a single-day fetch.
BASE_URL = "https://api.sportsblaze.com/nba/v1/schedule/season/{season}.json"

OUTPUT_PATH = Path("nba/data/nbaschedule.json")


def get_current_season():
    """
    SportsBlaze uses the year the season ENDS as the season key.
    e.g. the 2024-25 season = 2025.

    The NBA Finals end in June and the new season tips off in October, so:
      January–June   → season key = current year       (e.g. May 2026 → 2025... 
                        wait, 2025-26 tips Oct 2025 so May 2026 IS season 2026)
    
    Correction: the 2025-26 season started Oct 2025 and ends June 2026,
    so its key IS 2026. The Playoffs in May 2026 are the 2025-26 playoffs = key 2026.
    BUT the API returned 404 for 2026, which means SportsBlaze still keys it as 2025.
    
    Safe approach: try current year first, fall back to current year - 1.
    This function returns a candidate; fetch_schedule handles the fallback.
    """
    now = datetime.now()
    # NBA season key = the year the season ends.
    # Oct–Dec: new season just started, ends next year → year + 1
    # Jan–Jun: season ends this calendar year → current year  
    # Jul–Sep: offseason → upcoming season ends next year → year + 1
    if now.month >= 7:
        return now.year + 1
    else:
        return now.year


def fetch_schedule(season, season_type="Playoffs"):
    """
    Fetch the full season schedule filtered by type.
    Automatically retries with season-1 if the first attempt returns 404,
    since SportsBlaze keys seasons by the year the season STARTS
    (e.g. the 2025-26 season = key 2025), not the year it ends.
    """
    params = {
        "key": API_KEY,
        "type": season_type,
    }
    for candidate in (season, season - 1):
        url = BASE_URL.format(season=candidate)
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 404:
            print(f"  Season key {candidate} returned 404, trying {candidate - 1}...")
            continue
        response.raise_for_status()
        print(f"  Using season key: {candidate}")
        return response.json()
    raise RuntimeError(
        f"Could not find a valid season key near {season}. "
        f"Check your API key and the SportsBlaze docs."
    )


def save_schedule(data, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved schedule → {path}")
    if "games" in data:
        print(f"  {len(data['games'])} games in file")


def main():
    season = get_current_season()

    # -------------------------------------------------------
    # Change season_type here as the NBA calendar progresses:
    #   "Regular Season"      — October through April
    #   "Play-In Tournament"  — mid-April
    #   "Playoffs"            — late April through June
    # -------------------------------------------------------
    season_type = "Playoffs"

    print(f"Fetching NBA {season_type} schedule for {season} season...")
    data = fetch_schedule(season, season_type)
    save_schedule(data)


if __name__ == "__main__":
    main()