import logging
from pathlib import Path
from typing import Optional

from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    insert_session,
    get_session_by_date_and_time,
    get_or_create_member,
    insert_speech,
    insert_agenda_item,
    insert_agenda_item_topic,
    get_or_create_bill,
    insert_bill_reading,
)
from analyzer.pipeline.parser import parse_document, extract_text, extract_agenda_items
from analyzer.pipeline.normalizer import normalize
from analyzer.pipeline.bill_parser import extract_bills, extract_bill_metadata
from analyzer.analytics.topics import classify_agenda_title

logger = logging.getLogger(__name__)


# Speech-to-Agenda Assignment

def _find_agenda_item_id(
    speech_section: str,
    speech_content: str,
    agenda_items_map: dict,
) -> Optional[int]:
    """
    Finds the most likely agenda item id for a speech.

    Strategy:
    1. Map the speech's broad section (BILLS, MOTIONS) to an agenda item type
    2. Among agenda items of that type, find one whose title words appear
       in the speech content
    3. If no content match, return the last inserted agenda item of that type

    Returns an agenda_item_id integer, or None if no match can be found.
    """
    if not agenda_items_map:
        return None

    section_to_type = {
        "BILLS":      "BILL",
        "MOTIONS":    "MOTION",
        "PETITIONS":  "PETITION",
        "STATEMENTS": "STATEMENT",
        "QUESTIONS":  "QUESTION",
        "PAPERS":     "PAPER",
    }

    section_upper = (speech_section or "").upper()
    target_type = None

    for section_key, item_type in section_to_type.items():
        if section_key in section_upper:
            target_type = item_type
            break

    if target_type is None:
        return None

    content_lower = (speech_content or "").lower()
    last_match = None

    for aid, item in agenda_items_map.items():
        if item["type"] != target_type:
            continue
        last_match = aid
        title_words = [w for w in item["title"].lower().split() if len(w) > 4]
        if title_words and any(word in content_lower for word in title_words):
            return aid

    return last_match


# Pipeline Orchestration

def run_pipeline(pdf_path: Path) -> int:
    """
    Full ingestion pipeline for a single Hansard PDF.

    Steps:
      1. Parse PDF into structured data
      2. Normalize and validate all records
      3. Check for duplicate session
      4. Insert session record
      5. Extract and insert agenda items
      6. Classify topics from agenda item titles
      7. Insert speeches linked to agenda items via foreign key
      8. Extract and insert bills linked to agenda items

    Returns number of speeches stored, or 0 if skipped.
    """
    logger.info("Processing: %s", pdf_path.name)

    parsed = parse_document(pdf_path)
    if not parsed or not parsed.get("date"):
        logger.warning("Skipping %s — no parseable data.", pdf_path.name)
        return 0

    normalized = normalize(parsed)
    if not normalized.get("speeches"):
        logger.warning("Skipping %s — no valid speeches.", pdf_path.name)
        return 0

    conn = get_connection()

    existing = get_session_by_date_and_time(
        conn,
        date=normalized["date"],
        session_time=normalized.get("session_time"),
    )
    if existing:
        logger.info(
            "Session already stored for %s %s — skipping.",
            normalized["date"],
            normalized.get("session_time") or "",
        )
        conn.close()
        return 0

    session_id = insert_session(
        conn,
        date=normalized["date"],
        chamber=normalized["chamber"],
        parliament_number=normalized.get("parliament_number"),
        volume=normalized.get("volume"),
        issue=normalized.get("issue"),
        session_time=normalized.get("session_time"),
        pdf_path=str(pdf_path),
    )

    raw_text = extract_text(pdf_path)
    agenda_item_dicts = extract_agenda_items(raw_text)

    # agenda_items_map: {agenda_item_id: {title, type}} for speech matching
    agenda_items_map = {}

    for seq, item_dict in enumerate(agenda_item_dicts, start=1):
        aid = insert_agenda_item(
            conn,
            session_id=session_id,
            title=item_dict["title"],
            item_type=item_dict["type"],
            sequence=seq,
            raw_heading=item_dict["raw_heading"],
        )
        agenda_items_map[aid] = {
            "title": item_dict["title"],
            "type": item_dict["type"],
        }

        if item_dict["type"] == "BILL":
            bill_number, bill_year = extract_bill_metadata(item_dict["raw_heading"])
            get_or_create_bill(
                conn,
                title=item_dict["title"],
                agenda_item_id=aid,
                bill_number=bill_number,
                bill_year=bill_year,
                introduced_date=normalized["date"],
            )

        topics = classify_agenda_title(item_dict["title"])
        for tm in topics:
            insert_agenda_item_topic(conn, aid, tm["topic"], tm["confidence"])

    logger.info(
        "Inserted %d agenda items for session %s",
        len(agenda_items_map),
        normalized["date"],
    )

    stored_count = 0

    for speech in normalized["speeches"]:
        member_id = get_or_create_member(
            conn,
            name=speech["name"],
            constituency=speech["constituency"],
            party=speech["party"],
        )

        agenda_item_id = _find_agenda_item_id(
            speech_section=speech.get("section"),
            speech_content=speech.get("content"),
            agenda_items_map=agenda_items_map,
        )

        insert_speech(
            conn,
            session_id=session_id,
            member_id=member_id,
            agenda_item_id=agenda_item_id,
            section=speech.get("section"),
            content=speech["content"],
            word_count=speech["word_count"],
        )
        stored_count += 1

    bills = extract_bills(raw_text)
    for bill_data in bills:
        matching_aid = None
        for aid, item in agenda_items_map.items():
            if item["type"] == "BILL":
                title_words = [
                    w for w in bill_data["title"].lower().split() if len(w) > 4
                ]
                if any(word in item["title"].lower() for word in title_words):
                    matching_aid = aid
                    break

        bill_id = get_or_create_bill(
            conn,
            title=bill_data["title"],
            agenda_item_id=matching_aid,
            bill_number=bill_data.get("bill_number"),
            bill_year=bill_data.get("bill_year"),
            introduced_date=normalized["date"],
        )
        if bill_data.get("reading"):
            insert_bill_reading(
                conn,
                bill_id=bill_id,
                session_id=session_id,
                reading=bill_data.get("reading"),
                outcome=bill_data.get("outcome"),
                date=normalized["date"],
            )

    conn.close()
    logger.info("Stored %d speeches from %s", stored_count, pdf_path.name)
    return stored_count