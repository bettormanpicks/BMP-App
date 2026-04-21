import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'
FOLDER_ID = '1RU8FQu-03gMFGTMBwtNjDxoQvK4jPct3'  # paste your folder ID here

DATA_DIR = os.path.join("tabletennis", "data")

FILES_TO_UPLOAD = [
    ("tt_elite_matchlogs.csv", "text/csv"),
    ("tt_czech_matchlogs.csv", "text/csv"),
    ("tt_setka_matchlogs.csv", "text/csv"),
    ("tt_cup_matchlogs.csv", "text/csv"),
    ("tt_elite_h2h_summary.csv", "text/csv"),
    ("tt_czech_h2h_summary.csv", "text/csv"),
    ("tt_setka_h2h_summary.csv", "text/csv"),
    ("tt_cup_h2h_summary.csv", "text/csv"),
    ("tt_elite_schedule.csv", "text/csv"),
    ("tt_czech_schedule.csv", "text/csv"),
    ("tt_setka_schedule.csv", "text/csv"),
    ("tt_cup_schedule.csv", "text/csv"),
    ("tt_all_schedule.csv", "text/csv"),
    ("tt_all_h2h_index.pkl.gz", "application/gzip"),
]

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_file(service, filepath, filename, mime_type):
    # Check if file already exists in folder
    results = service.files().list(
        q=f"name='{filename}' and '{FOLDER_ID}' in parents and trashed=false",
        fields="files(id, name)").execute()
    files = results.get('files', [])

    media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)

    if files:
        # Update existing file
        file_id = files[0]['id']
        service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        print(f"Updated: {filename}")
    else:
        # Create new file
        file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
        service.files().create(
            body=file_metadata,
            media_body=media
        ).execute()
        print(f"Uploaded: {filename}")

if __name__ == "__main__":
    service = get_drive_service()
    for filename, mime_type in FILES_TO_UPLOAD:
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            upload_file(service, filepath, filename, mime_type)
        else:
            print(f"Skipped (not found): {filename}")
    print("Drive upload complete.")