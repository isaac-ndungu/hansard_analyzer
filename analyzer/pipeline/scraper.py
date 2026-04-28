import re
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import HANSARD_BASE_URL, PDF_DIR

logger = logging.getLogger(__name__)


# HTTP Session

def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "HansardAnalyzer/1.0 (civic research tool)"})
    return session


# Hansard Discovery

def get_available_hansards(from_date: str, to_date: str) -> list[dict]:
    """
    Scrapes parliament.go.ke and returns metadata for all Hansard documents
    published within the given date range.

    Each result dict contains: date, url, volume, issue, chamber.
    """
    session = _build_session()

    try:
        response = session.get(HANSARD_BASE_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        logger.error("Failed to fetch Hansard listing: %s", error)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    available = []

    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if not href.lower().endswith(".pdf"):
            continue

        metadata = _extract_metadata_from_link(link, href)

        if metadata is None:
            continue

        try:
            doc_date = datetime.strptime(metadata["date"], "%Y-%m-%d")
        except ValueError:
            continue

        if from_dt <= doc_date <= to_dt:
            available.append(metadata)

    return available


def _extract_metadata_from_link(link, href: str) -> dict | None:
    """
    Parses a PDF anchor tag and returns structured metadata,
    or None if the link cannot be interpreted as a Hansard document.
    """
    text = link.get_text(strip=True)

    date_match = re.search(r"(\d{1,2})[^\d]+(\w+)[^\d]+(\d{4})", text)
    if date_match is None:
        return None

    try:
        raw_date = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
        parsed_date = datetime.strptime(raw_date, "%d %B %Y")
        date_str = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return None

    volume_match = re.search(r"Vol(?:ume)?\.?\s*(\d+)", text, re.IGNORECASE)
    issue_match = re.search(r"(?:No|Issue)\.?\s*(\d+)", text, re.IGNORECASE)

    chamber = "Senate" if "senate" in href.lower() or "senate" in text.lower() else "National Assembly"

    full_url = href if href.startswith("http") else f"https://parliament.go.ke{href}"

    return {
        "date": date_str,
        "url": full_url,
        "volume": int(volume_match.group(1)) if volume_match else None,
        "issue": int(issue_match.group(1)) if issue_match else None,
        "chamber": chamber,
    }


# PDF Download

def download_hansard(url: str, save_path: Path) -> Path | None:
    """
    Downloads a single Hansard PDF to the given path.
    Returns the path on success, or None if the download failed.
    """
    if save_path.exists():
        logger.info("Already downloaded: %s", save_path.name)
        return save_path

    session = _build_session()

    try:
        response = session.get(url, timeout=60, stream=True)
        response.raise_for_status()
    except requests.RequestException as error:
        logger.error("Download failed for %s: %s", url, error)
        return None

    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
        logger.warning("Unexpected content type '%s' for URL: %s", content_type, url)
        return None

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=8192):
            pdf_file.write(chunk)

    logger.info("Downloaded: %s", save_path.name)
    return save_path


# Sync Orchestration

def sync_hansards(from_date: str | None = None) -> list[Path]:
    """
    Downloads all Hansard PDFs that have not yet been saved locally.
    Defaults to syncing from the start of the current year if no date is given.
    """
    if from_date is None:
        from_date = f"{datetime.utcnow().year}-01-01"

    to_date = datetime.utcnow().strftime("%Y-%m-%d")

    logger.info("Scanning for Hansards from %s to %s", from_date, to_date)

    available = get_available_hansards(from_date, to_date)

    if not available:
        logger.info("No Hansard documents found in the given date range.")
        return []

    downloaded_paths = []

    for document in available:
        filename = _build_filename(document)
        save_path = PDF_DIR / filename
        result = download_hansard(document["url"], save_path)

        if result is not None:
            downloaded_paths.append(result)

    logger.info("Sync complete. %d file(s) downloaded.", len(downloaded_paths))
    return downloaded_paths


def _build_filename(document: dict) -> str:
    """
    Constructs a deterministic filename from document metadata.
    Example: national_assembly_2026-04-14_vol25_no8.pdf
    """
    chamber_slug = document["chamber"].lower().replace(" ", "_")
    date_str = document["date"]
    volume_part = f"_vol{document['volume']}" if document["volume"] else ""
    issue_part = f"_no{document['issue']}" if document["issue"] else ""
    return f"{chamber_slug}_{date_str}{volume_part}{issue_part}.pdf"