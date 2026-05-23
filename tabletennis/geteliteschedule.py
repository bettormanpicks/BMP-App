import time
import csv
import os
import json
from urllib.parse import quote
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, UTC

# -------------------------
# Configuration
# -------------------------
LEAGUE_URL = "https://scores24.live/en/table-tennis/l-tt-elite-series-1"
CHROME_PROFILE_PATH = r"C:\selenium_profiles\scores24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_elite_schedule.csv")

# -------------------------
# Helpers
# -------------------------
def normalize_name(name):
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return name.strip()

# -------------------------
# Main Scraper
# -------------------------
def scrape_schedule():
    print("Launching browser...")

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # ✅ Critical: Enable performance logging to sniff headers
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=options, version_main=147)

    driver.get(LEAGUE_URL)
    print("Solve Cloudflare if needed...")
    time.sleep(20)

    # Force the site to make a request by scrolling down AND up
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

    import re

    # ✅ Helper to grab the rotating token and timestamp
    def get_live_session(driver):
        """
        Extract API token and timestamp using two approaches:
        1. Performance logs (captures token from live network requests)
        2. Page source regex (token is embedded in __REACT_QUERY_STATE__)
        """
        # --- Approach 1: Performance logs ---
        try:
            logs = driver.get_log("performance")
            for log in reversed(logs):
                try:
                    msg = json.loads(log["message"])["message"]
                    if msg.get("method") == "Network.requestWillBeSent":
                        headers = msg.get("params", {}).get("request", {}).get("headers", {})
                        token = headers.get("x-api-token") or headers.get("X-Api-Token")
                        timestamp = headers.get("x-api-timestamp") or headers.get("X-Api-Timestamp")
                        if token:
                            return {"token": token, "timestamp": timestamp}
                except Exception:
                    continue
        except Exception:
            pass

        # --- Approach 2: Page source regex ---
        try:
            source = driver.page_source
            token_match = re.search(r'"x-api-token"\s*:\s*"([a-z0-9]+)"', source)
            ts_match = re.search(r'"x-api-timestamp"\s*:\s*"([0-9]+)"', source)
            if token_match:
                token = token_match.group(1)
                timestamp = ts_match.group(1) if ts_match else str(int(time.time()))
                print(f"✅ Extracted token from page source: {token}")
                return {"token": token, "timestamp": timestamp}
        except Exception:
            pass

        return None

    session = get_live_session(driver)

    if session:
        print(f"✅ Extracted schedule session: {session['token']}")
    else:
        print("⚠️ Session not found, using fallback token.")
        session = {"token": "h57bsdl", "timestamp": str(int(time.time()))}

    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/tt-elite-series-1/matches"
    cursor = None
    buffer = []
    start_date_encoded = quote(datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"))

    while True:
        # Refresh session each loop to ensure we don't time out
        new_session = get_live_session(driver)
        if new_session:
            session = new_session

        query = f"{base_url}?lang=en&first=50&status=not_started&audience=us&date_between[]={start_date_encoded}&date_between[]=&with_markets=false&with_statistics=false"
        if cursor:
            query += f"&after={quote(cursor)}"

        print("Fetching:", query)

        # ✅ Updated Fetch with credentials and dynamic headers
        data = driver.execute_script("""
            return fetch(arguments[0], {
                headers: {
                    "accept": "*/*",
                    "x-api-timestamp": String(arguments[1]),
                    "x-api-token": arguments[2],
                    "x-bot-identifier": "client",
                    "x-country": "us",
                    "referer": "https://scores24.live/en/table-tennis/l-tt-elite-series-1"
                },
                credentials: "include"
            })
            .then(r => r.json())
            .catch(e => null)
        """, query, session['timestamp'], session['token'])

        if not data or "data" not in data:
            print("❌ Failed to fetch data or session expired.")
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

        time.sleep(1)

    driver.quit()

    if buffer:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        # Using pandas to overwrite with fresh upcoming data
        df = pd.DataFrame(buffer)
        df.sort_values("match_date", ascending=True, inplace=True)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"✅ Schedule scraping complete. Saved {len(buffer)} matches.")
    else:
        print("No matches found to save.")

# -------------------------
if __name__ == "__main__":
    scrape_schedule()