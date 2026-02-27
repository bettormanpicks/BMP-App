# getttmatchlogs.py

import requests
from bs4 import BeautifulSoup
import time
import csv
import os
import random

BASE_URL = "https://betsapi.com/le/29128/TT-Elite-Series"
OUTPUT_CSV = "tt_elite_matches.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/118.0.0.0 Safari/537.36",
    "Referer": BASE_URL
}

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
            fieldnames=["match_id","date","player1","player2","sets1","sets2"]
        )
        if not file_exists:
            writer.writeheader()
        for m in matches:
            writer.writerow(m)

def scrape_page(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    matches = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        date = cols[0].get("data-dt") or cols[0].get_text(strip=True)

        player_links = cols[2].find_all("a")
        if len(player_links) != 2:
            continue

        player1 = normalize_name(player_links[0].get_text())
        player2 = normalize_name(player_links[1].get_text())

        score_link = cols[3].find("a")
        if not score_link:
            continue

        score_text = score_link.get_text(strip=True)
        try:
            sets1, sets2 = map(int, score_text.split("-"))
        except:
            continue

        href = score_link.get("href", "")
        parts = href.strip("/").split("/")
        if len(parts) < 2:
            continue

        match_id = parts[1]

        matches.append({
            "match_id": match_id,
            "date": date,
            "player1": player1,
            "player2": player2,
            "sets1": sets1,
            "sets2": sets2
        })

    return matches

# -------------------------
# Main Historical Scraper
# -------------------------

def scrape_history(start_page=21, end_page=30,
                   save_interval=50,
                   min_delay=1.2,
                   max_delay=3.0):

    existing_ids = load_existing_ids()
    print(f"Loaded {len(existing_ids)} existing match IDs.")

    buffer = []

    for page in range(start_page, end_page + 1):

        url = BASE_URL if page == 1 else f"{BASE_URL}/p.{page}"
        print(f"Scraping page {page}...")

        max_retries = 5
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            try:
                matches = scrape_page(url)

                for m in matches:
                    if m["match_id"] not in existing_ids:
                        buffer.append(m)
                        existing_ids.add(m["match_id"])

                success = True  # Page scraped successfully

            except Exception as e:
                attempt += 1

                # Randomized exponential backoff
                base_wait = 4 * attempt
                jitter = random.uniform(0.5, 2.5)
                wait_time = base_wait + jitter

                print(f"Error on page {page}: {e}")
                print(f"Retry {attempt}/{max_retries} in {wait_time:.2f} seconds...")
                time.sleep(wait_time)

        if not success:
            print(f"Skipping page {page} after {max_retries} failed attempts.")

        # Save every N pages
        if page % save_interval == 0 and buffer:
            append_to_csv(buffer)
            print(f"Saved {len(buffer)} new matches at page {page}.")
            buffer = []

            # Cooldown pause after batch save
            cooldown = random.uniform(10, 25)
            print(f"Cooldown pause: {cooldown:.2f} seconds")
            time.sleep(cooldown)

        # Random sleep to avoid detection (normal per-page delay)
        sleep_time = random.uniform(min_delay, max_delay)
        time.sleep(sleep_time)

    # Final flush
    if buffer:
        append_to_csv(buffer)
        print(f"Final save: {len(buffer)} matches.")

    print("Scraping complete.")

# -------------------------

if __name__ == "__main__":
    scrape_history(
        start_page=21,
        end_page=30,
        save_interval=50,
        min_delay=1.2,
        max_delay=3.0
    )