import asyncio
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/ls/29128/TT-Elite-Series"
TOTAL_PAGES = 6
OUTPUT_FILE = "tt_elite_schedule.csv"

# Dedicated Playwright profile folder (NOT your real Chrome profile)
CHROME_PROFILE_PATH = r"C:\playwright_profiles\ttelite"

async def scrape_schedule():
    all_matches = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            headless=False
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for page_num in range(1, TOTAL_PAGES + 1):
            url = BASE_URL if page_num == 1 else f"{BASE_URL}/p.{page_num}"
            print(f"Loading page {page_num}")

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("table", timeout=60000)

            rows = await page.query_selector_all("table tbody tr")

            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) < 3:
                    continue

                date_text = (await cols[0].inner_text()).strip()
                matchup_text = (await cols[2].inner_text()).strip()

                # Expect format: "Player A v Player B"
                if " v " not in matchup_text:
                    continue

                player1, player2 = matchup_text.split(" v ", 1)

                all_matches.append({
                    "date": date_text,
                    "player1": player1.strip(),
                    "player2": player2.strip()
                })

            print(f"Page {page_num} scraped")

        await context.close()

    df = pd.DataFrame(all_matches)

    if df.empty:
        print("No matches were scraped.")
        return

    # Add current year and normalize date strings
    current_year = datetime.now().year

    def parse_date(x):
        x = x.replace("-", "/")  # normalize separator
        if len(x.split()) == 1:  # no time included
            x = x + " 00:00"
        x = f"{x} {current_year}"
        try:
            return pd.to_datetime(x, errors='coerce')  # let pandas infer format
        except Exception as e:
            print(f"Failed to parse date: {x} -> {e}")
            return pd.NaT

    df["date"] = df["date"].apply(parse_date)

    # Drop rows that failed to parse
    df = df.dropna(subset=["date"])
    df.sort_values("date", inplace=True)

    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Done. Saved {len(df)} matches to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_schedule())