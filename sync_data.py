"""
Run this script whenever you've added new CSV files to your Google Drive.
It downloads all data, merges it, deduplicates, and saves as data/combined_data.parquet.
Then commit and push to GitHub — Streamlit will pick up the new data automatically.

Usage:
    cd ~/sirc-intelligence
    source venv/bin/activate
    python3 sync_data.py
"""
import io
import os
import requests
import pandas as pd

API_KEY = os.environ.get("GDRIVE_API_KEY", "")
CSV_FOLDER_ID = "1O5QYugSiRdV9GnHzEQCCXXeLsYA7-ivM"
XLSX_FILE_ID = "17bkeJBE7iqX3z2WN1pXW3FJFlbm9DwjU"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "combined_data.parquet")


def download(file_id):
    r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={API_KEY}",
        timeout=180,
    )
    r.raise_for_status()
    return r.content


def list_subfolders(folder_id):
    folders, page_token = [], None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            "fields": "nextPageToken,files(id,name)",
            "key": API_KEY,
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        folders.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return folders


def list_csvs(folder_id):
    files, page_token = [], None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType='text/csv' and trashed=false",
            "fields": "nextPageToken,files(id,name,modifiedTime)",
            "key": API_KEY,
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        files.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    # Recurse into subfolders
    for subfolder in list_subfolders(folder_id):
        files.extend(list_csvs(subfolder["id"]))
    return files


if not API_KEY:
    print("ERROR: Set GDRIVE_API_KEY environment variable first.")
    print("  export GDRIVE_API_KEY='your-api-key'")
    exit(1)

frames = []

print("Downloading XLSX (historical data)...")
try:
    raw = download(XLSX_FILE_ID)
    xl = pd.read_excel(io.BytesIO(raw), dtype=str)
    frames.append(xl)
    print(f"  ✓ {len(xl):,} rows")
except Exception as e:
    print(f"  ✗ Failed: {e}")

print("Listing CSV files from Drive...")
csv_files = sorted(list_csvs(CSV_FOLDER_ID), key=lambda f: f["name"])
print(f"  Found {len(csv_files)} files")

for i, f in enumerate(csv_files):
    try:
        raw = download(f["id"])
        df = pd.read_csv(io.BytesIO(raw), dtype=str)
        frames.append(df)
        print(f"  ✓ {i+1}/{len(csv_files)}: {f['name']} — {len(df):,} rows")
    except Exception as e:
        print(f"  ✗ {i+1}/{len(csv_files)}: {f['name']} — {e}")

combined = pd.concat(frames, ignore_index=True)
print(f"\nTotal rows before dedup: {len(combined):,}")
combined = combined.drop_duplicates(subset=["ML #"], keep="last")
print(f"Total rows after dedup:  {len(combined):,}")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
combined.to_parquet(OUTPUT_PATH, index=False)
print(f"\n✓ Saved to {OUTPUT_PATH}")
print("\nNext steps:")
print("  git add data/combined_data.parquet")
print("  git commit -m 'Refresh data'")
print("  git push")
