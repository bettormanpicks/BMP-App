import time
import csv
import os
from urllib.parse import quote
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime

# -------------------------
# Configuration
# -------------------------
LEAGUE_URL = "https://scores24.live/en/table-tennis/l-setka-cup-0"
CHROME_PROFILE_PATH = r"C:\selenium_profiles\scores24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_setka_schedule.csv")

# -------------------------
# Helpers
# -------------------------
def normalize_name(name):
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return name.strip()

def append_to_csv(matches):
    if not matches:
        return
    file_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "match_id", "match_date", "player1", "player2", "match_link"
            ],
            quoting=csv.QUOTE_MINIMAL
        )
        if not file_exists:
            writer.writeheader()
        writer.writerows(matches)

def resort_csv():
    if not os.path.exists(OUTPUT_CSV):
        return
    df = pd.read_csv(OUTPUT_CSV)
    if "match_date" not in df.columns:
        print("CSV empty or missing match_date, skipping sort")
        return
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.dropna(subset=["match_date"])
    df.sort_values("match_date", ascending=True, inplace=True)
    df.to_csv(OUTPUT_CSV, index=False)

# -------------------------
# Main Scraper
# -------------------------
def scrape_schedule():
    print("Launching browser...")

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options, version_main=145)

    driver.get(LEAGUE_URL)
    print("Solve Cloudflare if needed...")
    time.sleep(15)

    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/setka-cup-0/matches"

    cursor = None
    buffer = []

    start_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    start_date_encoded = quote(start_date)

    while True:
        query = f"{base_url}?lang=en&first=50&status=not_started&audience=us&date_between[]={start_date_encoded}"
        if cursor:
            query += f"&after={quote(cursor)}"

        print("Fetching:", query)

        data = driver.execute_script("""
            return fetch(arguments[0])
                .then(r => r.json())
                .catch(e => null)
        """, query)

        if not data:
            print("❌ Failed to fetch data")
            break

        edges = data.get("data", {}).get("edges", [])
        if not edges:
            print("No more upcoming matches.")
            break

        print(f"Fetched {len(edges)} matches")

        for edge in edges:
            try:
                node = edge["node"]

                match_id = node["slug"]
                player1 = normalize_name(node["teams"][0]["name"])
                player2 = normalize_name(node["teams"][1]["name"])
                match_date = pd.to_datetime(node["match_date"]).strftime("%Y-%m-%d %H:%M:%S")
                match_link = f"https://scores24.live/en/table-tennis/{match_id}"

                buffer.append({
                    "match_id": match_id,
                    "match_date": match_date,
                    "player1": player1,
                    "player2": player2,
                    "match_link": match_link
                })

            except Exception as e:
                print("Parse error:", e)

        cursor = edges[-1].get("cursor")
        if not cursor:
            break

        time.sleep(0.5)

    driver.quit()

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    pd.DataFrame(buffer).to_csv(OUTPUT_CSV, index=False)
    print("✅ Schedule scraping complete.")

# -------------------------
if __name__ == "__main__":
    scrape_schedule()