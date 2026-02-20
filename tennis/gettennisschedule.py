from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime, timedelta

# -------------------
# Function Definitions
# -------------------

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
    target_date: datetime object
    Returns: pd.DataFrame
    """
    date_str_url = target_date.strftime("%Y%m%d")
    url = f"https://www.espn.com/tennis/scoreboard/_/date/{date_str_url}" if target_date.date() != datetime.today().date() else "https://www.espn.com/tennis/scoreboard"

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
        date_formatted = datetime.strptime(raw_date, "%A, %B %d, %Y").strftime("%Y-%m-%d")
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
                    # If no player tag, check if text says TBD
                    text_div = c.get_text(strip=True)
                    if text_div.upper() == "TBD":
                        names.append("TBD")

            # --- Skip any match with TBD ---
            if "TBD" in names:
                continue

            # --- Build singles / doubles teams ---
            if len(names) == 2:
                # Singles
                player1 = names[0]
                player2 = names[1]
            elif len(names) == 4:
                # Doubles
                player1 = f"{names[0]} / {names[1]}"
                player2 = f"{names[2]} / {names[3]}"
            else:
                # Unexpected layout
                continue

            data.append({
                "Date": date_formatted,
                "Time": match_time,
                "Tournament": tournament_name,
                "Player 1": player1,
                "Player 2": player2
            })

    return pd.DataFrame(data)


# -------------------
# Run scraper for today and tomorrow
# -------------------
today = datetime.today()
tomorrow = today + timedelta(days=1)

df_today = scrape_espn_scoreboard(today)
df_tomorrow = scrape_espn_scoreboard(tomorrow)

# Combine
combined_df = pd.concat([df_today, df_tomorrow], ignore_index=True)

# Save CSV
combined_df.to_csv("data/tennis_schedule.csv", index=False)
print(combined_df)