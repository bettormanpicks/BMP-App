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
import os

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
    """
    Canonical form for name matching.
    ASCII, lowercase, no punctuation.
    """
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
# Scraper
# ------------------------------
def fetch_nhl_injuries_selenium(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Use webdriver-manager to install ChromeDriver automatically
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(ESPN_URL)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        rows = []

        for table in driver.find_elements(By.TAG_NAME, "table"):
            tbody = table.find_element(By.TAG_NAME, "tbody")
            for tr in tbody.find_elements(By.TAG_NAME, "tr"):
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) < 5:
                    continue

                player = tds[0].text.strip()
                return_date = tds[2].text.strip()
                status = tds[3].text.strip()
                comment = tds[4].text.strip()

                rows.append({
                    "Player": player,
                    "ReturnDate": return_date,
                    "Status_raw": status,
                    "Comment": comment
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ------------------------------
        # Normalize status
        # ------------------------------
        base_map = {
            "Long-Term Injured Reserve": "LTIR",
            "Injured Reserve": "IR",
            "Out": "O",
            "Day-To-Day": "GTD",
            "Available": "A",
        }

        comment_triggers = {
            "long-term injured reserve": "LTIR",
            "ir-lt": "LTIR",
            "ltir": "LTIR",
            "game-time decision": "GTD",
            "day-to-day": "GTD",
            "will play": "A",
            "available": "A",
        }

        def infer_status(row):
            base = base_map.get(row["Status_raw"], "A")
            comment = str(row["Comment"]).lower()

            for key, val in comment_triggers.items():
                if key in comment:
                    return val

            # If 'Day-To-Day' in raw status but no comment trigger, mark as GTD
            if row["Status_raw"].lower() == "day-to-day":
                return "GTD"

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

    # Canonical names for matching
    roster["canon_name"] = roster["player_name"].apply(canon_name)
    inj_df["canon_name"] = inj_df["Player"].apply(canon_name)

    merged = inj_df.merge(
        roster[["player_id", "canon_name"]],
        on="canon_name",
        how="left",
    )

    # Clean player_id
    merged["player_id"] = (
        merged["player_id"]
        .astype(str)
        .replace("nan", "")
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Timestamp (Central Time)
    ct = pytz.timezone("US/Central")
    merged["Last_Updated"] = datetime.now(ct).strftime("%Y-%m-%d %H:%M:%S")

    # Drop helper column
    merged = merged.drop(columns=["canon_name"], errors="ignore")

    # Final column order
    merged = merged[
        ["player_id", "Player", "Status_norm", "Comment", "Last_Updated"]
    ]

    return merged

# ------------------------------
# Scrape & save CSV
# ------------------------------
def update_nhl_injuries(headless=True):
    df = fetch_nhl_injuries_selenium(headless=headless)
    if df.empty:
        print("No injuries found.")
        return df

    df_final = add_player_ids(df)
    df_final.to_csv(OUTPUT_CSV, index=False)
    print(f"[DONE] Saved {len(df_final)} rows -> {OUTPUT_CSV}")
    return df_final

# ------------------------------
# Run script directly
# ------------------------------
if __name__ == "__main__":
    print("Fetching NHL injuries...")
    update_nhl_injuries(headless=False)
