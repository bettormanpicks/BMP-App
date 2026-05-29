import os
import re
import pandas as pd
from datetime import datetime, timedelta
from curl_cffi import requests

# --- PATH ANCHORING ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "tt_elite_schedule.csv")
CURL_PATH = os.path.join(SCRIPT_DIR, "curl_command.txt")

# --- HELPER FUNCTIONS ---
def get_session_from_curl():
    with open(CURL_PATH, "r") as f:
        cmd = f.read()
    headers = {}
    cookies = {}
    for line in cmd.split("-H"):
        match = re.search(r"'([^']+)'", line)
        if match:
            h = match.group(1).split(": ", 1)
            if len(h) == 2 and h[0].lower() != 'referer': headers[h[0]] = h[1]
    cookie_match = re.search(r"-b '([^']+)'", cmd)
    if cookie_match:
        for c in cookie_match.group(1).split('; '):
            if '=' in c:
                k, v = c.split('=', 1)
                cookies[k] = v
    return headers, cookies

def normalize_name(name):
    name = name.replace('"', '').replace("'", "")
    if ',' in name:
        parts = name.split(',')
        return f"{parts[1].strip()} {parts[0].strip()}".title()
    return name.strip().title()

# --- MAIN EXECUTION ---
def main():
    headers, cookies = get_session_from_curl()
    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/tt-elite-series-1/matches"
    
    # Dynamic Date Range (Evergreen)
    start_date = datetime.now().strftime("%Y-%m-%d 00:00:00")
    end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d 23:59:59")
    
    params = {
        'lang': 'en', 'first': '50', 'status': 'not_started', 'audience': 'us',
        'date_between[]': [start_date, end_date]
    }

    print("Fetching upcoming schedule...")
    buffer = []
    
    while True:
        response = requests.get(base_url, headers=headers, cookies=cookies, params=params, impersonate="chrome")
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}")
            break
            
        data = response.json()
        edges = data.get("data", {}).get("edges", [])
        if not edges: break

        for edge in edges:
            node = edge["node"]
            # Clean Date
            raw_date = node.get("match_date", "").split('.')[0]
            try:
                match_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            except:
                match_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            buffer.append({
                "match_id": node["slug"].strip("/"),
                "match_date": match_date,
                "player1": normalize_name(node["teams"][0]["name"]),
                "player2": normalize_name(node["teams"][1]["name"]),
                "match_link": f"https://scores24.live/en/table-tennis/{node['slug'].strip('/')}"
            })

        # Pagination
        page_info = data.get("data", {}).get("pageInfo", {})
        if page_info.get("hasNextPage"):
            params['after'] = page_info.get("endCursor")
        else: break

    if buffer:
        if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
        df = pd.DataFrame(buffer)
        df.sort_values("match_date", inplace=True)
        df.to_csv(CSV_PATH, index=False)
        print(f"✅ Schedule complete. Saved {len(buffer)} upcoming matches.")

if __name__ == "__main__":
    main()