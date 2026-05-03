import logging
from pathlib import Path
from typing import Optional

from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    insert_session,
    get_session_by_date_and_time,
    get_or_create_member,
    get_member_by_name,
    insert_speech,
    insert_agenda_item,
    insert_agenda_item_topic,
    get_or_create_bill,
    insert_bill_reading,
)
from analyzer.pipeline.parser import parse_document, extract_text, extract_agenda_items
from analyzer.pipeline.normalizer import normalize
from analyzer.pipeline.bill_parser import (
    extract_bills,
    extract_bill_metadata,
    extract_bill_sponsor,
)
from analyzer.analytics.topics import classify_agenda_title

logger = logging.getLogger(__name__)


# Speech-to-Agenda Assignment

def _find_agenda_item_for_speech(
    speech_position: int,
    agenda_items_with_positions: list[dict],
) -> Optional[int]:
    """
    Finds the agenda item a speech belongs to using character position.

    A speech belongs to the agenda item whose heading appeared most recently
    before the speech in the raw text. This is the positional reading model —
    everything after a heading belongs to that heading until the next one appears.

    Returns the agenda item id or None if no heading precedes the speech.
    """
    if not agenda_items_with_positions:
        return None

    best_id = None
    best_position = -1

    for item in agenda_items_with_positions:
        item_pos = item["position"]
        if item_pos <= speech_position and item_pos > best_position:
            best_position = item_pos
            best_id = item["id"]

    return best_id


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
    raw_agendas = extract_agenda_items(raw_text)
    
    # Deduplicate: Keep only the last occurrence of each title to merge TOC and body
    deduped_agendas = {}
    for item in raw_agendas:
        title = item["title"].lower()
        deduped_agendas[title] = item
        
    agenda_item_dicts = sorted(deduped_agendas.values(), key=lambda x: x["position"])

    # agenda_items_with_positions: list of agenda items with document offsets
    agenda_items_with_positions = []

    for seq, item_dict in enumerate(agenda_item_dicts, start=1):
        aid = insert_agenda_item(
            conn,
            session_id=session_id,
            title=item_dict["title"],
            item_type=item_dict["type"],
            sequence=seq,
            raw_heading=item_dict["raw_heading"],
        )

        topics = classify_agenda_title(item_dict["title"])
        for tm in topics:
            insert_agenda_item_topic(conn, aid, tm["topic"], tm["confidence"])

        agenda_items_with_positions.append({
            "id": aid,
            "position": item_dict["position"],
            "title": item_dict["title"],
            "type": item_dict["type"],
            "raw_heading": item_dict["raw_heading"],
        })

    logger.info(
        "Inserted %d agenda items for session %s",
        len(agenda_items_with_positions),
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

        agenda_item_id = _find_agenda_item_for_speech(
            speech_position=speech.get("position", 0),
            agenda_items_with_positions=agenda_items_with_positions,
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

    # Create bill rows for every agenda item typed as BILL.
    # Sponsor is inferred from the first speech under that agenda item.
    for item in agenda_items_with_positions:
        if item["type"] != "BILL":
            continue

        sponsor_name = extract_bill_sponsor(raw_text, item["position"])
        sponsor_id = None

        if sponsor_name:
            member = get_member_by_name(conn, sponsor_name)
            sponsor_id = member["id"] if member else None

        if sponsor_id is None:
            sponsor_row = conn.execute(
                "SELECT member_id FROM speeches WHERE agenda_item_id = ? ORDER BY id ASC LIMIT 1",
                (item["id"],),
            ).fetchone()
            sponsor_id = sponsor_row[0] if sponsor_row else None

        bill_number, bill_year = extract_bill_metadata(item["raw_heading"])
        get_or_create_bill(
            conn,
            title=item["title"],
            agenda_item_id=item["id"],
            bill_number=bill_number,
            bill_year=bill_year,
            introduced_date=normalized["date"],
            sponsor_id=sponsor_id,
        )

    bills = extract_bills(raw_text)
    for bill_data in bills:
        matching_aid = None
        for item in agenda_items_with_positions:
            if item["type"] != "BILL":
                continue
            title_words = [
                w for w in bill_data["title"].lower().split() if len(w) > 4
            ]
            if any(word in item["title"].lower() for word in title_words):
                matching_aid = item["id"]
                break

        bill_id = get_or_create_bill(
            conn,
            title=bill_data["title"],
            agenda_item_id=matching_aid,
            bill_number=bill_data.get("bill_number"),
            bill_year=bill_data.get("bill_year"),
            introduced_date=normalized["date"],
        )
        if bill_data.get("reading") or bill_data.get("outcome"):
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

    # Update sentiment for newly stored speeches
    from analyzer.analytics.sentiment import update_speech_sentiments
    updated = update_speech_sentiments()
    logger.info("Sentiment updated for %d speeches.", updated)

    return stored_count