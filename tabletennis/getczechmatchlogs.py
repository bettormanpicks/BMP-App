# gettt_czech_matchlogs.py

import asyncio
import csv
import os
import random
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/le/22742/Czech-Liga-Pro"
OUTPUT_CSV = "data/tt_czech_matchlogs.csv"

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

def resort_csv():
    if not os.path.exists(OUTPUT_CSV):
        return

    df = pd.read_csv(OUTPUT_CSV)

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

async def scrape_history(start_page=1,
                         end_page=8,
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

        # Block Google vignette / ad network requests
        await context.route("**/*", lambda route, request: (
            route.abort()
            if any(x in request.url for x in ["doubleclick", "googlesyndication", "googleads"])
            else route.continue_()
        ))

        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(60000)

        for page_num in range(start_page, end_page + 1):

            print(f"\nScraping page {page_num}...")

            success = False

            for attempt in range(5):
                try:
                    if page_num == 1:
                        await page.goto(BASE_URL, timeout=60000)
                        await page.wait_for_selector("table", timeout=60000)
                    else:
                        print(f"Clicking page {page_num}...")

                        await page.click(f'a[href*="p.{page_num}"]')

                        # Wait for table rows to reappear after AJAX reload
                        await page.wait_for_selector("table tbody tr", timeout=60000)

                        # Small buffer for stability
                        await page.wait_for_timeout(1000)

                    success = True
                    consecutive_failures = 0
                    break

                except Exception as e:
                    wait_time = min(60, (2 ** attempt) + random.uniform(5, 15))
                    print(f"Attempt {attempt+1} failed. Cooling {round(wait_time)}s. Error: {e}")
                    await asyncio.sleep(wait_time)

            if not success:
                consecutive_failures += 1
                print(f"Page {page_num} failed after 5 attempts. Marking for retry.")
                failed_pages.append(page_num)

                if consecutive_failures >= 5:
                    cooldown = random.uniform(300, 600)
                    print(f"Too many consecutive failures. Long cooldown: {round(cooldown)}s")
                    await asyncio.sleep(cooldown)
                    consecutive_failures = 0

                continue

            # ------------------------
            # Human simulation
            # ------------------------
            await page.mouse.wheel(0, random.randint(300, 1200))
            await asyncio.sleep(random.uniform(0.5, 1.5))

            rows = await page.query_selector_all("table tbody tr")

            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) < 4:
                    continue

                date = await cols[0].get_attribute("data-dt")
                if not date:
                    date = (await cols[0].inner_text()).strip()

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

            # ------------------------
            # Safe periodic flush
            # ------------------------
            if len(buffer) >= 300:
                append_to_csv(buffer)
                print(f"Flushed {len(buffer)} matches.")
                buffer.clear()

            # ------------------------
            # Human pacing
            # ------------------------
            await asyncio.sleep(random.uniform(min_delay, max_delay))

            # ------------------------
            # Session refresh every 400 pages
            # ------------------------
            if page_num % 400 == 0:
                print("Refreshing browser session...")
                await context.close()
                await asyncio.sleep(random.uniform(30, 60))

                context = await p.chromium.launch_persistent_context(
                    CHROME_PROFILE_PATH,
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.pages[0] if context.pages else await context.new_page()

            # ------------------------
            # Heartbeat
            # ------------------------
            if page_num % 250 == 0:
                print(f"=== Reached page {page_num} successfully ===")

        # ------------------------
        # Second pass for failed pages
        # ------------------------
        if failed_pages:
            print(f"\n=== Retrying {len(failed_pages)} failed pages ===")

            for retry_page in failed_pages:
                print(f"Retrying page {retry_page}...")

                url = BASE_URL if retry_page == 1 else f"{BASE_URL}/p.{retry_page}"

                try:
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

                    await asyncio.sleep(random.uniform(5, 10))

                except Exception as e:
                    print(f"Retry failed again for page {retry_page}: {e}")

        await context.close()

    if buffer:
        append_to_csv(buffer)
        print(f"Final flush: saved {len(buffer)} matches.")

    resort_csv()
    print("Scraping complete.")

# -------------------------

if __name__ == "__main__":
    asyncio.run(scrape_history(
        start_page=1,
        end_page=8
    ))