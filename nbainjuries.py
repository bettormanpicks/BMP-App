# nbainjuries.py
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from unidecode import unidecode

# Path to CSVs
PLAYER_POS_CSV = "nba/data/nbaplayerspositions.csv"
OUTPUT_CSV = "nba/data/nbaplayerstatus.csv"
LOG_FILE = "nba/data/nbaplayerstatus.log"

def fetch_nba_injuries_selenium(headless=True):
    """
    Scrape ESPN NBA injuries page via Selenium.
    Returns DataFrame with:
        Player, Status_norm, Comment
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.espn.com/nba/injuries")
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
                status = tds[3].text.strip()
                comment = tds[4].text.strip()

                rows.append({"Player": player, "Status": status, "Comment": comment})

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ---- Normalize status ----
        status_map = {"Out": "O", "Doubtful": "D", "Questionable": "Q", "Probable": "P", "Available": "A"}
        triggers = {
            "won't play": "O",
            "out": "O",
            "doubtful": "D",
            "questionable": "Q",
            "probable": "P",
            "will play": "A",
            "available": "A",
        }

        def infer_status(row):
            base = status_map.get(row["Status"], "A")
            comment = str(row["Comment"]).lower()
            for word, code in triggers.items():
                if word in comment:
                    return code
            if row["Status"].lower() == "day-to-day":
                return "Q"
            return base

        df["Status_norm"] = df.apply(infer_status, axis=1)

        return df[["Player", "Status_norm", "Comment"]]

    finally:
        driver.quit()


def add_player_ids(df):
    """
    Add player_id from nbaplayerspositions.csv using unidecode-normalized names.
    """
    pos_df = pd.read_csv(PLAYER_POS_CSV)
    pos_df["norm_name"] = pos_df["Player"].apply(lambda x: unidecode(str(x).lower().strip()))
    df["norm_name"] = df["Player"].apply(lambda x: unidecode(str(x).lower().strip()))

    merged = df.merge(pos_df[["player_id", "norm_name"]], on="norm_name", how="left")
    merged = merged.drop(columns=["norm_name"])
    # Remove decimal points in player_id
    merged["player_id"] = merged["player_id"].apply(lambda x: str(int(x)) if pd.notna(x) else "")
    return merged


if __name__ == "__main__":
    try:
        print("Fetching ESPN NBA injury report...")
        df = fetch_nba_injuries_selenium(headless=True)

        if df.empty:
            print("No injuries scraped. Exiting.")
        else:
            df = add_player_ids(df)
            df["Last_Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Ensure directory exists
            os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

            df.to_csv(OUTPUT_CSV, index=False)
            print(f"Saved {len(df)} injury rows to {OUTPUT_CSV}")

    except Exception as e:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            import traceback
            f.write(traceback.format_exc())
        raise