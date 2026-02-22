import pandas as pd
import unicodedata

ATP_FILE = "data/atp_rankings.csv"
WTA_FILE = "data/wta_rankings.csv"
OUTPUT_FILE = "data/tennisplayers.csv"

TOP_N = 500

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

    # read names
    df["player_name"] = df["player"]

    # deterministic player_id (tour + rank)
    df["player_id"] = tour.lower() + "_" + df["rank"].astype(int).astype(str)

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