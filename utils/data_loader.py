import io
import json
import os

import pandas as pd
import requests
import streamlit as st

SIRC_KEYWORDS = ["sotheby", "sothebys", "sotheby's"]
CSV_FOLDER_ID = "1O5QYugSiRdV9GnHzEQCCXXeLsYA7-ivM"
XLSX_FILE_ID = "17bkeJBE7iqX3z2WN1pXW3FJFlbm9DwjU"
DIANE_FOLDER_ID = "1vjbD4wSeWVTPznf28F-rqv8ekM_dctJq"

# Known CSV file IDs from the CSV files folder (populated from Drive scan)
KNOWN_CSV_IDS = [
    "1Zv9cVEAbXbxDdFKMbLtRn3-B6BXPPHfe",
    "1Q0qFLBE_HDba6B7GVYjboZCoeGCvGq81",
    "1FCuYwDadblPT7rna7vWVF6iTK20EZXvb",
    "10HcQUcvQVYTWW4pRCVFTZMXxJagZ5t-4",
    "1PeqKmjES86ZemODVu_hu7hX9Ip0vAtcc",
    "1rn_wVrnp27SX3sLwE2cbN6bNw44315cK",
    "137ueIKiXqcaZnx3daEqKxt5_sQMgJVRQ",
    "1RBICmp8q3thLcndrKHyACzCq8DDGYHnZ",
    "1gzNRZ-s6WgnnVWdIbQfozbDOPe02yoi6",
    "1upgcERnlZu87bVSjSvpQZBIf-RhjsT8k",
    "1dRSFMWHj9MT2Rb5DOtoehqCozsgHl-0t",
    "19tkarjjtUulZ2gGSUEhakt2eQW2WEC3c",
    "1KX-9ELCibJKMZxxurCKfRYyeJmk7adhN",
    "1FwA5GVasu_x6bJDj0Z58B1Dzm8zjy8Ky",
    "17876w-tg93ohEdTuDAcGJTH9CKcFcIqr",
    "1IoYWX6gm0HODE5Q2virf18OJDPZNWSa_",
    "1zyxo3nf40ll3gq1PAl6IHiH7G79vnMHE",
    "1cuhICE-K5XBJINuyOr_HS2XkwfqqFCkh",
    "1EMi3qhCTxHZVgzud9B_Uj7Ekq-fUDBHs",
    "1lVn5HcoUoUVgwC0anjF_bYPfOTkk49hK",
    "16-Bal3YHJUY6RQFvC8STZhKffJLeL1S-",
    "1MJ2ckIiQ1EVg7Ko7zjXtGgT7iws-KRDt",
    "18otFbYGDP-80_1xPQ9du9IrSqxwUBavF",
    "1HO5UZJuN09-7a5wwAR7XwjFVewjh2_o4",
    "1DYf7rwMRNX_XO34vyRoWb0hS07KuQIwX",
    "12vqLJnLY70TrgDxdCbsTQrs8uhmFMXu2",
    "12SYljL4xMP-Ue3x8AyW-vKBT36LGjB86",
    "1T1EuBqOG4AkNMbvIwEJi9Xqf_iIS6qiY",
    "1lWfPWYQ3gmQS0dh2QwM3H0eOTBoJgr4x",
    "1X1HhZUFa3vXHJrzSDXJPAR4JyWIoQ6uL",
    # Root-level CSVs
    "1PZftBll40yy5ZpiHMlu9Hvn6BMkiHE7Q",
    "1dloeKPMMJiRNwqVaHSCeHzTjRdDM3rpu",
    "1E4xeNK2kUlfOJ7nUuXgXbBFwOJG6BIUl",
    "12YvK0W3m09vKL2uRjLcPE0OZZhXkNMLF",
    "1yUlF0mrraVnhFSIMz0Iulretrbe6LRZy",
    "1Ic_YCxq4sKILI8HBCYUnwuJD9OMD5iga",
    "1ycQYygXoHi9SSu_-cYRfi5J1CdXcrGW_",
    "1S3G2Y_Lyh44oV8FlyyvhG_YliFK3akoB",
]


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

    # Merge both sub-area columns — "Sub Area" is primary, "S/A" fills gaps
    if "Sub Area" in df.columns or "S/A" in df.columns:
        sub = df.get("Sub Area", pd.Series(dtype=str))
        sa  = df.get("S/A",       pd.Series(dtype=str))
        df["sub_area"] = sub.combine_first(sa)
        df.drop(columns=[c for c in ["Sub Area", "S/A"] if c in df.columns], inplace=True)

    # Expand abbreviated city names to full names
    CITY_MAP = {
        "WEST VANC":   "WEST VANCOUVER",
        "NORTH VANC":  "NORTH VANCOUVER",
        "MAPLERIDGE":  "MAPLE RIDGE",
        "NEW WEST":    "NEW WESTMINSTER",
        "PORT COQ":    "PORT COQUITLAM",
        "PITT":        "PITT MEADOWS",
        "TSAWW":       "TSAWWASSEN",
        "HARRISONHS":  "HARRISON HOT SPRINGS",
        "HARRISONMI":  "HARRISON MILLS",
        "HALFMOON":    "HALFMOON BAY",
        "PENDER HRB":  "PENDER HARBOUR",
        "PENDER ISL":  "PENDER ISLAND",
        "BRACKENDAL":  "BRACKENDALE",
        "SUNSHINE V":  "SUNSHINE VALLEY",
        "SALTSPRING":  "SALT SPRING ISLAND",
        "SARDIS GRN":  "SARDIS GREEN",
        "SARDIS CRV":  "SARDIS CURVE",
        "NORTH BLAC":  "NORTH BLACKTOP",
        "MTWOODSIDE":  "MT WOODSIDE",
        "CADREB OTH":  "OTHER",
    }
    if "city" in df.columns:
        df["city"] = df["city"].str.strip().str.upper().replace(CITY_MAP)

    for col in ["orig_price", "list_price", "sold_price"]:
        if col in df.columns:
            df[col] = _parse_price(df[col])

    for col in ["list_date", "sold_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=False)

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


def _get_api_key() -> str:
    try:
        return st.secrets["google_drive"]["api_key"]
    except Exception:
        return ""


def _download_file_with_api_key(file_id: str, api_key: str) -> bytes:
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={api_key}"
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    return response.content


def _list_csv_files_with_api_key(folder_id: str, api_key: str) -> list:
    files = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and mimeType='text/csv' and trashed=false",
            "fields": "nextPageToken, files(id, name)",
            "key": api_key,
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        files.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return files


# ── Public API ─────────────────────────────────────────────────────────────

PARQUET_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "combined_data.parquet")


@st.cache_data(ttl=1800, show_spinner="Loading market data…")
def load_data() -> pd.DataFrame:
    """
    Load and return the combined, cleaned DataFrame from the bundled Parquet file.
    Run sync_data.py to refresh from Google Drive.
    """
    frames = []

    if os.path.exists(PARQUET_PATH):
        df = pd.read_parquet(PARQUET_PATH)
        return _clean(df)

    # Fallback: local data/ directory (CSV/XLSX)
    data_dir = os.path.dirname(PARQUET_PATH)
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
