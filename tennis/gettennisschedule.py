# gettennisschedule.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
from datetime import datetime, timedelta
import pytz

# ==============================
# BASE DIRECTORY (robust path fix)
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
output_path = os.path.join(DATA_DIR, "tennis_schedule.csv")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# ==============================
# UTILS
# ==============================
def get_central_today():
    central = pytz.timezone("America/Chicago")
    return datetime.now(central)

def extract_match_time(match):
    """
    Returns:
        HH:MM -> scheduled
        Live  -> currently playing
        Final -> completed
        TBD   -> not assigned yet
    """
    time_pattern = re.compile(r"\b\d{1,2}:\d{2}\s?(AM|PM)\b", re.IGNORECASE)
    for text in match.stripped_strings:
        clean = text.strip()
        if time_pattern.search(clean):
            raw_time = time_pattern.search(clean).group()
            try:
                parsed = datetime.strptime(raw_time.upper(), "%I:%M %p")
                return parsed.strftime("%H:%M")
            except:
                return raw_time

    if match.select_one('[data-testid="live-indicator"]'):
        return "Live"
    for text in match.stripped_strings:
        if text.strip().lower() == "final":
            return "Final"
    return "TBD"

def scrape_espn_scoreboard(target_date: datetime):
    """
    Scrape ESPN Tennis scoreboard for a specific date.
    Returns: pd.DataFrame
    """
    date_str_url = target_date.strftime("%Y%m%d")
    url = (
        f"https://www.espn.com/tennis/scoreboard/_/date/{date_str_url}"
        if target_date.date() != datetime.today().date()
        else "https://www.espn.com/tennis/scoreboard"
    )

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    # Scroll to load all tournaments
    last_height = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Grab date from top of page
    date_tag = soup.select_one("header.Card__Header h3.Card__Header__Title")
    if date_tag:
        raw_date = date_tag.get_text(strip=True)
        try:
            date_formatted = datetime.strptime(raw_date, "%A, %B %d, %Y").strftime("%Y-%m-%d")
        except:
            date_formatted = target_date.strftime("%Y-%m-%d")
    else:
        date_formatted = target_date.strftime("%Y-%m-%d")

    data = []

    tournament_cards = soup.find_all("section", class_="Card")
    for card in tournament_cards:
        tourney_name_tag = card.find("a", class_="Tournament_Link")
        tournament_name = tourney_name_tag.get_text(strip=True) if tourney_name_tag else "Unknown Tournament"

        matches_wrapper = card.find_all("div", {"data-testid": "match-cell"})
        for match in matches_wrapper:
            match_time = extract_match_time(match)
            competitors = match.select('[data-testid="competitor"]')
            if len(competitors) < 2:
                continue

            names = []
            for c in competitors:
                player_tag = c.select_one('a[data-testid="prism-linkbase"]')
                if player_tag:
                    names.append(player_tag.get_text(strip=True))
                else:
                    text_div = c.get_text(strip=True)
                    if text_div.upper() == "TBD":
                        names.append("TBD")

            if "TBD" in names:
                continue

            # Singles only
            if len(names) == 2:
                player1, player2 = names
            else:
                continue

            data.append({
                "Date": date_formatted,
                "Time": match_time,
                "Tournament": tournament_name,
                "Player 1": player1,
                "Player 2": player2
            })

    return pd.DataFrame(data)


# ==============================
# RUN SCRAPER
# ==============================
central_today = get_central_today()
central_tomorrow = central_today + timedelta(days=1)

df_today = scrape_espn_scoreboard(central_today)
df_tomorrow = scrape_espn_scoreboard(central_tomorrow)

combined_df = pd.concat([df_today, df_tomorrow], ignore_index=True)

# Save CSV
combined_df.to_csv(output_path, index=False)
print(combined_df)
