import re
import logging
from pathlib import Path
from datetime import datetime

import pdfplumber

from config import SECTION_HEADINGS, ROMAN_NUMERALS, PARLIAMENT_NAMES

logger = logging.getLogger(__name__)


# Speaker Patterns


_SPEECH_LOOKAHEAD = r"(?=Hon\.\s+(?:\([^)]+\)\s+)?[^(\n]+\(|The (?:Temporary )?Speaker\s*\(|$)"

SPEAKER_PATTERN = re.compile(
    r"Hon\.\s+([^(\n]+?)\s*\(([^,)]+),\s*([^)]+)\)\s*:\s*(.*?)" + _SPEECH_LOOKAHEAD,
    re.DOTALL,
)

TITLED_SPEAKER_PATTERN = re.compile(
    r"Hon\.\s+\(([^)]+)\)\s+([^(\n]+?)\s*\(([^,)]+),\s*([^)]+)\)\s*:\s*(.*?)" + _SPEECH_LOOKAHEAD,
    re.DOTALL,
)

SECTION_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(h) for h in SECTION_HEADINGS) + r")\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Ordinal suffix (st, nd, rd, th) is optional — real PDFs use "11th March"
DATE_PATTERN = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+),?\s+(\d{4})",
    re.IGNORECASE,
)

# Volume uses Roman numerals: "Vol. V No. 17"
VOLUME_PATTERN = re.compile(
    r"Vol\.\s+([IVXLCDM]+)\s+No\.\s+(\d+)",
    re.IGNORECASE,
)

PARLIAMENT_PATTERN = re.compile(
    r"(" + "|".join(PARLIAMENT_NAMES.keys()) + r")\s+PARLIAMENT",
    re.IGNORECASE,
)

SESSION_TIME_PATTERN = re.compile(
    r"The House met at\s+([\d.]+\s*[ap]\.m\.)",
    re.IGNORECASE,
)


# Text Extraction

def extract_text(pdf_path: Path) -> str:
    """
    Raw text extraction from all pages of a PDF file.
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
    Extracts all MP speech entries from Hansard text.

    Handles two speaker formats:
      - Standard:  Hon. Name (Constituency, Party): ...
      - Titled:    Hon. (Dr) Name (Constituency, Party): ...

    Chair/procedural entries (The Speaker, The Temporary Speaker) are excluded.
    Results are returned in document order.
    """
    if not text:
        return []

    collected = []

    for match in TITLED_SPEAKER_PATTERN.finditer(text):
        title = match.group(1).strip()
        name = match.group(2).strip()
        constituency = match.group(3).strip()
        party = match.group(4).strip()
        content = match.group(5).strip()

        if not content:
            continue

        collected.append({
            "name": name,
            "title": title,
            "constituency": constituency,
            "party": party,
            "content": content,
            "_pos": match.start(),
        })

    titled_positions = {s["_pos"] for s in collected}

    for match in SPEAKER_PATTERN.finditer(text):
        name = match.group(1).strip()

        if name.startswith("Temporary Speaker") or name.startswith("Speaker"):
            continue

        if match.start() in titled_positions:
            continue

        constituency = match.group(2).strip()
        party = match.group(3).strip()
        content = match.group(4).strip()

        if not content:
            continue

        collected.append({
            "name": name,
            "title": None,
            "constituency": constituency,
            "party": party,
            "content": content,
            "_pos": match.start(),
        })

    collected.sort(key=lambda s: s["_pos"])

    for speech in collected:
        del speech["_pos"]

    return collected


# Section Parsing

def parse_sections(text: str) -> list[dict]:
    """
    Identifies named procedural sections within the document.
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

        sections.append({"title": title, "content": content})

    return sections


# Metadata Extraction

def _extract_date(text: str) -> str | None:
    match = DATE_PATTERN.search(text[:3000])
    if match is None:
        return None
    try:
        raw = f"{match.group(1)} {match.group(2)} {match.group(3)}"
        return datetime.strptime(raw, "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_volume(text: str) -> int | None:
    """
    Converts Roman numeral volume to integer. Vol. V -> 5.
    """
    match = VOLUME_PATTERN.search(text[:1000])
    if match is None:
        return None
    return ROMAN_NUMERALS.get(match.group(1).upper())


def _extract_issue(text: str) -> int | None:
    match = VOLUME_PATTERN.search(text[:1000])
    if match is None:
        return None
    return int(match.group(2))


def _extract_parliament_number(text: str) -> int | None:
    """
    Converts parliament word form to integer. THIRTEENTH -> 13.
    """
    match = PARLIAMENT_PATTERN.search(text[:1000])
    if match is None:
        return None
    return PARLIAMENT_NAMES.get(match.group(1).upper())


def _extract_session_time(text: str) -> str | None:
    """
    Normalises sitting time to MORNING or AFTERNOON.
    "The House met at 9.30 a.m." -> MORNING
    "(The House met at 2.30 p.m.)" -> AFTERNOON
    """
    match = SESSION_TIME_PATTERN.search(text[:3000])
    if match is None:
        return None
    time_str = match.group(1).lower()
    if "a.m" in time_str:
        return "MORNING"
    if "p.m" in time_str:
        return "AFTERNOON"
    return None


def _detect_chamber(text: str) -> str:
    if "senate" in text[:2000].lower():
        return "Senate"
    return "National Assembly"


# Full Document Parse

def parse_document(pdf_path: Path) -> dict:
    """
    Full parse of a single Hansard PDF.

    Returns a dict containing:
      date, chamber, parliament_number, volume, issue,
      session_time, pdf_path, sections, speeches.
    """
    text = extract_text(pdf_path)

    if not text:
        logger.warning("No text extracted from %s", pdf_path.name)
        return {}

    sections = parse_sections(text)
    speakers = parse_speakers(text)
    speeches = _assign_sections_to_speeches(text, sections, speakers)

    return {
        "date": _extract_date(text),
        "chamber": _detect_chamber(text),
        "parliament_number": _extract_parliament_number(text),
        "volume": _extract_volume(text),
        "issue": _extract_issue(text),
        "session_time": _extract_session_time(text),
        "pdf_path": str(pdf_path),
        "sections": sections,
        "speeches": speeches,
    }


def _assign_sections_to_speeches(
    full_text: str,
    sections: list[dict],
    speakers: list[dict],
) -> list[dict]:
    """
    Matches each speech to the procedural section it falls under,
    using character position in the full document text.
    """
    section_boundaries = []

    for section in sections:
        pos = full_text.find(section["title"])
        if pos != -1:
            section_boundaries.append((pos, section["title"]))

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