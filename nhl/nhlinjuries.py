# espn_injuries.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
import os
from datetime import datetime

# ==================================================
# CONFIG for saving CSV
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(DATA_DIR, "nhlplayerstatus.csv")

# ==================================================
# SCRAPER FUNCTION
# ==================================================
def fetch_nhl_injuries_selenium(headless=True):
    """
    Scrape ESPN NHL injuries page via Selenium.
    Returns DataFrame with:
        Player, Status_norm, Comment
    """

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.espn.com/nhl/injuries")
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Grab all tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        rows = []

        for table in tables:
            tbody = table.find_element(By.TAG_NAME, "tbody")
            for tr in tbody.find_elements(By.TAG_NAME, "tr"):
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) < 5:
                    continue  # skip malformed rows

                player = tds[0].text.strip()
                return_date = tds[2].text.strip()
                status = tds[3].text.strip()
                comment = tds[4].text.strip()

                rows.append({
                    "Player": player,
                    "ReturnDate": return_date,
                    "Status": status,
                    "Comment": comment
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ---- Normalize status ----
        status_map = {
            "Long-Term Injured Reserve": "LTIR",
            "Injured Reserve": "IR",
            "Out": "O",
            "Day-To-Day": "GTD",
            "Available": "A",
        }

        triggers = {
            "long-term injured reserve": "LTIR",
            "ir-lt": "LTIR",
            "ltir": "LTIR",
            "game-time decision": "GTD",
            "day-to-day": "GTD",
            "will play": "A",
            "available": "A",
        }

        def infer_status(row):
            status = row["Status"]
            comment = str(row["Comment"]).lower()
            return_date = str(row["ReturnDate"]).strip()

            # 1️⃣ Strong base from STATUS column
            norm = status_map.get(status, "A")

            # 2️⃣ EST. RETURN DATE == today → GTD
            if return_date:
                try:
                    rd = datetime.strptime(return_date, "%b %d").replace(
                        year=datetime.now().year
                    ).date()
                    if rd == datetime.now().date():
                        return "GTD"
                except:
                    pass

            # 3️⃣ Comment overrides
            for word, code in triggers.items():
                if word in comment:
                    return code

            return norm

        df["Status_norm"] = df.apply(infer_status, axis=1)

        # Return only the columns we need
        return df[["Player", "Status_norm", "ReturnDate", "Comment"]]

    finally:
        driver.quit()

# ==================================================
# WRAPPER TO SAVE CSV
# ==================================================
def update_nhl_injuries(headless=True):
    df = fetch_nhl_injuries_selenium(headless=headless)
    if df.empty:
        print("No injuries found.")
        return df

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"[DONE] Saved {len(df)} rows -> {OUTPUT_CSV}")
    return df

# ==================================================
# RUN SCRIPT DIRECTLY
# ==================================================
if __name__ == "__main__":
    print("Fetching NHL injuries...")
    df = update_nhl_injuries(headless=False)
    if not df.empty:
        print(f"Rows scraped: {len(df)}")
        print(df.head(20))
