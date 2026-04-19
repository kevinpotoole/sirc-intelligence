import io
import json
import os
import re

import pandas as pd
import streamlit as st

SIRC_KEYWORDS = ["sotheby", "sothebys", "sotheby's"]
CSV_FOLDER_ID = "1O5QYugSiRdV9GnHzEQCCXXeLsYA7-ivM"
XLSX_FILE_ID = "17bkeJBE7iqX3z2WN1pXW3FJFlbm9DwjU"


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_price(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.strip()
        .replace("", "0")
        .pipe(pd.to_numeric, errors="coerce")
    )


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "ML #": "mls_number",
        "ML \\#": "mls_number",
        "Address": "address",
        "City": "city",
        "S/A": "sub_area",
        "Prop Type": "prop_type",
        "Type": "property_type",
        "Orig Price": "orig_price",
        "List Price": "list_price",
        "List Date": "list_date",
        "Sold Price": "sold_price",
        "Sold Date": "sold_date",
        "CDOM": "days_on_market",
        "Status": "status",
        "Commission": "commission",
        "Firm1Code - Ofc Name": "listing_office",
        "List Dsg 1 - AgntFName": "listing_agent",
        "Buy Brok 1 - Ofc Name": "buying_office",
        "Buy Agt 1 - AgntFName": "buying_agent",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for col in ["orig_price", "list_price", "sold_price"]:
        if col in df.columns:
            df[col] = _parse_price(df[col])

    for col in ["list_date", "sold_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "days_on_market" in df.columns:
        df["days_on_market"] = pd.to_numeric(df["days_on_market"], errors="coerce")

    if "mls_number" in df.columns:
        df["mls_number"] = df["mls_number"].astype(str).str.strip()

    if "sold_price" in df.columns and "list_price" in df.columns:
        df["list_to_sale_ratio"] = (df["sold_price"] / df["list_price"]).round(4)

    if "sold_date" in df.columns:
        df["sold_year"] = df["sold_date"].dt.year
        df["sold_month"] = df["sold_date"].dt.month
        df["sold_quarter"] = df["sold_date"].dt.quarter
        df["sold_ym"] = df["sold_date"].dt.to_period("M").astype(str)

    for col in ["listing_office", "buying_office"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").str.strip()

    for col in ["listing_agent", "buying_agent"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").str.strip()
            df[col] = df[col].str.replace(r"\s*PREC\*?", "", regex=True).str.strip()

    if "listing_office" in df.columns:
        lo = df["listing_office"].str.lower()
        df["is_sirc_listing"] = lo.apply(lambda x: any(k in x for k in SIRC_KEYWORDS))
    if "buying_office" in df.columns:
        bo = df["buying_office"].str.lower()
        df["is_sirc_buying"] = bo.apply(lambda x: any(k in x for k in SIRC_KEYWORDS))

    df["is_sirc_involved"] = df.get("is_sirc_listing", False) | df.get("is_sirc_buying", False)

    return df


def _build_drive_service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_raw = st.secrets["google_drive"]["credentials"]
        creds_dict = json.loads(creds_raw)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _download_file_bytes(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.seek(0)
    return buf.read()


def _list_csv_files(service, folder_id: str) -> list[dict]:
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='text/csv' and trashed=false",
            fields="nextPageToken, files(id, name, modifiedTime)",
            pageToken=page_token,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


# ── Public API ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner="Loading market data…")
def load_data() -> pd.DataFrame:
    """
    Load and return the combined, cleaned DataFrame.
    Tries Google Drive first; falls back to local data/ folder.
    """
    service = _build_drive_service()
    frames = []

    if service:
        # Load historical XLSX
        try:
            raw = _download_file_bytes(service, XLSX_FILE_ID)
            xl = pd.read_excel(io.BytesIO(raw), dtype=str)
            frames.append(xl)
        except Exception as e:
            st.warning(f"Could not load XLSX from Drive: {e}")

        # Load all CSVs from the folder
        try:
            csv_folder = st.secrets["google_drive"].get("csv_folder_id", CSV_FOLDER_ID)
            files = _list_csv_files(service, csv_folder)
            for f in files:
                try:
                    raw = _download_file_bytes(service, f["id"])
                    df = pd.read_csv(io.BytesIO(raw), dtype=str)
                    frames.append(df)
                except Exception:
                    pass
        except Exception as e:
            st.warning(f"Could not load CSVs from Drive: {e}")

    else:
        # Fallback: local data/ directory
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        if os.path.isdir(data_dir):
            for fname in os.listdir(data_dir):
                fpath = os.path.join(data_dir, fname)
                try:
                    if fname.endswith(".csv"):
                        frames.append(pd.read_csv(fpath, dtype=str))
                    elif fname.endswith((".xlsx", ".xls")):
                        frames.append(pd.read_excel(fpath, dtype=str))
                except Exception:
                    pass

    if not frames:
        st.error("No data found. Please configure Google Drive credentials or add files to the data/ folder.")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Deduplicate by MLS number if present
    if "ML #" in df.columns or "mls_number" in df.columns:
        key = "ML #" if "ML #" in df.columns else "mls_number"
        df = df.drop_duplicates(subset=[key], keep="last")

    df = _clean(df)
    return df


def refresh_data():
    st.cache_data.clear()


def sirc_name_variants(df: pd.DataFrame) -> list[str]:
    """Return all unique SIRC office name spellings in the data."""
    offices = set()
    for col in ["listing_office", "buying_office"]:
        if col in df.columns:
            mask = df[col].str.lower().apply(lambda x: any(k in x for k in SIRC_KEYWORDS))
            offices.update(df.loc[mask, col].unique())
    return sorted(offices)
