import time
import csv
import os
import json
import re
from urllib.parse import quote
from datetime import datetime, timedelta, UTC
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

# -------------------------
# Configuration
# -------------------------
LEAGUE_URL = "https://scores24.live/en/table-tennis/l-tt-elite-series-1"
CHROME_PROFILE_PATH = r"C:\selenium_profiles\scores24"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_elite_matchlogs.csv")
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

    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.dropna(subset=["match_date"])

    before = len(df)
    df = df.drop_duplicates(subset=["match_id"], keep="last")
    df.reset_index(drop=True, inplace=True)
    after = len(df)
    print(f"Removed {before - after} duplicate rows")

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

    driver = uc.Chrome(options=options, version_main=147)
    
    driver.get(LEAGUE_URL)
    print("Solve Cloudflare if needed...")
    time.sleep(20)

    buffer = []
    page_number = 1

    while True:
        print(f"Processing Page {page_number} via live DOM parsing...")
        time.sleep(5) # Give the UI plenty of time to render rows

        # 🎯 THE DOM FIX: Find all match row wrappers natively rendered on screen
        # Scores24 rows typically use an anchor link containing '/match/' or a specific class
        match_elements = driver.find_elements("css selector", "a[href*='/match/']")
        
        if not match_elements:
            # Secondary broader selector fallback if they hide rows inside div containers
            match_elements = driver.find_elements("css selector", "div[class*='match'], div[class*='game_row']")

        if not match_elements:
            print("❌ No visible match rows found on the screen. Stopping.")
            break

        print(f"Found {len(match_elements)} match elements visible on the page.")
        new_matches_found = False

        for el in match_elements:
            try:
                # 1. Extract unique match ID from the elements' attributes or text hashes
                match_url = el.get_attribute("href") or ""
                if "/match/" in match_url:
                    match_id = match_url.split("/match/")[-1].split("?")[0].strip("/")
                else:
                    # Fallback to text signature if no URL available
                    raw_text = el.text.strip()
                    if not raw_text: continue
                    match_id = str(hash(raw_text))

                if not match_id or match_id in existing_ids:
                    continue

                # 2. Extract Text Blocks Natively
                text_lines = [line.strip() for line in el.text.split("\n") if line.strip()]
                if len(text_lines) < 3: 
                    continue # Skip structural elements or empty boxes

                # Process typical row layout: [Time/Status, Player 1, Player 2, Scores...]
                # Adjusting slice indices dynamically based on layout length
                match_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Fallback layout time
                
                player1 = normalize_name(text_lines[1])
                player2 = normalize_name(text_lines[2])
                
                # Extract trailing score blocks (e.g., ["3", "1"] or ["11:9", "11:7"])
                scores_text = text_lines[3:]
                sets = [s for s in scores_text if ":" in s or (s.isdigit() and len(s) == 1)]
                
                # Compute stats
                total_points = sum(sum(map(int, x.split(":"))) for x in sets if ":" in x)
                four_plus = 1 if len(sets) >= 4 else 0
                match_winner = 0 # Default if status unclear

                new_matches_found = True
                existing_ids.add(match_id)

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
                continue

        if buffer:
            append_to_csv(buffer)
            print(f"Saved {len(buffer)} matches from Page {page_number}")
            buffer.clear()

        # 🎯 PAGINATION: Scroll down to automatically trigger their lazy-load engine
        print("Scrolling to load more matches...")
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            page_number += 1
            time.sleep(2)
            
            # Check if we hit the end of the page by monitoring scroll layout heights
            new_height = driver.execute_script("return document.body.scrollHeight")
            # If no new content rendered or no new matches found, wrap it up
            if not new_matches_found and page_number > 3:
                print("No fresh rows detected after scroll loops. Finishing up.")
                break
        except Exception as e:
            print(f"Scroll navigation stopped: {e}")
            break

    driver.quit()
    resort_csv()
    print("✅ Scraping complete.")

# -------------------------
if __name__ == "__main__":
    scrape_api()