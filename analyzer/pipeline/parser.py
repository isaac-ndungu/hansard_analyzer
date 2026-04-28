import re
import logging
from pathlib import Path
from datetime import datetime

import pdfplumber

from config import SECTION_HEADINGS

logger = logging.getLogger(__name__)


# Speaker Pattern

SPEAKER_PATTERN = re.compile(
    r"Hon\.\s+([^(]+?)\s*\(([^,)]+),\s*([^)]+)\)\s*:\s*(.*?)(?=Hon\.\s+[^(]+\(|$)",
    re.DOTALL,
)

SECTION_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(h) for h in SECTION_HEADINGS) + r")\s*$",
    re.MULTILINE | re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+(\d{1,2})\s+(\w+),?\s+(\d{4})",
    re.IGNORECASE,
)

VOLUME_PATTERN = re.compile(r"Volume\s+(\d+)", re.IGNORECASE)
ISSUE_PATTERN = re.compile(r"(?:No\.|Issue)\s*(\d+)", re.IGNORECASE)


# Text Extraction

def extract_text(pdf_path: Path) -> str:
    """
    Raw text extraction from a PDF file.
    """
    pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
    except Exception as error:
        logger.error("Failed to extract text from %s: %s", pdf_path.name, error)
        return ""

    return "\n".join(pages)


# Speaker Parsing

def parse_speakers(text: str) -> list[dict]:
    """
    Extracts all speaker entries from document text.
    Returns a list of dicts with keys: name, constituency, party, content.
    """
    if not text:
        return []

    speakers = []

    for match in SPEAKER_PATTERN.finditer(text):
        name = match.group(1).strip()
        constituency = match.group(2).strip()
        party = match.group(3).strip()
        content = match.group(4).strip()

        if not content:
            continue

        speakers.append({
            "name": name,
            "constituency": constituency,
            "party": party,
            "content": content,
        })

    return speakers


# Section Parsing

def parse_sections(text: str) -> list[dict]:
    """
    Identifies named sections within the document text.
    Returns a list of dicts with keys: title, content.
    """
    if not text:
        return []

    sections = []
    matches = list(SECTION_PATTERN.finditer(text))

    for index, match in enumerate(matches):
        title = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append({
            "title": title,
            "content": content,
        })

    return sections


# Document-Level Metadata

def _extract_date(text: str) -> str | None:
    match = DATE_PATTERN.search(text[:2000])
    if match is None:
        return None

    try:
        raw = f"{match.group(1)} {match.group(2)} {match.group(3)}"
        return datetime.strptime(raw, "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_volume(text: str) -> int | None:
    match = VOLUME_PATTERN.search(text[:2000])
    return int(match.group(1)) if match else None


def _extract_issue(text: str) -> int | None:
    match = ISSUE_PATTERN.search(text[:2000])
    return int(match.group(1)) if match else None


def _detect_chamber(text: str) -> str:
    if "senate" in text[:2000].lower():
        return "Senate"
    return "National Assembly"


# Full Document Parse

def parse_document(pdf_path: Path) -> dict:
    """
    Full parse of a single Hansard PDF.
    Returns a structured dict with: date, chamber, volume, issue, sections, speeches.
    Each speech includes the active section it was found under.
    """
    text = extract_text(pdf_path)

    if not text:
        logger.warning("No text extracted from %s", pdf_path.name)
        return {}

    sections = parse_sections(text)
    all_speakers = parse_speakers(text)

    speeches_with_sections = _assign_sections_to_speeches(text, sections, all_speakers)

    return {
        "date": _extract_date(text),
        "chamber": _detect_chamber(text),
        "volume": _extract_volume(text),
        "issue": _extract_issue(text),
        "pdf_path": str(pdf_path),
        "sections": sections,
        "speeches": speeches_with_sections,
    }


def _assign_sections_to_speeches(
    full_text: str,
    sections: list[dict],
    speakers: list[dict],
) -> list[dict]:
    """
    Matches each speech to the section it appeared under by comparing
    content position in the full document text.
    """
    section_boundaries = []

    for section in sections:
        title = section["title"]
        start_index = full_text.find(title)
        if start_index != -1:
            section_boundaries.append((start_index, title))

    section_boundaries.sort(key=lambda pair: pair[0])

    result = []

    for speech in speakers:
        content_index = full_text.find(speech["content"][:80])
        active_section = "UNKNOWN"

        for boundary_index, section_title in section_boundaries:
            if content_index >= boundary_index:
                active_section = section_title
            else:
                break

        result.append({**speech, "section": active_section})

    return result