import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


# Known Party Name Variants

PARTY_ALIASES = {
    "uda": "UDA",
    "u.d.a": "UDA",
    "u.d.a.": "UDA",
    "odm": "ODM",
    "o.d.m": "ODM",
    "o.d.m.": "ODM",
    "jubilee": "Jubilee",
    "wiper": "Wiper",
    "amani": "Amani",
    "ford kenya": "Ford Kenya",
    "ford-kenya": "Ford Kenya",
    "dp": "DP",
    "independent": "Independent",
}


# Name Normalization

def normalize_name(raw_name: str) -> str:
    """
    Cleans an MP name extracted from Hansard text.
    Removes titles, excess whitespace, and standardizes casing.
    """
    prefixes = re.compile(r"\b(Dr|Prof|Eng|Gen|Col|Capt|Hon)\b\.?\s*", re.IGNORECASE)
    cleaned = prefixes.sub("", raw_name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title()


# Party Normalization

def normalize_party(raw_party: str) -> str:
    """
    Maps raw party strings to canonical party names.
    Falls back to title-cased raw value if no alias is found.
    """
    lookup_key = raw_party.strip().lower()
    return PARTY_ALIASES.get(lookup_key, raw_party.strip().title())


# Constituency Normalization

def normalize_constituency(raw_constituency: str) -> str:
    return re.sub(r"\s+", " ", raw_constituency).strip().title()


# Word Count

def compute_word_count(content: str) -> int:
    words = content.split()
    return len(words)


# Speech Validation

def is_valid_speech(speech: dict) -> bool:
    """
    Checks that a parsed speech record has the minimum required fields
    to be worth storing. Logs a warning for each rejected record.
    """
    required_fields = ("name", "constituency", "party", "content", "section")

    for field in required_fields:
        if not speech.get(field):
            logger.warning("Skipping speech — missing field '%s': %s", field, speech)
            return False

    if compute_word_count(speech["content"]) < 3:
        logger.warning("Skipping speech — content too short: %s", speech["content"][:60])
        return False

    return True


# Full Normalization

def normalize_speech(speech: dict) -> dict:
    """
    Applies all cleaning and standardization to a single parsed speech dict.
    """
    return {
        "name": normalize_name(speech["name"]),
        "constituency": normalize_constituency(speech["constituency"]),
        "party": normalize_party(speech["party"]),
        "content": speech["content"].strip(),
        "section": speech.get("section", "UNKNOWN").upper(),
        "word_count": compute_word_count(speech["content"]),
    }


def normalize(parsed_document: dict) -> dict:
    """
    Runs normalization over all speeches in a parsed document.
    Skips any speech that fails validation.
    """
    if not parsed_document:
        return {}

    raw_speeches = parsed_document.get("speeches", [])
    clean_speeches = []

    for speech in raw_speeches:
        if is_valid_speech(speech):
            clean_speeches.append(normalize_speech(speech))

    return {
        **parsed_document,
        "speeches": clean_speeches,
    }