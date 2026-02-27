import requests
from bs4 import BeautifulSoup
from unidecode import unidecode
import time

BASE_URL = "https://betsapi.com/le/29128/TT-Elite-Series"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def normalize_name(name):
    name = unidecode(name.strip())
    name = " ".join(name.split())
    return name

def scrape_page(page_number):
    if page_number == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}/p.{page_number}"

    print(f"Scraping: {url}")

    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    rows = soup.find_all("tr")

    matches = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue  # skip header or malformed rows

        # --- Date ---
        date = cols[0].get("data-dt")  # ISO format
        if not date:
            date = cols[0].get_text(strip=True)

        # --- Players ---
        player_links = cols[2].find_all("a")
        if len(player_links) != 2:
            continue
        player1 = normalize_name(player_links[0].get_text())
        player2 = normalize_name(player_links[1].get_text())

        # --- Score ---
        score_link = cols[3].find("a")
        if not score_link:
            continue
        score_text = score_link.get_text(strip=True)
        try:
            sets1, sets2 = map(int, score_text.split("-"))
        except:
            continue

        # --- Match ID ---
        href = score_link.get("href", "")
        match_id = href.strip("/").split("/")[1]  # numeric ID

        matches.append({
            "match_id": match_id,
            "date": date,
            "player1": player1,
            "player2": player2,
            "sets1": sets1,
            "sets2": sets2
        })

    return matches


if __name__ == "__main__":
    all_matches = []

    for page in range(1, 4):  # first 3 pages only
        matches = scrape_page(page)
        all_matches.extend(matches)
        time.sleep(0.5)  # be polite

    print("\nSample Results:\n")
    for m in all_matches[:10]:
        print(m)

    print(f"\nTotal matches scraped: {len(all_matches)}")