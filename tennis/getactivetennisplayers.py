import pandas as pd
import unicodedata

ATP_FILE = "atp_rankings.csv"
WTA_FILE = "wta_rankings.csv"
OUTPUT_FILE = "tennisplayers.csv"

TOP_N = 500


# ------------------------------------------------------------
# Name Normalization (CRITICAL for later match log matching)
# ------------------------------------------------------------
def normalize_name(name: str) -> str:
    if pd.isna(name):
        return ""

    # remove accents (Djoković -> Djokovic)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # remove punctuation differences
    name = (
        name.replace(".", "")
            .replace(",", "")
            .replace("'", "")
            .replace("-", " ")
            .strip()
    )

    # collapse double spaces
    name = " ".join(name.split())

    return name


# ------------------------------------------------------------
def process_rankings(file, tour):
    print(f"Reading {file}")

    df = pd.read_csv(file)

    # Explicit columns (based on your sample)
    df = df[["rank", "player", "points", "country"]].copy()

    # Ensure numeric rank
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df = df.dropna(subset=["rank"])

    # sort and keep top 500
    df = df.sort_values("rank").head(TOP_N)

    # normalize names
    df["player_name"] = df["player"].apply(normalize_name)

    # deterministic player_id
    df["player_id"] = df["rank"].astype(int).astype(str)
    df["player_id"] = tour.lower() + "_" + df["player_id"]

    df["tour"] = tour

    return df[["player_id", "player_name", "tour", "rank", "points", "country"]]


# ------------------------------------------------------------
def main():
    print("Processing ATP rankings...")
    atp = process_rankings(ATP_FILE, "ATP")

    print("Processing WTA rankings...")
    wta = process_rankings(WTA_FILE, "WTA")

    combined = pd.concat([atp, wta], ignore_index=True)

    combined.to_csv(OUTPUT_FILE, index=False)

    print("\nSUCCESS")
    print(f"Total players: {len(combined)}")
    print(f"ATP: {len(atp)}")
    print(f"WTA: {len(wta)}")
    print("Saved to tennisplayers.csv")


if __name__ == "__main__":
    main()
