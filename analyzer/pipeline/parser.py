import re
import logging
from pathlib import Path
from datetime import datetime

import pdfplumber

from config import SECTION_HEADINGS, ROMAN_NUMERALS, PARLIAMENT_NAMES

logger = logging.getLogger(__name__)


# Speaker Patterns
#
# Two formats exist in Hansard PDFs:
#   Standard:  Hon. Name (Constituency, Party): content
#   Titled:    Hon. (Dr) Name (Constituency, Party): content
#
# The Temporary Speaker and Hon. Speaker entries are procedural chair
# interventions and are excluded from speech records.

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

# Date Pattern
DATE_PATTERN = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+),?\s+(\d{4})",
    re.IGNORECASE,
)

# Volume Pattern
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
    speeches_with_sections = _assign_sections_to_speeches(text, sections, speakers)
    speeches = assign_agenda_items_to_speeches(text, speeches_with_sections)

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


# Agenda Item Extraction

_AGENDA_PATTERNS = [
    re.compile(
        r"(THE\s+[A-Z][A-Z\s\(\)\/\-]+(?:BILL|ACT))\s*\n\s*\((?:National Assembly|Senate) Bill",
        re.MULTILINE,
    ),
    re.compile(
        r"^(APPROVAL\s+OF\s+[A-Z][A-Z\s\(\)\/\-\,]+|ADOPTION\s+OF\s+[A-Z][A-Z\s\(\)\/\-\,]+)$",
        re.MULTILINE,
    ),
    re.compile(
        r"^STATEMENT\s*\n([A-Z][A-Z\s\(\)\/\-\,]{10,})$",
        re.MULTILINE,
    ),
    re.compile(
        r"Question\s+\d+/\d+\s*\n([A-Z][A-Z\s\(\)\/\-\,]{8,})$",
        re.MULTILINE,
    ),
    re.compile(
        r"^REQUEST FOR STATEMENT\s*\n([A-Z][A-Z\s\(\)\/\-\,]{8,})$",
        re.MULTILINE,
    ),
]

# Agenda Item Type Classification
AGENDA_TYPE_PATTERNS = {
    "BILL": [
        r"\bBILL\b",
        r"\bAMENDMENT\b",
    ],
    "MOTION": [
        r"\bMOTION\b",
        r"\bADOPTION\b",
        r"\bAPPROVAL\b",
        r"\bSENATE AMENDMENTS\b",
    ],
    "PETITION": [
        r"\bPETITION\b",
    ],
    "STATEMENT": [
        r"\bSTATEMENT\b",
    ],
    "QUESTION": [
        r"\bQUESTION\b",
        r"\bREQUEST FOR STATEMENT\b",
    ],
    "PAPER": [
        r"\bPAPERS?\b",
    ],
}

SECTION_DIVIDER_HEADINGS = {
    "PRAYERS",
    "ADJOURNMENT",
    "QUORUM",
    "POINT OF ORDER",
    "PERSONAL STATEMENT",
    "COMMUNICATION FROM THE CHAIR",
    "QUESTIONS AND STATEMENTS",
    "REQUESTS FOR STATEMENTS",
    "IN THE COMMITTEE",
    "IN THE HOUSE",
    "SECOND READING",
    "THIRD READING",
    "COMMITTEE OF THE WHOLE HOUSE",
    "NATIONAL ASSEMBLY",
    "REPUBLIC OF KENYA",
    "THE HANSARD",
    "THIRTEENTH PARLIAMENT",
}


def classify_agenda_type(heading: str) -> str:
    """
    Classifies an agenda item heading into a structural type.
    Returns one of: BILL, MOTION, PETITION, STATEMENT, QUESTION, PAPER, OTHER
    """
    heading_upper = heading.upper()
    for item_type, patterns in AGENDA_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, heading_upper):
                return item_type
    return "OTHER"


def is_section_divider(heading: str) -> bool:
    """
    Returns True if the heading is a broad procedural divider rather than
    a specific agenda item. Section dividers should not become agenda items.
    """
    return heading.strip().upper() in SECTION_DIVIDER_HEADINGS


def clean_agenda_title(raw_heading: str) -> str:
    """
    Converts a raw ALL CAPS Hansard heading into a readable title.

    Examples:
      'THE QUALITY HEALTHCARE AND PATIENT SAFETY BILL' ->
      'Quality Healthcare and Patient Safety Bill'

      'APPROVAL OF NOMINEES FOR APPOINTMENT TO THE NATIONAL LAND COMMISSION' ->
      'Approval of Nominees for Appointment to the National Land Commission'
    """
    title = re.sub(r"^THE\s+", "", raw_heading.strip(), flags=re.IGNORECASE)
    title = re.sub(
        r"\((?:National Assembly|Senate) Bill No\..*?\)",
        "",
        title,
        flags=re.IGNORECASE,
    )
    title = title.strip().title()
    return title


def extract_agenda_items(text: str) -> list[dict]:
    """
    Scans Hansard text for agenda item headings.

    A heading qualifies as an agenda item if it:
    - Is a line substantially in ALL CAPS
    - Is not a section divider (PRAYERS, ADJOURNMENT, etc.)
    - Contains at least 3 words
    - Does not match known noise patterns (page numbers, disclaimers)

    Returns a list of dicts, each containing:
      raw_heading  — original text as found in the PDF
      title        — cleaned, readable title
      type         — BILL | MOTION | PETITION | STATEMENT | QUESTION | PAPER | OTHER
      position     — character position in full text (used for speech assignment)

    Results are sorted by position ascending.
    """
    heading_pattern = re.compile(
        r"^([A-Z][A-Z\s\-\(\)\'\/,]{10,})$",
        re.MULTILINE,
    )

    noise_patterns = [
        r"^\d+$",
        r"Disclaimer",
        r"Hansard Editor",
        r"electronic version",
        r"^[A-Z]{1,3}$",
        r"^National Assembly Debates",
    ]

    items = []
    sequence = 0

    for match in heading_pattern.finditer(text):
        raw = match.group(1).strip()

        if any(re.search(p, raw, re.IGNORECASE) for p in noise_patterns):
            continue

        if is_section_divider(raw):
            continue

        if len(raw.split()) < 3:
            continue

        sequence += 1
        items.append({
            "raw_heading": raw,
            "title": clean_agenda_title(raw),
            "type": classify_agenda_type(raw),
            "position": match.start(),
        })

    items.sort(key=lambda item: item["position"])
    return items

# Deprecated
def assign_agenda_items_to_speeches(
    full_text: str,
    speeches: list[dict],
) -> list[dict]:
    """
    Assigns each speech the agenda item it falls under.

    A speech belongs to the most recent agenda item that started before
    the speech's position in the document. Speeches that precede the first
    agenda item (e.g. procedural PAPERS entries) receive None.
    """
    agenda_items = extract_agenda_items(full_text)

    if not agenda_items:
        return [{**speech, "agenda_item": None} for speech in speeches]

    result = []

    for speech in speeches:
        content_pos = full_text.find(speech["content"][:80])
        active_item = None

        for item in agenda_items:
            if content_pos >= item["position"]:
                active_item = item["title"]
            else:
                break

        result.append({**speech, "agenda_item": active_item})

    return result