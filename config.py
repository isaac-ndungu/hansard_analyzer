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

{
    "healthcare": [
        "health", "hospital", "doctor", "nurse", "patient", "clinic", "medicine",
        "SHA", "NHIF", "KMTC", "malaria", "disease", "mental health", "maternal",
        "pharmaceutical", "ambulance", "dispensary", "surgery", "treatment",
    ],
    "education": [
        "school", "teacher", "TSC", "university", "student", "curriculum",
        "TVET", "college", "bursary", "tuition", "CBC", "exam", "KNEC",
        "primary", "secondary", "polytechnic", "literacy", "scholarship",
    ],
    "infrastructure": [
        "road", "bridge", "KeRRA", "KURA", "KENHA", "railway", "airport",
        "port", "construction", "tarmac", "internet", "broadband",
        "fibre", "housing", "estate", "affordable housing",
    ],
    "water": [
        "water", "dam", "river", "borehole", "irrigation", "rainfall",
        "WRUA", "sewerage", "pipeline", "abstraction", "catchment",
        "reservoir", "flood", "sanitation", "WASH",
    ],
    "security": [
        "police", "crime", "terror", "KDF", "security", "bandit", "raid",
        "gun", "arms", "Al-Shabaab", "DCI", "NIS", "GSU", "NYS",
        "kidnap", "abduction", "femicide", "robbery", "extrajudicial",
    ],
    "agriculture": [
        "farmer", "crop", "livestock", "food", "fertiliser", "subsidy",
        "maize", "wheat", "coffee", "tea", "sugar", "milk", "dairy",
        "NCPB", "ADC", "KDB", "harvest", "famine", "hunger", "drought",
    ],
    "finance": [
        "budget", "tax", "debt", "KRA", "Treasury", "deficit", "revenue",
        "loan", "IMF", "World Bank", "borrowing", "expenditure", "fiscal",
        "VAT", "excise", "inflation", "shilling", "forex", "eurobond",
    ],
    "environment": [
        "climate", "forest", "pollution", "wildlife", "conservation",
        "carbon", "emission", "NEMA", "KWS", "deforestation", "Mau",
        "green", "plastic", "waste", "ocean", "coral",
    ],
    "land": [
        "land", "title deed", "eviction", "NLC", "survey", "adjudication",
        "squatter", "settlement", "acreage", "lease", "compulsory acquisition",
        "encroachment", "boundary", "community land",
    ],
    "devolution": [
        "county", "governor", "CEC", "devolution", "ward", "MCA",
        "equitable share", "OCOB", "intergovernmental", "transfer",
        "CRA", "service delivery", "county government",
    ],
    "energy": [
        "electricity", "power", "KPLC", "KenGen", "EPRA", "REA",
        "solar", "geothermal", "wind", "oil", "petroleum", "gas",
        "fuel", "kerosene", "blackout", "generation", "transmission",
    ],
    "fisheries": [
        "fish", "fishing", "fishermen", "lake", "ocean", "aquaculture",
        "tilapia", "omena", "trawler", "BMU", "landing site", "cage",
        "blue economy", "marine", "coastline", "fingerling",
    ],
    "gender": [
        "women", "gender", "girl", "female", "GBV", "femicide",
        "two-thirds", "affirmative action", "sexual violence", "FGM",
        "maternity", "menstrual", "sanitary",
    ],
    "youth": [
        "youth", "young people", "unemployment", "intern", "NYS",
        "graduate", "HELB", "startup", "NITA",
    ],
}


# Scheduler Configuration

SYNC_SCHEDULE_HOUR = 6
SYNC_SCHEDULE_MINUTE = 0