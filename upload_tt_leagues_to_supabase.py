import os
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BUCKET_NAME = "bmp-data"

DATA_DIR = os.path.join("tabletennis", "data")

FILES_TO_UPLOAD = [
    # Per-league h2h indexes (pre-built slim pickles, replaces matchlog CSVs)
    "tt_elite_h2h_index.pkl.gz",
    "tt_czech_h2h_index.pkl.gz",
    "tt_setka_h2h_index.pkl.gz",
    "tt_cup_h2h_index.pkl.gz",
    # H2H summary CSVs
    "tt_elite_h2h_summary.csv",
    "tt_czech_h2h_summary.csv",
    "tt_setka_h2h_summary.csv",
    "tt_cup_h2h_summary.csv",
    # Schedule CSVs
    "tt_elite_schedule.csv",
    "tt_czech_schedule.csv",
    "tt_setka_schedule.csv",
    "tt_cup_schedule.csv",
    # Matchlog CSVs removed — no longer downloaded at runtime.
    # buildallleagues.py reads them locally to build the slim pickles.
    # If you want to keep them in Supabase as a backup, you can add them
    # back here, but they will count against your egress quota if downloaded.
]

def upload_file(supabase, filepath, filename):
    with open(filepath, "rb") as f:
        data = f.read()

    # Determine content type
    if filename.endswith(".csv"):
        content_type = "text/csv"
    elif filename.endswith(".pkl.gz"):
        content_type = "application/gzip"
    else:
        content_type = "application/octet-stream"

    # Try to remove existing file first (upsert workaround)
    try:
        supabase.storage.from_(BUCKET_NAME).remove([filename])
    except Exception:
        pass  # File didn't exist yet, that's fine

    supabase.storage.from_(BUCKET_NAME).upload(
        path=filename,
        file=data,
        file_options={"content-type": content_type}
    )
    print(f"Uploaded: {filename}")

if __name__ == "__main__":
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    for filename in FILES_TO_UPLOAD:
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            upload_file(supabase, filepath, filename)
        else:
            print(f"Skipped (not found): {filename}")

    print("Supabase upload complete.")