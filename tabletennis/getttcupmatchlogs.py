import os
import re
import pandas as pd
from datetime import datetime, timedelta
from curl_cffi import requests

# --- PATH ANCHORING ---
# Gets the directory where this script resides, regardless of current working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "tt_cup_matchlogs.csv")
CURL_PATH = os.path.join(SCRIPT_DIR, "curl_command.txt")

# --- HELPER FUNCTIONS ---
def append_to_csv(new_rows):
    df_new = pd.DataFrame(new_rows)
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if not os.path.exists(CSV_PATH):
        df_new.to_csv(CSV_PATH, index=False)
    else:
        df_new.to_csv(CSV_PATH, mode='a', header=False, index=False)

def resort_csv():
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        df.drop_duplicates(subset=["match_id"], keep="first", inplace=True)
        df["match_date"] = pd.to_datetime(df["match_date"])
        df.sort_values(by="match_date", ascending=False, inplace=True)
        df.to_csv(CSV_PATH, index=False)

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

# --- MAIN EXECUTION ---
def main():
    headers, cookies = get_session_from_curl()
    buffer = []
    existing_ids = set()
    
    if os.path.exists(CSV_PATH):
        existing_ids = set(pd.read_csv(CSV_PATH)["match_id"].astype(str))

    base_url = "https://scores24.live/rapi/localized/leagues/table-tennis/international-tt-cup/matches"

    start_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")
    end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
    
    params = {
        'lang': 'en', 'first': '20', 'status': 'ended', 'audience': 'us',
        'date_between[]': [start_date, end_date]
    }

    cutoff_date = datetime.now() - timedelta(hours=72)
    print(f"Scraping matches since: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        response = requests.get(base_url, headers=headers, cookies=cookies, params=params, impersonate="chrome")
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}")
            break
            
        payload = response.json()
        data_block = payload.get("data", {}) or {}
        edges_list = data_block.get("edges", [])
        
        if not edges_list: break

        stop_loop = False
        for edge in edges_list:
            node = edge.get("node", {})
            match_id = node.get("slug", "").strip("/")
            
            raw_date = node.get("match_date", "")
            match_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            dt = datetime.now()
            
            if raw_date:
                try:
                    clean_date = raw_date.split('.')[0] 
                    dt = datetime.strptime(clean_date, "%Y-%m-%dT%H:%M:%S")
                    match_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    pass

            if dt < cutoff_date:
                stop_loop = True
                continue
            
            if match_id in existing_ids: continue
            
            raw_scores = node.get("result_scores", [])
            sets_list = []
            total_pts = 0
            
            for s in raw_scores:
                val = s.get('value', '')
                if ':' in val:
                    try:
                        p1_s, p2_s = map(int, val.split(':'))
                        if p1_s > 3 or p2_s > 3:
                            sets_list.append(val)
                            total_pts += (p1_s + p2_s)
                    except ValueError:
                        continue

            def clean_name(name):
                name = name.replace('"', '').replace("'", "")
                if ',' in name:
                    parts = name.split(',')
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                return name.title()

            p1 = clean_name(node['teams'][0].get("name", "Unknown"))
            p2 = clean_name(node['teams'][1].get("name", "Unknown"))
            
            four_plus = 1.0 if len(sets_list) >= 4 else 0.0
            
            buffer.append({
                "match_id": match_id, "match_date": match_date_str, "player1": p1, "player2": p2,
                "sets": "|".join(sets_list), "total_points": float(total_pts),
                "match_winner": float(node.get("winner", 1)), "four_plus": four_plus
            })
            existing_ids.add(match_id)

        if stop_loop:
            print("  🏁 Reached historical data. Stopping.")
            break

        page_info = data_block.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            params['after'] = page_info.get("endCursor")
        else: break

    if buffer:
        append_to_csv(buffer)
        resort_csv()
        print(f"🚀 Success! Logged {len(buffer)} new matches.")
    else:
        print("✅ No new matches found.")

if __name__ == "__main__":
    main()