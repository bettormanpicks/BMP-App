# nbainjuries.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from datetime import datetime
import pytz

# Path to master roster CSV
MASTER_ROSTER = "nba/data/nbaplayerspositions.csv"
OUTPUT_CSV = "nba/data/nbaplayerstatus.csv"

def fetch_nba_injuries_selenium(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://www.espn.com/nba/injuries")
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        tables = driver.find_elements(By.TAG_NAME, "table")
        rows = []

        for table in tables:
            tbody = table.find_element(By.TAG_NAME, "tbody")
            for tr in tbody.find_elements(By.TAG_NAME, "tr"):
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) < 5:
                    continue
                player = tds[0].text.strip()
                status = tds[3].text.strip()
                comment = tds[4].text.strip()
                rows.append({"Player": player, "Status_norm": status, "Comment": comment})

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Normalize statuses
        status_map = {"Out": "O", "Doubtful": "D", "Questionable": "Q", "Probable": "P", "Available": "A"}
        triggers = {"won't play": "O", "out": "O", "doubtful": "D", "questionable": "Q",
                    "probable": "P", "will play": "A", "available": "A"}

        def infer_status(row):
            base = status_map.get(row["Status_norm"], "A")
            comment = str(row["Comment"]).lower()
            for word, code in triggers.items():
                if word in comment:
                    return code
            if row["Status_norm"].lower() == "day-to-day":
                return "Q"
            return base

        df["Status_norm"] = df.apply(infer_status, axis=1)
        return df

    finally:
        driver.quit()

def add_player_ids(inj_df, roster_path=MASTER_ROSTER):
    # Load master roster
    roster_df = pd.read_csv(roster_path, dtype={"player_id": str})
    roster_df["Player_norm"] = roster_df["Player"].str.lower().str.replace(".", "", regex=False).str.strip()
    inj_df["Player_norm"] = inj_df["Player"].str.lower().str.replace(".", "", regex=False).str.strip()

    # Merge to get player_id
    merged = pd.merge(inj_df, roster_df[["player_id", "Player_norm"]],
                      on="Player_norm", how="left")

    # Ensure player_id is string without decimal
    merged["player_id"] = merged["player_id"].astype(str).str.replace(".0", "", regex=False).str.strip()

    # Add Last_Updated timestamp in CT
    ct = pytz.timezone("US/Central")
    merged["Last_Updated"] = datetime.now(ct).strftime("%Y-%m-%d %H:%M:%S")

    # Reorder columns
    merged = merged[["player_id", "Player", "Status_norm", "Comment", "Last_Updated"]]

    return merged

if __name__ == "__main__":
    print("Fetching ESPN NBA injury report...")
    df = fetch_nba_injuries_selenium(headless=True)
    if df.empty:
        print("No injuries found. Exiting.")
        exit(0)

    df_final = add_player_ids(df)
    df_final.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(df_final)} injury rows to {OUTPUT_CSV}")
