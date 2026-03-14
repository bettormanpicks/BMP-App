import asyncio
import pandas as pd
import os
import re
from bs4 import BeautifulSoup
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
            # Freeze table HTML to avoid DOM updates mid-scrape
            table_html = await page.inner_html("table tbody")

            soup = BeautifulSoup(table_html, "html.parser")
            rows = soup.select("tr")

            for row in rows:
                cols = row.select("td")
                if len(cols) < 4:
                    continue

                # --- DATE as rendered in browser ---
                date_text = cols[0].get_text(strip=True)

                # Skip rows that show scores instead of dates or empty strings
                if not re.match(r"\d{2}/\d{2}\s\d{2}:\d{2}", date_text):
                    continue

                # --- PLAYERS ---
                players = cols[2].select("a")
                if len(players) < 2:
                    continue

                player1 = players[0].get_text(strip=True)
                player2 = players[1].get_text(strip=True)

                # --- MATCH ID ---
                match_id = None

                match_link = cols[3].select_one("a")
                if match_link:
                    href = match_link.get("href")
                    if href:
                        m = re.search(r"\d+", href)
                        if m:
                            match_id = m.group()

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

    # Append year to browser date text
    df["date"] = df["date"] + f" {current_year}"

    # Let pandas parse it directly
    df["date"] = pd.to_datetime(df["date"], format="%m/%d %H:%M %Y", errors="coerce")
    df.dropna(subset=["date"], inplace=True)
    df.sort_values("date", inplace=True)

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done. Saved {len(df)} matches to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(scrape_schedule())