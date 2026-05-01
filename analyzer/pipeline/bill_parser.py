import re
from pathlib import Path
from typing import Optional


# Bill Number Pattern

BILL_NUMBER_PATTERN = re.compile(
    r"(?:National Assembly|Senate)\s+Bill\s+No\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)

BILL_TITLE_PATTERN = re.compile(
    r"(THE\s+[A-Z][A-Z\s\(\)\/\-]+(?:BILL))\s*\n\s*"
    r"\((?:National Assembly|Senate)\s+Bill\s+No\.?\s*(\d+)\s+of\s+(\d{4})\)",
    re.MULTILINE,
)


def extract_bill_metadata(text: str) -> tuple[Optional[str], Optional[int]]:
    """Parses bill number and year from an agenda heading or bill title."""
    match = BILL_NUMBER_PATTERN.search(text)
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


READING_PATTERNS = {
    "First Reading":  re.compile(r"First\s+Reading", re.IGNORECASE),
    "Second Reading": re.compile(r"Second\s+Reading", re.IGNORECASE),
    "Third Reading":  re.compile(r"Third\s+Reading", re.IGNORECASE),
    "Committee":      re.compile(r"Committee\s+of\s+the\s+Whole\s+House", re.IGNORECASE),
}


# Bill Extraction

def extract_bills(text: str) -> list[dict]:
    """
    Extracts bill records from Hansard text.

    Finds bills by locating their formal title and bill number annotation,
    then determines which reading stage was reached in this session.

    Returns a list of dicts:
      title       — readable bill title
      raw_title   — original ALL CAPS title from PDF
      bill_number — e.g. '8'
      bill_year   — e.g. 2026
      reading     — 'First Reading' | 'Second Reading' | etc. | None
      outcome     — None (outcomes are not reliably parseable from text)
    """
    bills = []
    seen_titles = set()

    for match in BILL_TITLE_PATTERN.finditer(text):
        raw_title = match.group(1).strip()
        bill_number = match.group(2)
        bill_year = int(match.group(3))

        clean_title = re.sub(r"^THE\s+", "", raw_title, flags=re.IGNORECASE)
        clean_title = clean_title.strip().title()

        if clean_title in seen_titles:
            continue
        seen_titles.add(clean_title)

        # Determine reading from context around the match
        context_start = max(0, match.start() - 200)
        context_end = min(len(text), match.end() + 500)
        context = text[context_start:context_end]

        reading = None
        for reading_name, pattern in READING_PATTERNS.items():
            if pattern.search(context):
                reading = reading_name
                break

        bills.append({
            "raw_title": raw_title,
            "title": clean_title,
            "bill_number": bill_number,
            "bill_year": bill_year,
            "reading": reading,
            "outcome": None,
        })

    return bills