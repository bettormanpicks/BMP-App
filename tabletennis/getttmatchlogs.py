# getttmatchlogs.py

import asyncio
import csv
import os
import random
import time
import pandas as pd
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/le/29128/TT-Elite-Series"
OUTPUT_CSV = "data/tt_elite_matchlogs.csv"

# IMPORTANT: Same profile path as schedule script
CHROME_PROFILE_PATH = r"C:\playwright_profiles\ttelite"

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

# -------------------------
# Playwright Scraper
# -------------------------

async def scrape_history(start_page=1, end_page=6,
                         min_delay=1.5,
                         max_delay=3.5):

    existing_ids = load_existing_ids()
    print(f"Loaded {len(existing_ids)} existing match IDs.")

    buffer = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for page_num in range(start_page, end_page + 1):

            url = BASE_URL if page_num == 1 else f"{BASE_URL}/p.{page_num}"
            print(f"Scraping page {page_num}...")

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("table", timeout=60000)

            rows = await page.query_selector_all("table tbody tr")

            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) < 4:
                    continue

                date = await cols[0].get_attribute("data-dt")
                if not date:
                    date = (await cols[0].inner_text()).strip()

                player_links = await cols[2].query_selector_all("a")
                if len(player_links) != 2:
                    continue

                player1 = normalize_name(await player_links[0].inner_text())
                player2 = normalize_name(await player_links[1].inner_text())

                score_link = await cols[3].query_selector("a")
                if not score_link:
                    continue

                score_text = (await score_link.inner_text()).strip()

                # Only process finished matches (score like 3-1)
                if "-" not in score_text:
                    continue

                try:
                    sets1, sets2 = map(int, score_text.split("-"))
                except:
                    continue

                href = await score_link.get_attribute("href")
                if not href or "/r/" not in href:
                    continue

                match_id = href.split("/")[2]

                if match_id not in existing_ids:
                    buffer.append({
                        "match_id": match_id,
                        "date": date,
                        "player1": player1,
                        "player2": player2,
                        "sets1": sets1,
                        "sets2": sets2
                    })
                    existing_ids.add(match_id)

            # Human-like delay
            sleep_time = random.uniform(min_delay, max_delay)
            await asyncio.sleep(sleep_time)

        await context.close()

    def resort_csv():
        if not os.path.exists(OUTPUT_CSV):
            return

        df = pd.read_csv(OUTPUT_CSV)

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        df.sort_values("date", ascending=False, inplace=True)

        # Force consistent ISO format
        df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")

        df.to_csv(OUTPUT_CSV, index=False)

        print("CSV re-sorted by date (newest first).")

    if buffer:
        append_to_csv(buffer)
        print(f"Saved {len(buffer)} new matches.")
        resort_csv()

    print("Scraping complete.")

# -------------------------

if __name__ == "__main__":
    asyncio.run(scrape_history(
        start_page=1,
        end_page=6
    ))