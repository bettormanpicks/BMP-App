import requests

API_KEY = "sbf0cxa6scw0hrykgk0c4cu"
game_id = "42e9c44a-8d8d-51df-be16-afbd2343ec12"
url = f"https://api.sportsblaze.com/mlb/v1/boxscores/game/{game_id}.json?key={API_KEY}"

resp = requests.get(url)
print(resp.status_code)
print(resp.text)