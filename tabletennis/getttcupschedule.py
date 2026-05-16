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
LEAGUE_URL = "https://scores24.live/en/table-tennis/l-international-tt-cup"
CHROME_PROFILE_PATH = r"C:\selenium_profiles\scores24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_cup_schedule.csv")

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
    print("Ensuring clean environment...")
    # Force kill any lingering or background zombie processes
    os.system("taskkill /F /IM chrome.exe /T >nul 2>&1")
    os.system("taskkill /F /IM chromedriver.exe /T >nul 2>&1")
    time.sleep(3) # Give the OS a brief moment to clear the profile file-locks

    print("Launching browser...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # --- FIX 1: FILTER DOWN PERFORMANCE LOGGING ENTRY SIZES ---
    # This prevents the log buffer from filling up and dropping requests
    logging_prefs = {
        "performance": "ALL"
    }
    options.set_capability("goog:loggingPrefs", logging_prefs)
    
    # Restrict the performance logging categories strictly to Network
    perf_logging_prefs = {
        "enableNetwork": True,
        "enablePage": False,
    }
    options.set_capability("goog:chromeOptions", {"perfLoggingPrefs": perf_logging_prefs})

    driver = uc.Chrome(options=options, version_main=147)

    driver.get(LEAGUE_URL)
    print("Solve Cloudflare if needed (Waiting 20s)...")
    time.sleep(20)

    # ✅ Helper to grab the rotating token and timestamp (Standardized Version)
    def get_live_session(driver, current_logs):
        for log in reversed(current_logs):
            try:
                msg = json.loads(log["message"])["message"]
                if "request" in msg.get("params", {}):
                    headers = msg["params"]["request"].get("headers", {})
                    # Case-insensitive mapping
                    headers_lower = {k.lower(): v for k, v in headers.items()}
                    
                    token = headers_lower.get("x-api-token")
                    timestamp = headers_lower.get("x-api-timestamp")
                    
                    if token and len(token) == 6:
                        return {"token": token, "timestamp": timestamp}
            except:
                continue
        return None

    # ✅ Robust Extraction Loop
    print("Searching for live session token...")
    session = None
    all_captured_logs = []

    for attempt in range(15):
        # Trigger network activity with varying scroll distances
        scroll_amount = 400 + (attempt * 100)
        driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
        
        # Accumulate logs to ensure we don't miss the specific frame
        new_logs = driver.get_log("performance")
        all_captured_logs.extend(new_logs)
        
        session = get_live_session(driver, all_captured_logs)
        if session:
            print(f"✅ Extracted schedule session: {session['token']}")
            break
        
        print(f"  Attempt {attempt + 1}: Token not found yet, retrying...")
        time.sleep(2)

    if not session:
        print("⚠️ Session not found after retries, using fallbacks...")
        # Using your existing fallback token
        session = {"token": "h57bsdl", "timestamp": str(int(time.time()))}

    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/international-tt-cup/matches"
    cursor = None
    buffer = []
    start_date_encoded = quote(datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"))

    while True:
        # Refresh session each loop using the miner approach
        new_logs = driver.get_log("performance")
        fresh_session = get_live_session(driver, new_logs)
        if fresh_session:
            session = fresh_session
            # print(f"🔄 Session updated: {session['token']}") # Optional: uncomment for verbose logs

        query = f"{base_url}?lang=en&first=50&status=not_started&audience=us&date_between[]={start_date_encoded}&date_between[]=&with_markets=false&with_statistics=false"
        if cursor:
            query += f"&after={quote(cursor)}"

        print("Fetching:", query)

        # ✅ Execute the fetch
        data = driver.execute_script("""
            return fetch(arguments[0], {
                headers: {
                    "accept": "*/*",
                    "x-api-timestamp": String(arguments[1]),
                    "x-api-token": arguments[2],
                    "x-bot-identifier": "client",
                    "x-country": "us",
                    "referer": "https://scores24.live/en/table-tennis/l-international-tt-cup"
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