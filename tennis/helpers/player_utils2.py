import os
import pandas as pd
import unicodedata

PLAYERS_FILE = "data/tennisplayers.csv"
ALIAS_FILE = "data/player_aliases.csv"

# ==========================================================
# NORMALIZATION
# (ONLY used to create lookup keys — never for display)
# ==========================================================
def normalize_name(name: str) -> str:
    if pd.isna(name) or not name:
        return ""

    # remove accents (Djoković -> Djokovic)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    name = name.lower()
    name = (
        name.replace(".", "")
            .replace(",", "")
            .replace("'", "")
            .replace("-", " ")
    )

    # collapse whitespace
    name = " ".join(name.split())

    return name


# ==========================================================
# LOAD / INIT ALIAS DATABASE
# ==========================================================
if os.path.exists(ALIAS_FILE):
    alias_df = pd.read_csv(ALIAS_FILE)

    # ensure columns exist
    for col in ["scoreboard_name", "player_id", "canonical_name"]:
        if col not in alias_df.columns:
            alias_df[col] = None
else:
    alias_df = pd.DataFrame(columns=["scoreboard_name", "player_id", "canonical_name"])

# normalized lookup
alias_lookup = {
    normalize_name(row["scoreboard_name"]): row["player_id"]
    for _, row in alias_df.iterrows()
}


# ==========================================================
# LOAD RANKED PLAYERS (ATP ONLY)
# ==========================================================
def build_rank_lookup():
    players = pd.read_csv(PLAYERS_FILE)

    lookup = {}

    for _, row in players.iterrows():
        if row["tour"] != "ATP":
            continue

        pid = row["player_id"]
        full = normalize_name(row["player_name"])
        parts = full.split()

        if len(parts) < 2:
            continue

        first = parts[0]
        last = " ".join(parts[1:])
        first_initial = first[0]

        # full surname
        lookup[f"{last} {first_initial}"] = pid

        # first surname token
        lookup[f"{last.split()[0]} {first_initial}"] = pid

        # last surname token
        lookup[f"{last.split()[-1]} {first_initial}"] = pid

    return lookup


ATP_RANK_LOOKUP = build_rank_lookup()


# ==========================================================
# CREATE NEW PLAYER ID (FOR QUALIFIERS / UNKNOWN PLAYERS)
# ==========================================================
def generate_new_player_id():
    """
    Creates persistent new IDs for players not in rankings.
    Starts at atp_9000 to never collide with ranked players.
    """

    existing_ids = set(alias_lookup.values())

    # also include ranking IDs
    if os.path.exists(PLAYERS_FILE):
        players = pd.read_csv(PLAYERS_FILE)
        existing_ids.update(players["player_id"].astype(str))

    n = 9000
    while True:
        candidate = f"atp_{n}"
        if candidate not in existing_ids:
            return candidate
        n += 1


# ==========================================================
# SAVE NEW ALIAS
# ==========================================================
def save_alias(scoreboard_name, player_id, canonical):
    global alias_df, alias_lookup

    new_row = pd.DataFrame([{
        "scoreboard_name": scoreboard_name,
        "player_id": player_id,
        "canonical_name": canonical
    }])

    new_row.to_csv(
        ALIAS_FILE,
        mode="a",
        header=not os.path.exists(ALIAS_FILE),
        index=False
    )

    alias_df.loc[len(alias_df)] = new_row.iloc[0]
    alias_lookup[normalize_name(scoreboard_name)] = player_id

    print(f"REGISTERED NEW PLAYER: {scoreboard_name} -> {player_id}")


# ==========================================================
# MAIN RESOLVER (THE IMPORTANT PART)
# ==========================================================
def get_atp_player_id(scoreboard_name: str):

    if pd.isna(scoreboard_name) or scoreboard_name.strip() == "":
        return None

    norm = normalize_name(scoreboard_name)

    # --------------------------------------------------
    # 1) ALREADY KNOWN PLAYER (FAST PATH)
    # --------------------------------------------------
    pid = alias_lookup.get(norm)
    if pid:
        return pid

    # --------------------------------------------------
    # 2) TRY TO MATCH RANKED PLAYER
    # --------------------------------------------------
    parts = norm.split()

    if len(parts) >= 2:
        last = " ".join(parts[:-1])
        first_initial = parts[-1][0]
        key = f"{last} {first_initial}"

        pid = ATP_RANK_LOOKUP.get(key)
        if pid:
            save_alias(scoreboard_name, pid, key)
            return pid

    # --------------------------------------------------
    # 3) BRAND NEW HUMAN (QUALIFIER / CHALLENGER)
    # --------------------------------------------------
    new_id = generate_new_player_id()

    # canonical just for debugging reference
    canonical = norm

    save_alias(scoreboard_name, new_id, canonical)

    return new_id