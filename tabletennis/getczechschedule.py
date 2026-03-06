import asyncio
import pandas as pd
import os
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/table-tennis/ls/22742/Czech-Liga-Pro"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "tt_czech_schedule.csv")

CHROME_PROFILE_PATH = r"C:\playwright_profiles\ttelite"

async def scrape_schedule():
    all_matches = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # Block ads
        await context.route("**/*", lambda route, request: (
            route.abort() if any(x in request.url for x in ["google", "doubleclick"]) else route.continue_()
        ))

        page = context.pages[0] if context.pages else await context.new_page()

        # Load first page
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_selector("table", timeout=60000)

        # Detect pagination
        pagination_links = await page.query_selector_all('a[href*="/p."]')
        max_page = 1
        for link in pagination_links:
            href = await link.get_attribute("href")
            if href and "/p." in href:
                try:
                    page_number = int(href.split("/p.")[1])
                    max_page = max(max_page, page_number)
                except:
                    continue

        print(f"Detected {max_page} total pages.")

        # -------------------------
        # Scrape all pages
        # -------------------------
        for page_num in range(1, max_page + 1):

            if page_num == 1:
                await page.goto(BASE_URL, timeout=60000)
                await page.wait_for_selector("table", timeout=60000)
            else:
                print(f"Clicking page {page_num}")
                old_first_row = await page.locator("table tbody tr").first.inner_text()
                await page.click(f'a[href*="p.{page_num}"]')
                await page.wait_for_function(
                    """(oldText) => {
                        const row = document.querySelector("table tbody tr");
                        return row && row.innerText !== oldText;
                    }""",
                    arg=old_first_row
                )

            print(f"Scraping page {page_num}")
            rows = await page.query_selector_all("table tbody tr")
            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) < 4:
                    continue

                # --- DATE as rendered in browser ---
                date_text = (await cols[0].inner_text()).strip()

                # Skip rows that show scores instead of dates or empty strings
                if not date_text or not date_text[0].isdigit():
                    continue

                # --- PLAYERS ---
                matchup_links = await cols[2].query_selector_all("a")
                if len(matchup_links) < 2:
                    continue
                player1 = (await matchup_links[0].inner_text()).strip()
                player2 = (await matchup_links[1].inner_text()).strip()

                # --- MATCH ID ---
                match_link = await cols[3].query_selector("a")
                if match_link:
                    href = await match_link.get_attribute("href")
                    if href and "/r/" in href:
                        match_id = href.split("/")[2]
                    else:
                        match_id = None
                else:
                    match_id = None

                all_matches.append({
                    "match_id": match_id,
                    "date": date_text,
                    "player1": player1,
                    "player2": player2
                })

            print(f"Page {page_num} scraped")

        await context.close()

    # -------------------------
    # Convert to DataFrame
    # -------------------------
    df = pd.DataFrame(all_matches)
    if df.empty:
        print("No matches scraped.")
        return

    current_year = datetime.now().year

    # Convert browser-rendered times (already local CST) into timestamps
    def parse_browser_time(x):
        # BetsAPI shows dates as MM/DD HH:MM
        try:
            dt = datetime.strptime(f"{x} {current_year}", "%m/%d %H:%M %Y")
            return dt
        except:
            return pd.NaT

    df["date"] = df["date"].apply(parse_browser_time)
    df.dropna(subset=["date"], inplace=True)
    df.sort_values("date", inplace=True)

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done. Saved {len(df)} matches to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(scrape_schedule())