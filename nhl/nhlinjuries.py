# nhlinjuries.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import pandas as pd
from datetime import datetime
import pytz
from unidecode import unidecode

# ------------------------------
# CONFIG
# ------------------------------
MASTER_ROSTER = "nhl/data/nhlplayers.csv"
OUTPUT_CSV = "nhl/data/nhlplayerstatus.csv"
ESPN_URL = "https://www.espn.com/nhl/injuries"

# ------------------------------
# Helpers
# ------------------------------
def canon_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return (
        unidecode(name)
        .lower()
        .replace(".", "")
        .replace(",", "")
        .strip()
    )

# ------------------------------
# Selenium Scraper
# ------------------------------
def fetch_nhl_injuries_selenium(headless=True):

    options = Options()

    # REQUIRED for GitHub Actions Linux runners
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-port=9222")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        driver.get(ESPN_URL)

        wait = WebDriverWait(driver, 25)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        rows = []

        tables = driver.find_elements(By.TAG_NAME, "table")

        for table in tables:
            tbody = table.find_element(By.TAG_NAME, "tbody")

            for tr in tbody.find_elements(By.TAG_NAME, "tr"):
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) < 5:
                    continue

                rows.append({
                    "Player": tds[0].text.strip(),
                    "Status_raw": tds[3].text.strip(),
                    "Comment": tds[4].text.strip(),
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ------------------------------
        # Normalize injury status
        # ------------------------------
        base_map = {
            "Out": "O",
            "Injured Reserve": "IR",
            "Long-Term Injured Reserve": "LTIR",
            "Day-To-Day": "GTD",
        }

        comment_triggers = {
            "out": "O",
            "will not play": "O",
            "game-time decision": "GTD",
            "day-to-day": "GTD",
            "long-term injured reserve": "LTIR",
            "ltir": "LTIR",
        }

        def infer_status(row):
            base = base_map.get(row["Status_raw"], "A")
            comment = str(row["Comment"]).lower()

            for key, val in comment_triggers.items():
                if key in comment:
                    return val

            return base

        df["Status_norm"] = df.apply(infer_status, axis=1)
        df = df.drop(columns=["Status_raw"])

        return df

    finally:
        driver.quit()

# ------------------------------
# Player ID merge
# ------------------------------
def add_player_ids(inj_df, roster_path=MASTER_ROSTER):
    roster = pd.read_csv(roster_path, dtype={"player_id": str})

    # NHL roster uses player_name instead of Player
    roster["canon_name"] = roster["player_name"].apply(canon_name)
    inj_df["canon_name"] = inj_df["Player"].apply(canon_name)

    merged = inj_df.merge(
        roster[["player_id", "canon_name"]],
        on="canon_name",
        how="left",
    )

    merged["player_id"] = (
        merged["player_id"]
        .astype(str)
        .replace("nan", "")
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Timestamp (Central time to match NBA)
    ct = pytz.timezone("US/Central")
    merged["Last_Updated"] = datetime.now(ct).strftime("%Y-%m-%d %H:%M:%S")

    merged = merged.drop(columns=["canon_name"], errors="ignore")

    merged = merged[
        ["player_id", "Player", "Status_norm", "Comment", "Last_Updated"]
    ]

    return merged

# ------------------------------
# Main
# ------------------------------
def update_nhl_injuries(headless=True):
    print("Fetching NHL injuries...")

    df = fetch_nhl_injuries_selenium(headless=headless)

    # ---- SAFETY CHECK ----
    # ESPN sometimes loads page chrome but not the injury table.
    # That produces a tiny dataframe which would wipe your CSV.
    if df is None or len(df) < 5:
        print("WARNING: Suspiciously small scrape. Skipping update to protect existing data.")
        return

    df_final = add_player_ids(df)
    df_final.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved {len(df_final)} injury rows to {OUTPUT_CSV}")

if __name__ == "__main__":
    update_nhl_injuries(headless=True)
