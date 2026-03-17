# getczechmatchlogs.py

import csv
import os
import gc
import random
import time
import pandas as pd
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

BASE_URL = "https://betsapi.com/table-tennis/le/22742/Czech-Liga-Pro"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_czech_matchlogs.csv")

# -------------------------
# Helpers
# -------------------------

def normalize_name(name):
    return name.strip()

def load_existing_ids():
    existing_ids = set()
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row["match_id"])
    return existing_ids

def append_to_csv(matches):
    file_exists = os.path.exists(OUTPUT_CSV)

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["match_id","date","player1","player2","sets1","sets2","four_plus"]
        )
        if not file_exists:
            writer.writeheader()

        for m in matches:
            writer.writerow(m)

def resort_csv():
    if not os.path.exists(OUTPUT_CSV):
        return

    df = pd.read_csv(OUTPUT_CSV, dtype={"match_id": str})

    print("Rows before parsing:", len(df))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    print("NaT count after parsing:", df["date"].isna().sum())
    df = df.dropna(subset=["date"])

    print("Rows after dropna:", len(df))

    df.sort_values("date", ascending=False, inplace=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    df.to_csv(OUTPUT_CSV, index=False)

    print("CSV re-sorted by date (newest first).")

# -------------------------
# Selenium Scraper (replaces Playwright)
# -------------------------

def scrape_history(start_page=1, end_page=10, min_delay=4, max_delay=7):

    empty_pages = 0
    EMPTY_PAGE_THRESHOLD = 10  # tweakable

    existing_ids = load_existing_ids()
    print(f"Loaded {len(existing_ids)} existing match IDs.")

    buffer = []
    failed_pages = []

    print("Launching browser...")


    CHROME_PROFILE_PATH = r"C:\selenium_profiles\ttelite"

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    driver = uc.Chrome(options=options, version_main=145)

    # --- Open start page ---
    start_url = BASE_URL if start_page == 1 else f"{BASE_URL}/p.{start_page}"
    print(f"Opening start page: {start_url}")

    driver.get(start_url)

    print("Solve Cloudflare manually if needed...")
    time.sleep(20)

    current_page_num = start_page

    while current_page_num <= end_page:
        print(f"\nScraping page {current_page_num}...")
        new_matches_this_page = 0

        try:
            time.sleep(2)

            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

            if not rows:
                raise Exception("No rows found (possible block or load issue)")

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4:
                    continue

                try:
                    date_attr = cols[0].get_attribute("data-dt")

                    if date_attr:
                        try:
                            parsed = pd.to_datetime(date_attr, utc=True)
                            parsed = parsed.tz_convert(None)
                            date = parsed.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            continue
                    else:
                        continue

                    players = cols[2].find_elements(By.TAG_NAME, "a")
                    if len(players) != 2:
                        continue

                    player1 = normalize_name(players[0].text)
                    player2 = normalize_name(players[1].text)

                    score_link = cols[3].find_element(By.TAG_NAME, "a")
                    score_text = score_link.text.strip()

                    if "-" not in score_text:
                        continue

                    sets1, sets2 = map(int, score_text.split("-"))

                    href = score_link.get_attribute("href")
                    if not href or "/r/" not in href:
                        continue

                    match_id = href.split("/r/")[1].split("/")[0]

                    if match_id not in existing_ids:
                        four_plus = 1 if (sets1 + sets2) >= 4 else 0

                        buffer.append({
                            "match_id": match_id,
                            "date": date,
                            "player1": player1,
                            "player2": player2,
                            "sets1": sets1,
                            "sets2": sets2,
                            "four_plus": four_plus
                        })

                        existing_ids.add(match_id)
                        new_matches_this_page += 1

                except Exception as inner_e:
                    continue

            if new_matches_this_page == 0:
                empty_pages += 1
                print(f"No new matches on page {current_page_num} ({empty_pages}/{EMPTY_PAGE_THRESHOLD})")
            else:
                empty_pages = 0
                print(f"Found {new_matches_this_page} new matches on page {current_page_num}")

            if empty_pages >= EMPTY_PAGE_THRESHOLD:
                print(f"\nStopping early after {EMPTY_PAGE_THRESHOLD} consecutive empty pages.")
                break

            # Flush buffer
            if len(buffer) >= 300:
                append_to_csv(buffer)
                print(f"Flushed {len(buffer)} matches.")
                buffer.clear()

            # Human pacing
            time.sleep(random.uniform(min_delay, max_delay))

            # Move to next page
            current_page_num += 1
            if current_page_num <= end_page:
                next_url = f"{BASE_URL}/p.{current_page_num}"
                print(f"Navigating to page {current_page_num}...")
                driver.get(next_url)

        except Exception as e:
            print(f"Page {current_page_num} failed: {e}")

            if current_page_num not in failed_pages:
                failed_pages.append(current_page_num)

            print(f"Retrying page {current_page_num} after delay...")
            time.sleep(random.uniform(6, 10))

            driver.get(f"{BASE_URL}/p.{current_page_num}")

    # Retry failed pages
    if failed_pages:
        print(f"\n=== Retrying {len(failed_pages)} failed pages ===")
        for retry_page in failed_pages:
            print(f"Retrying page {retry_page}...")
            driver.get(f"{BASE_URL}/p.{retry_page}")
            time.sleep(5)

    try:
        driver.quit()
    except:
        pass

    #  Prevent UC destructor from firing again
    driver = None
    gc.collect()

    # Final flush
    if buffer:
        append_to_csv(buffer)
        print(f"Final flush: saved {len(buffer)} matches.")

    resort_csv()
    print("Scraping complete.")

# -------------------------

if __name__ == "__main__":
    scrape_history(
        start_page=1,
        end_page=10
    )