import time
import csv
import os
from urllib.parse import quote
from datetime import datetime, timedelta, UTC
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait

# -------------------------
# Configuration
# -------------------------
LEAGUE_URL = "https://scores24.live/en/table-tennis/l-setka-cup-0"
CHROME_PROFILE_PATH = r"C:\selenium_profiles\scores24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_setka_matchlogs.csv")
LOOKBACK_DAYS = 2

start_dt = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
START_DATE = start_dt.strftime("%Y-%m-%d %H:%M:%S")

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
                "match_id","match_date","player1","player2","sets",
                "total_points","match_winner","four_plus"
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

    # --- Parse date ---
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.dropna(subset=["match_date"])

    # ✅ NEW: Drop duplicates by match_id
    before = len(df)
    df = df.drop_duplicates(subset=["match_id"], keep="last")
    df.reset_index(drop=True, inplace=True)
    after = len(df)

    print(f"Removed {before - after} duplicate rows")

    # --- Sort ---
    df.sort_values("match_date", ascending=False, inplace=True)

    df.to_csv(OUTPUT_CSV, index=False)

# -------------------------
# Main Scraper
# -------------------------
def scrape_api():
    existing_ids = set()
    if os.path.exists(OUTPUT_CSV):
        try:
            df_existing = pd.read_csv(OUTPUT_CSV)
            existing_ids = set(df_existing["match_id"].astype(str))
            print(f"Loaded {len(existing_ids)} existing match IDs")
        except:
            print("Could not load existing CSV, continuing fresh")

    print("Launching browser...")

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options, version_main=145)
    wait = WebDriverWait(driver, 20)

    driver.get(LEAGUE_URL)
    print("Solve Cloudflare if needed...")
    time.sleep(15)

    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/setka-cup-0/matches"

    cursor = None
    buffer = []

    start_date_encoded = quote(START_DATE)

    while True:
        new_matches_found = False
        end_dt = datetime.now(UTC)
        end_date_encoded = quote(end_dt.strftime("%Y-%m-%d %H:%M:%S"))

        query = f"{base_url}?lang=en&first=50&status=ended&audience=us&date_between[]=&date_between[]={end_date_encoded}&with_markets=false&with_statistics=false"
        if cursor:
            query += f"&after={quote(cursor)}"

        print("Fetching:", query)

        timestamp = int(time.time())

        data = driver.execute_script("""
            return fetch(arguments[0], {
                headers: {
                    "accept": "*/*",
                    "x-api-timestamp": String(arguments[1]),
                    "x-api-token": "h57bsdl",
                    "x-bot-identifier": "client",
                    "x-country": "us",
                    "referer": "https://scores24.live/en/table-tennis"
                }
            })
            .then(r => r.json())
            .catch(e => null)
        """, query, timestamp)

        if not data:
            print("❌ Failed to fetch data")
            break

        edges = data.get("data", {}).get("edges", [])
        if not edges:
            print("No more matches.")
            break

        print(f"Fetched {len(edges)} matches")

        for idx, edge in enumerate(edges):
            try:
                node = edge["node"]

                match_id = node["slug"]

                # ✅ SKIP duplicates HERE
                if match_id in existing_ids:
                    continue

                new_matches_found = True

                existing_ids.add(match_id)

                player1 = normalize_name(node["teams"][0]["name"])
                player2 = normalize_name(node["teams"][1]["name"])
                match_date = pd.to_datetime(node["match_date"]).strftime("%Y-%m-%d %H:%M:%S")
                winner_raw = node.get("winner")
                match_winner = int(winner_raw) if winner_raw else 0

                sets = [s["value"] for s in node.get("result_scores", []) if s["type"] != "FT"]
                total_points = sum(sum(map(int, x.split(":"))) for x in sets if ":" in x)
                four_plus = 1 if len(sets) >= 4 else 0

                buffer.append({
                    "match_id": match_id,
                    "match_date": match_date,
                    "player1": player1,
                    "player2": player2,
                    "sets": "|".join(sets),
                    "total_points": total_points,
                    "match_winner": match_winner,
                    "four_plus": four_plus
                })

            except Exception as e:
                print(f"Parse error at index {idx}: {e}")

        # ✅ Flush every loop (safe + prevents data loss)
        if buffer:
            append_to_csv(buffer)
            print(f"Saved {len(buffer)} matches")
            buffer.clear()

        if not new_matches_found:
            print("No new matches found on this page. Stopping early.")
            break

        cursor = edges[-1].get("cursor")
        if not cursor:
            print("No next cursor. Done.")
            break

        time.sleep(0.5)

    driver.quit()
    resort_csv()
    print("✅ Scraping complete.")

# -------------------------
if __name__ == "__main__":
    scrape_api()