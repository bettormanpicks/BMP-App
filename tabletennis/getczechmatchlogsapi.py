# getczechmatchlogs_api_playwright.py

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://betsapi.com/table-tennis/le/22742/Czech-Liga-Pro"

API_URL = "https://betsapi.com/api/league-history?league_id=22742&page=1"

CHROME_PROFILE_PATH = r"C:\playwright_profiles\ttelite"


async def test_api():

    async with async_playwright() as p:

        context = await p.chromium.launch_persistent_context(
            CHROME_PROFILE_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto(BASE_URL)

        # Wait until the real page loads
        await page.wait_for_selector("table tbody tr", timeout=120000)

        # Call the API from inside the browser
        data = await page.evaluate(f"""
        async () => {{
            const res = await fetch("{API_URL}");
            return await res.json();
        }}
        """)

        print(data)

        await context.close()


asyncio.run(test_api())