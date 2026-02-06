# nbainjuries.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
from datetime import datetime
import pytz
from unidecode import unidecode

# ------------------------------
# CONFIG
# ------------------------------
MASTER_ROSTER = "nba/data/nbaplayerspositions.csv"
OUTPUT_CSV = "nba/data/nbaplayerstatus.csv"
ESPN_URL = "https://www.espn.com/nba/injuries"

# ------------------------------
# Helpers
# ------------------------------
def canon_name(name: str) -> str:
    """
    Canonical form for name matching only.
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
def fetch_nba_injuries_selenium(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

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
            "Doubtful": "D",
            "Questionable": "Q",
            "Probable": "P",
            "Available": "A",
        }

        comment_triggers = {
            "won't play": "O",
            "out": "O",
            "doubtful": "D",
            "questionable": "Q",
            "probable": "P",
            "will play": "A",
            "available": "A",
        }

        def infer_status(row):
            base = base_map.get(row["Status_raw"], "A")
            comment = str(row["Comment"]).lower()

            for key, val in comment_triggers.items():
                if key in comment:
                    return val

            if row["Status_raw"].lower() == "day-to-day":
                return "Q"

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

    # Build canonical names (MATCHING ONLY)
    roster["canon_name"] = roster["Player"].apply(canon_name)
    inj_df["canon_name"] = inj_df["Player"].apply(canon_name)

    merged = inj_df.merge(
        roster[["player_id", "canon_name"]],
        on="canon_name",
        how="left",
    )

    # Ensure clean player_id
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

    # Drop internal helper column
    merged = merged.drop(columns=["canon_name"], errors="ignore")

    # Final column order
    merged = merged[
        ["player_id", "Player", "Status_norm", "Comment", "Last_Updated"]
    ]

    return merged

# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    print("Fetching ESPN NBA injury report...")

    df = fetch_nba_injuries_selenium(headless=True)
    if df.empty:
        print("No injuries found. Exiting.")
        raise SystemExit(0)

    df_final = add_player_ids(df)
    df_final.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved {len(df_final)} injury rows to {OUTPUT_CSV}")
