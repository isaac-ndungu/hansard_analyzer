import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# Directory Paths

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR  = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "hansard.db"

PDF_DIR.mkdir(parents=True, exist_ok=True)


# External Sources

HANSARD_BASE_URL = "https://parliament.go.ke/the-national-assembly/house-business/hansard"


# AI Configuration

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"


# Parser Configuration

CHAMBERS = ["National Assembly", "Senate"]

ROMAN_NUMERALS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XX": 20, "XXV": 25, "L": 50,
}

PARLIAMENT_NAMES = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
    "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14,
    "FIFTEENTH": 15,
}

SECTION_HEADINGS = [
    "PRAYERS",
    "PETITIONS",
    "PAPERS",
    "NOTICES OF MOTION",
    "QUESTIONS",
    "BILLS",
    "MOTIONS",
    "ADJOURNMENT",
    "STATEMENTS",
]


# Analytics Configuration

TOPIC_MAP = {
    "healthcare": ["health", "hospital", "doctor", "nurse", "SHA", "NHIF", "patient"],
    "education": ["school", "teacher", "TSC", "university", "student", "curriculum"],
    "infrastructure": ["road", "bridge", "water", "electricity", "KeRRA", "KURA"],
    "security": ["police", "crime", "terror", "KDF", "security"],
    "agriculture": ["farmer", "crop", "livestock", "drought", "food"],
    "finance": ["budget", "tax", "debt", "KRA", "Treasury", "deficit"],
    "environment": ["climate", "forest", "river", "pollution", "wildlife"],
}


# Scheduler Configuration

SYNC_SCHEDULE_HOUR = 6
SYNC_SCHEDULE_MINUTE = 0