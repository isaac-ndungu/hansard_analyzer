import logging
import re
from collections import Counter
from config import TOPIC_MAP

logger = logging.getLogger(__name__)


# Known Party Name Variants

PARTY_ALIASES = {

    "uda": "UDA",
    "u.d.a": "UDA",
    "u.d.a.": "UDA",

    "odm": "ODM",
    "o.d.m": "ODM",
    "o.d.m.": "ODM",
    "jp": "JP",
    "kanu": "KANU",
    "kup": "KUP",
    "udm": "UDM",
    "mdg": "MDG",
    "wdm": "WDM",
    "gddp": "GDDP",
    "ccm": "CCM",
    "dp": "DP",

    "jubilee": "Jubilee",
    "wiper": "Wiper",
    "amani": "Amani",
    "ford kenya": "Ford Kenya",
    "ford-kenya": "Ford Kenya",
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


# Topic Extraction

def extract_topics(content: str) -> list[dict]:
    """
    Extracts topics from speech content by matching keywords from TOPIC_MAP.
    Returns a list of dicts with 'topic' and 'confidence' keys.
    
    Confidence is calculated as: (keyword_matches / total_words) * 100
    """
    if not content:
        return []
    
    content_lower = content.lower()
    word_count = compute_word_count(content)
    detected = {}
    
    for topic, keywords in TOPIC_MAP.items():
        match_count = 0
        for keyword in keywords:
            # Count word boundary matches for accuracy
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = len(re.findall(pattern, content_lower))
            match_count += matches
        
        if match_count > 0:
            # Confidence: (matches / word_count) * 100, capped at 100
            confidence = min(100, (match_count / word_count) * 100)
            detected[topic] = round(confidence, 2)
    
    # Return topics sorted by confidence (highest first)
    return [
        {"topic": topic, "confidence": conf}
        for topic, conf in sorted(detected.items(), key=lambda x: x[1], reverse=True)
    ]


# Full Normalization

def normalize_speech(speech: dict) -> dict:
    """
    Applies all cleaning and standardization to a single parsed speech dict.
    Extracts topics from the content.
    """
    return {
        "name": normalize_name(speech["name"]),
        "constituency": normalize_constituency(speech["constituency"]),
        "party": normalize_party(speech["party"]),
        "content": speech["content"].strip(),
        "section": speech.get("section", "UNKNOWN").upper(),
        "agenda_item": speech.get("agenda_item"),
        "position": speech.get("position", 0),
        "word_count": compute_word_count(speech["content"]),
        "topics": extract_topics(speech["content"]),
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