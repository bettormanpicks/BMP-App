# getczechmatchlogs.py

import asyncio
import csv
import os
import random
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/table-tennis/le/22742/Czech-Liga-Pro"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_czech_matchlogs.csv")

# Same persistent profile (keeps Cloudflare clearance)
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

# ------------------------
# Robust pagination helper
# ------------------------
async def click_next_page(page, current_page_num):
    """Click the pagination link for the next page on betsapi table."""
    # Only visible links inside pagination
    pagination_links = page.locator('ul.pagination a[href*="p."] >> visible=true')
    count = await pagination_links.count()
    if count == 0:
        raise Exception("No visible pagination links found!")

    # Look for the exact page number link
    for i in range(count):
        href = await pagination_links.nth(i).get_attribute("href")
        if not href or "/p." not in href:
            continue
        # Extract page number from href
        try:
            page_num = int(href.split("/p.")[1].split("/")[0])
            if page_num == current_page_num:
                await pagination_links.nth(i).click(force=True)
                # Wait for AJAX content to load
                await page.wait_for_selector("table tbody tr >> nth=0", timeout=60000)
                await page.wait_for_timeout(1000)  # small buffer
                return True
        except:
            continue
    raise Exception(f"Could not find pagination link for page {current_page_num}")

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
# Playwright Scraper
# -------------------------
async def scrape_history(start_page=101,
                         end_page=5087,
                         min_delay=3,
                         max_delay=7):

    existing_ids = load_existing_ids()
    print(f"Loaded {len(existing_ids)} existing match IDs.")

    buffer = []
    consecutive_failures = 0
    failed_pages = []

    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # Block ads
        await context.route("**/*", lambda route, request: (
            route.abort() if any(x in request.url for x in ["doubleclick", "googlesyndication", "googleads"]) 
            else route.continue_()
        ))

        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(60000)

        # --- Always start at page 1 ---
        await page.goto(BASE_URL)
        await page.wait_for_selector("table")

        # Navigate to start_page robustly
        for page_num in range(2, start_page + 1):
            await click_next_page(page, page_num)

        current_page_num = start_page

        while current_page_num <= end_page:
            print(f"\nScraping page {current_page_num}...")

            try:
                # Wait for the table rows to appear
                await page.wait_for_selector("table tbody tr >> nth=0", timeout=60000)
                await page.wait_for_timeout(1000)  # buffer

                rows = await page.query_selector_all("table tbody tr")

                for row in rows:
                    cols = await row.query_selector_all("td")
                    if len(cols) < 4:
                        continue

                    date = await cols[0].get_attribute("data-dt") or (await cols[0].inner_text()).strip()
                    try:
                        parsed = pd.to_datetime(date, utc=True)
                        parsed = parsed.tz_convert(None)
                        date = parsed.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        continue

                    player_links = await cols[2].query_selector_all("a")
                    if len(player_links) != 2:
                        continue

                    player1 = normalize_name(await player_links[0].inner_text())
                    player2 = normalize_name(await player_links[1].inner_text())

                    score_link = await cols[3].query_selector("a")
                    if not score_link:
                        continue

                    score_text = (await score_link.inner_text()).strip()
                    if "-" not in score_text:
                        continue

                    try:
                        sets1, sets2 = map(int, score_text.split("-"))
                    except:
                        continue

                    href = await score_link.get_attribute("href")
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

                # Flush buffer periodically
                if len(buffer) >= 300:
                    append_to_csv(buffer)
                    print(f"Flushed {len(buffer)} matches.")
                    buffer.clear()

                # Human pacing
                await asyncio.sleep(random.uniform(min_delay, max_delay))

                # Move to next page if not at end
                if current_page_num < end_page:
                    await click_next_page(page, current_page_num + 1)

                current_page_num += 1

            except Exception as e:
                print(f"Page {current_page_num} failed: {e}")
                failed_pages.append(current_page_num)
                consecutive_failures += 1

                if consecutive_failures >= 5:
                    cooldown = random.uniform(300, 600)
                    print(f"Too many consecutive failures. Cooling {round(cooldown)}s...")
                    await asyncio.sleep(cooldown)
                    consecutive_failures = 0

                # Move to next page
                current_page_num += 1

        # --- Retry failed pages ---
        if failed_pages:
            print(f"\n=== Retrying {len(failed_pages)} failed pages ===")
            for retry_page in failed_pages:
                print(f"Retrying page {retry_page}...")
                # Always start from page 1 and click forward
                await page.goto(BASE_URL)
                await page.wait_for_selector("table")
                for page_num in range(2, retry_page + 1):
                    await click_next_page(page, page_num)
                # Then scrape as above (reuse same scraping logic)

        await context.close()

    # Final flush
    if buffer:
        append_to_csv(buffer)
        print(f"Final flush: saved {len(buffer)} matches.")

    resort_csv()
    print("Scraping complete.")

# -------------------------

if __name__ == "__main__":
    asyncio.run(scrape_history(
        start_page=101,
        end_page=5087
    ))