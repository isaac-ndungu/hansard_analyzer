import logging
from pathlib import Path

from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    insert_session,
    get_or_create_member,
    insert_speech,
    insert_speech_topic,
    get_session_by_date_and_time,
)
from analyzer.pipeline.parser import parse_document
from analyzer.pipeline.normalizer import normalize
from analyzer.analytics.topics import classify_speech_topics

logger = logging.getLogger(__name__)


# Pipeline Orchestration

def run_pipeline(pdf_path: Path) -> int:
    """
    Full ingestion pipeline for a single Hansard PDF.

    Steps:
      1. Parse the PDF into structured data
      2. Normalize and validate all speech records
      3. Check for an existing session with the same date and session_time
      4. Store the session, members, speeches, and speech topics to the database

    Returns the number of speeches stored, or 0 if the document was skipped.
    """
    logger.info("Processing: %s", pdf_path.name)

    parsed = parse_document(pdf_path)

    if not parsed:
        logger.warning("Nothing parsed from %s — skipping.", pdf_path.name)
        return 0

    if parsed.get("date") is None:
        logger.warning("No date found in %s — skipping.", pdf_path.name)
        return 0

    normalized = normalize(parsed)

    if not normalized.get("speeches"):
        logger.warning("No valid speeches after normalization for %s", pdf_path.name)
        return 0

    conn = get_connection()

    existing = get_session_by_date_and_time(
        conn,
        date=normalized["date"],
        session_time=normalized.get("session_time"),
    )

    if existing is not None:
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
        pdf_path=normalized["pdf_path"],
    )

    stored_count = 0

    for speech in normalized["speeches"]:
        member_id = get_or_create_member(
            conn,
            name=speech["name"],
            constituency=speech["constituency"],
            party=speech["party"],
        )

        speech_id = insert_speech(
            conn,
            session_id=session_id,
            member_id=member_id,
            section=speech["section"],
            content=speech["content"],
            word_count=speech["word_count"],
        )

        topics = classify_speech_topics(speech["content"])

        for topic_result in topics:
            insert_speech_topic(
                conn,
                speech_id=speech_id,
                topic=topic_result["topic"],
                confidence=topic_result["confidence"],
            )

        stored_count += 1

    conn.close()
    logger.info("Stored %d speeches from %s", stored_count, pdf_path.name)
    return stored_count