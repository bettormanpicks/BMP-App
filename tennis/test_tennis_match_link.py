import pandas as pd
import unicodedata

PLAYERS_FILE = "tennisplayers.csv"
MATCH_FILE = "atp_matches_2025.csv"


def norm(name):
    if pd.isna(name):
        return ""

    name = unicodedata.normalize("NFKD", str(name))
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.replace("-", " ")
    name = " ".join(name.split())
    return name.lower()


print("Loading players...")
players = pd.read_csv(PLAYERS_FILE)

print("Loading matches...")
matches = pd.read_csv(MATCH_FILE)

# normalize match player names
matches["winner_norm"] = matches["winner_name"].apply(norm)
matches["loser_norm"] = matches["loser_name"].apply(norm)

# choose a top player guaranteed to exist
target_player = "Carlos Alcaraz"
target_norm = norm(target_player)

player_matches = matches[
    (matches["winner_norm"] == target_norm) |
    (matches["loser_norm"] == target_norm)
]

print("\nMatches found:", len(player_matches))

print("\nSample matches:")
print(player_matches[[
    "winner_name",
    "loser_name",
    "match_score",
    "match_duration"
]].head(10))
