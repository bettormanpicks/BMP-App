# nbainjuries.py
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import unidecode

# ------------------------------
# CONFIG
# ------------------------------
POSITIONS_CSV = "nba/data/nbaplayerspositions.csv"
OUTPUT_CSV = "nba/data/nbaplayerstatus.csv"


# ------------------------------
# Scrape ESPN NBA Injuries
# ------------------------------
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
                    continue  # skip malformed rows
                player = tds[0].text.strip()
                status = tds[3].text.strip()
                comment = tds[4].text.strip()
                rows.append({"Player": player, "Status": status, "Comment": comment})

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Normalize status
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
            comment_lower = str(row["Comment"]).lower()
            for word, code in triggers.items():
                if word in comment_lower:
                    return code
            if str(row["Status"]).lower() == "day-to-day":
                return "Q"
            return base

        df["Status_norm"] = df.apply(infer_status, axis=1)

        return df[["Player", "Status_norm", "Comment"]]

    finally:
        driver.quit()


# ------------------------------
# Merge with master roster for player_id
# ------------------------------
def enrich_with_player_id(inj_df):
    pos_df = pd.read_csv(POSITIONS_CSV, dtype={"player_id": str})

    # Normalize names for matching
    inj_df["Player_norm"] = inj_df["Player"].apply(lambda x: unidecode.unidecode(x).lower().strip())
    pos_df["Player_norm"] = pos_df["Player"].apply(lambda x: unidecode.unidecode(x).lower().strip())

    # Merge on normalized player names
    merged = inj_df.merge(
        pos_df[["player_id", "Player_norm"]],
        on="Player_norm",
        how="left"
    )

    merged.drop(columns=["Player_norm"], inplace=True)
    merged["player_id"] = merged["player_id"].astype(str)

    # Add Last_Updated timestamp
    merged["Last_Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return merged


# ------------------------------
# Main execution
# ------------------------------
if __name__ == "__main__":
    print("Fetching ESPN NBA injury report...")
    inj_df = fetch_nba_injuries_selenium(headless=True)

    if inj_df.empty:
        print("No injury data found.")
    else:
        inj_df = enrich_with_player_id(inj_df)
        inj_df.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved {len(inj_df)} injury rows to {OUTPUT_CSV}")
