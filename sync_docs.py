"""
Builds the AI assistant knowledge base by:
1. Downloading regulatory PDFs from Google Drive
2. Crawling BCFSA website (real-estate sections)
3. Extracting and chunking all text
4. Saving to data/docs/knowledge_base.json

Run manually:
    cd ~/sirc-intelligence
    source venv/bin/activate
    export GDRIVE_API_KEY='your-key'
    python3 sync_docs.py

Also runs automatically via GitHub Actions daily.
"""
import io
import json
import os
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

API_KEY = os.environ.get("GDRIVE_API_KEY", "")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "docs", "knowledge_base.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
CHUNK_SIZE = 400  # words per chunk

# ── Google Drive documents ──────────────────────────────────────────────────
DRIVE_DOCS = [
    ("GVR Constitution & Bylaws (March 2023)",              "1WyfaSfaAHxoccwbr41NME2wT9mh445_v", "pdf"),
    ("From Conversation to Commission (GVR)",               "1WjzAs2AJB5c5C3OGrlowJQr5-zEx-sXv", "pdf"),
    ("Competition Act - Real Estate Guide (CREA)",          "1I1i_-JquI8vqV3CC8DAGlPdxdv0Nk6Gw", "pdf"),
    ("What is Misconduct (GVR)",                            "1OVh0PjptPi8M6qnbDNrEb4r3XOi1EQqI", "pdf"),
    ("REALTOR Code of Ethics (April 2023)",                 "1duR-06DrE1r_TmG79zEJmT32Yuu6z4ap", "pdf"),
    ("SIRC Brand Standards 2026",                           "1sIV4gScPBo2eeZA6AQe_yz92ZSesC6xk", "pdf"),
    ("FINTRAC Compliance Manual (SIRC)",                    "1GCvObiTan141WtTDbcV4U4LoXvSpqYBP", "pdf"),
    ("Wire Transfer Instructions 2025 (SIRC)",              "1LrZrd_xGe1c4OWhsWxdvRzmOSwbRBuxy", "pdf"),
    ("BCFSA Regulation 209-2021",                           "1EailEUPqVSdH5vnaocvevuFwf36SHEIA", "pdf"),
    ("BCFSA Real Estate Services Act Regulation 506-2004",  "1M0uv8Fj94WZ3kO2pW5j5fQyrbCUlOEv7", "pdf"),
]

# ── BCFSA website sections to crawl ────────────────────────────────────────
BCFSA_BASE = "https://www.bcfsa.ca"
BCFSA_SEED_URLS = [
    "/industry-resources/real-estate-professional-resources",
    "/industry-resources/real-estate-professional-resources/knowledge-base/practice-resources/managing-broker-tools-support-your-team",
    "/industry-resources/real-estate-professional-resources/knowledge-base/practice-resources/2025-real-estate-brokerage-data-call",
    "/about-us/legislation",
    "/about-us/news/real-estate-bulletin",
    "/public-resources/real-estate",
    "/public-resources/real-estate/home-buyer-rescission-period",
    "/public-resources/real-estate/consumer-resources",
    "/public-protection/decisions/real-estate-decisions",
]

# URL patterns to follow when crawling BCFSA
BCFSA_FOLLOW_PATTERNS = [
    "/industry-resources/real-estate",
    "/about-us/news/blog",
    "/about-us/news/real-estate-bulletin",
    "/about-us/legislation",
    "/public-resources/real-estate",
    "/public-protection",
    "/knowledge-base",
    "/practice-resources",
    "/managing-broker",
]

# ── CREA website sections to crawl ─────────────────────────────────────────
CREA_BASE = "https://www.crea.ca"
CREA_SEED_URLS = [
    "/standards-programs/realtor-code/",
    "/standards-programs/trademark-protection-competition/",
    "/standards-programs/programs/",
    "/standards-programs/reputation/learning-development/",
    "/media-hub/publications/",
    "/media-hub/news/",
    "/media-hub/blogs/",
    "/legal/",
    "/advocacy/political-advocacy/",
    "/housing-market-stats/canadian-housing-market-stats/",
]

# URL patterns to follow when crawling CREA
CREA_FOLLOW_PATTERNS = [
    "/standards-programs/",
    "/media-hub/",
    "/legal/",
    "/advocacy/",
    "/housing-market-stats/",
    "/cafe/",
]

CREA_SKIP_PATTERNS = [
    "/fr/", "/careers/", "/contact/", "/search/", "/privacy/",
    "/technology/", "/realtor-ca-for-canadians/", "/hpi-tool/",
    "/national-price-map/", "/podcast-guest-application/",
]

# PDFs to always fetch directly (not relying on crawl discovery)
CREA_DIRECT_PDFS = [
    ("CREA: REALTOR® Code (Full)", "https://www.crea.ca/files/REALTOR-Code-Eng.pdf"),
]

# ── Helpers ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, source: str, url: str = "") -> list[dict]:
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if len(chunk.strip()) > 80:
            chunks.append({
                "source": source,
                "url": url,
                "chunk_id": i // CHUNK_SIZE,
                "text": chunk,
            })
    return chunks


def extract_pdf_text(raw_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_bytes))
    return " ".join(page.extract_text() or "" for page in reader.pages)


def extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "form", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|body"))
    target = main if main else soup
    return target.get_text(separator=" ", strip=True)


def download_drive_file(file_id: str) -> bytes:
    r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={API_KEY}",
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def is_relevant_bcfsa_url(url: str) -> bool:
    parsed = urlparse(url)
    if "bcfsa.ca" not in parsed.netloc:
        return False
    path = parsed.path
    # Skip non-content pages
    skip = ["/about-us/careers", "/about-us/foi", "/find-professional",
            "/contact", "/privacy", "/terms", "/media/", "/node/65",
            "credit-union", "insurance", "pension", "trust", "mortgage-broker"]
    if any(s in path for s in skip):
        return False
    return any(p in path for p in BCFSA_FOLLOW_PATTERNS)


def is_relevant_crea_url(url: str) -> bool:
    parsed = urlparse(url)
    if "crea.ca" not in parsed.netloc:
        return False
    path = parsed.path
    if any(s in path for s in CREA_SKIP_PATTERNS):
        return False
    return any(p in path for p in CREA_FOLLOW_PATTERNS)


# ── Google Drive section ────────────────────────────────────────────────────

def process_drive_docs() -> list[dict]:
    chunks = []
    if not API_KEY:
        print("  Skipping Drive docs (no API key)")
        return chunks

    for title, file_id, ftype in DRIVE_DOCS:
        try:
            raw = download_drive_file(file_id)
            if ftype == "pdf":
                text = extract_pdf_text(raw)
            else:
                text = raw.decode("utf-8", errors="replace")
            doc_chunks = chunk_text(text, title, url="")
            chunks.extend(doc_chunks)
            print(f"  ✓ {title}: {len(doc_chunks)} chunks")
        except Exception as e:
            print(f"  ✗ {title}: {e}")
    return chunks


# ── BCFSA crawler ───────────────────────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 20):
    """Fetch a URL with retries. Returns None on failure."""
    for attempt in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            return r
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
            else:
                print(f"  ✗ fetch error {url}: {e}")
    return None


def crawl_bcfsa() -> list[dict]:
    visited: set[str] = set()
    to_visit: list[str] = [BCFSA_BASE + path for path in BCFSA_SEED_URLS]
    chunks: list[dict] = []
    pdf_urls: set[str] = set()

    print(f"  Starting crawl with {len(to_visit)} seed URLs")

    while to_visit and len(visited) < 120:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        print(f"  → fetching ({len(visited)}/{len(to_visit)+len(visited)}): {url[:80]}")
        time.sleep(0.5)

        r = _fetch_url(url)
        if r is None:
            continue

        if r.status_code != 200:
            print(f"  ✗ HTTP {r.status_code}: {url}")
            continue

        content_type = r.headers.get("content-type", "")

        if "pdf" in content_type:
            try:
                text = extract_pdf_text(r.content)
                title = f"BCFSA Document: {url.split('/')[-1]}"
                doc_chunks = chunk_text(text, title, url=url)
                chunks.extend(doc_chunks)
                print(f"  ✓ PDF {url.split('/')[-1]}: {len(doc_chunks)} chunks")
            except Exception as e:
                print(f"  ✗ PDF parse error {url}: {e}")
            continue

        if "html" not in content_type:
            print(f"  – skipping content-type '{content_type[:40]}': {url}")
            continue

        try:
            soup = BeautifulSoup(r.text, "lxml")
            page_title_tag = soup.find("h1") or soup.find("title") or soup.find("h2")
            page_title = page_title_tag.get_text(strip=True) if page_title_tag else url.split("/")[-1]
            source_label = f"BCFSA: {page_title}"

            text = extract_html_text(r.text)
            word_count = len(text.split())
            if word_count > 80:
                doc_chunks = chunk_text(text, source_label, url=url)
                chunks.extend(doc_chunks)
                print(f"  ✓ {source_label[:65]}: {len(doc_chunks)} chunks ({word_count} words)")
            else:
                print(f"  – too short ({word_count} words): {source_label[:60]}")

            # Find links to follow
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                full_url = urljoin(url, href).split("?")[0].split("#")[0]
                if full_url in visited or full_url in to_visit:
                    continue
                if full_url.endswith(".pdf"):
                    pdf_urls.add(full_url)
                elif is_relevant_bcfsa_url(full_url):
                    to_visit.append(full_url)

        except Exception as e:
            print(f"  ✗ parse error {url}: {e}")

    # Download discovered PDFs
    print(f"  Discovered {len(pdf_urls)} PDF links")
    for pdf_url in list(pdf_urls)[:20]:
        if pdf_url in visited:
            continue
        visited.add(pdf_url)
        time.sleep(0.5)
        r = _fetch_url(pdf_url, timeout=30)
        if r is None or r.status_code != 200:
            continue
        try:
            text = extract_pdf_text(r.content)
            title = f"BCFSA PDF: {pdf_url.split('/')[-1].replace('.pdf','').replace('-',' ').title()}"
            doc_chunks = chunk_text(text, title, url=pdf_url)
            chunks.extend(doc_chunks)
            print(f"  ✓ {title}: {len(doc_chunks)} chunks")
        except Exception as e:
            print(f"  ✗ PDF parse error {pdf_url}: {e}")

    return chunks


# ── CREA crawler ────────────────────────────────────────────────────────────

def crawl_crea() -> list[dict]:
    visited: set[str] = set()
    to_visit: list[str] = [CREA_BASE + path for path in CREA_SEED_URLS]
    chunks: list[dict] = []
    pdf_urls: set[str] = set()

    print(f"  Starting CREA crawl with {len(to_visit)} seed URLs")

    while to_visit and len(visited) < 80:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        print(f"  → fetching ({len(visited)}/{len(to_visit)+len(visited)}): {url[:80]}")
        time.sleep(0.5)

        r = _fetch_url(url)
        if r is None:
            continue

        if r.status_code != 200:
            print(f"  ✗ HTTP {r.status_code}: {url}")
            continue

        content_type = r.headers.get("content-type", "")

        if "pdf" in content_type:
            try:
                text = extract_pdf_text(r.content)
                title = f"CREA Document: {url.split('/')[-1]}"
                doc_chunks = chunk_text(text, title, url=url)
                chunks.extend(doc_chunks)
                print(f"  ✓ PDF {url.split('/')[-1]}: {len(doc_chunks)} chunks")
            except Exception as e:
                print(f"  ✗ PDF parse error {url}: {e}")
            continue

        if "html" not in content_type:
            continue

        try:
            soup = BeautifulSoup(r.text, "lxml")
            page_title_tag = soup.find("h1") or soup.find("title") or soup.find("h2")
            page_title = page_title_tag.get_text(strip=True) if page_title_tag else url.split("/")[-1]
            source_label = f"CREA: {page_title}"

            text = extract_html_text(r.text)
            word_count = len(text.split())
            if word_count > 80:
                doc_chunks = chunk_text(text, source_label, url=url)
                chunks.extend(doc_chunks)
                print(f"  ✓ {source_label[:65]}: {len(doc_chunks)} chunks ({word_count} words)")
            else:
                print(f"  – too short ({word_count} words): {source_label[:60]}")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                full_url = urljoin(url, href).split("?")[0].split("#")[0]
                if full_url in visited or full_url in to_visit:
                    continue
                if full_url.endswith(".pdf"):
                    pdf_urls.add(full_url)
                elif is_relevant_crea_url(full_url):
                    to_visit.append(full_url)

        except Exception as e:
            print(f"  ✗ parse error {url}: {e}")

    # Always fetch these PDFs directly (guaranteed inclusion)
    for title, pdf_url in CREA_DIRECT_PDFS:
        if pdf_url in visited:
            continue
        visited.add(pdf_url)
        time.sleep(0.5)
        r = _fetch_url(pdf_url, timeout=30)
        if r is None or r.status_code != 200:
            print(f"  ✗ direct PDF failed ({getattr(r,'status_code','?')}): {pdf_url}")
            continue
        try:
            text = extract_pdf_text(r.content)
            doc_chunks = chunk_text(text, title, url=pdf_url)
            chunks.extend(doc_chunks)
            print(f"  ✓ {title}: {len(doc_chunks)} chunks")
        except Exception as e:
            print(f"  ✗ PDF parse error {pdf_url}: {e}")

    # Download discovered PDFs
    print(f"  Discovered {len(pdf_urls)} CREA PDF links")
    for pdf_url in list(pdf_urls)[:15]:
        if pdf_url in visited:
            continue
        visited.add(pdf_url)
        time.sleep(0.5)
        r = _fetch_url(pdf_url, timeout=30)
        if r is None or r.status_code != 200:
            continue
        try:
            text = extract_pdf_text(r.content)
            title = f"CREA PDF: {pdf_url.split('/')[-1].replace('.pdf','').replace('-',' ').title()}"
            doc_chunks = chunk_text(text, title, url=pdf_url)
            chunks.extend(doc_chunks)
            print(f"  ✓ {title}: {len(doc_chunks)} chunks")
        except Exception as e:
            print(f"  ✗ PDF parse error {pdf_url}: {e}")

    return chunks


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("SIRC Intelligence — Document Knowledge Base Sync")
    print("=" * 60)

    all_chunks = []

    print("\n[1/3] Processing Google Drive regulatory documents...")
    drive_chunks = process_drive_docs()
    all_chunks.extend(drive_chunks)
    print(f"      {len(drive_chunks)} chunks from Drive documents")

    print("\n[2/3] Crawling BCFSA website...")
    bcfsa_chunks = crawl_bcfsa()
    all_chunks.extend(bcfsa_chunks)
    print(f"      {len(bcfsa_chunks)} chunks from BCFSA website")

    print("\n[3/3] Crawling CREA website...")
    crea_chunks = crawl_crea()
    all_chunks.extend(crea_chunks)
    print(f"      {len(crea_chunks)} chunks from CREA website")

    # Deduplicate by text content
    seen_texts = set()
    unique_chunks = []
    for chunk in all_chunks:
        key = chunk["text"][:200]
        if key not in seen_texts:
            seen_texts.add(key)
            unique_chunks.append(chunk)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(unique_chunks, f)

    print(f"\n✓ Knowledge base saved: {len(unique_chunks)} unique chunks")
    print(f"  Sources: {len(set(c['source'] for c in unique_chunks))} documents")
    print(f"  File: {OUTPUT_PATH}")
    print("\nNext: git add data/docs/knowledge_base.json && git commit -m 'Refresh knowledge base' && git push")
