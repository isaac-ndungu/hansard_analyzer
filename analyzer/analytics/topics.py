import re
import logging
from collections import defaultdict
from pathlib import Path

from config import TOPIC_MAP, DB_PATH
from analyzer.database.seed import get_connection

logger = logging.getLogger(__name__)


# Topic Classification

def classify_speech_topics(content: str) -> list[dict]:
    """
    Scans speech content against the TOPIC_MAP keyword lists and returns
    all topics that have at least one keyword match.

    Each result dict contains:
      topic      — the topic name
      confidence — proportion of the topic's keywords found in the content,
                   rounded to two decimal places (0.0 to 1.0)
      matches    — the specific keywords that were found

    Results are sorted by confidence descending.
    Topics with zero matches are excluded entirely.
    """
    if not content:
        return []

    content_lower = content.lower()
    results = []

    for topic, keywords in TOPIC_MAP.items():
        matched = []

        for keyword in keywords:
            pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
            if pattern.search(content_lower):
                matched.append(keyword)

        if not matched:
            continue

        confidence = round(len(matched) / len(keywords), 2)

        results.append({
            "topic": topic,
            "confidence": confidence,
            "matches": matched,
        })

    results.sort(key=lambda r: r["confidence"], reverse=True)

    return results


# Topic Frequency

def get_topic_frequency(
    conn,
    topic: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Returns how many speeches were tagged with the given topic,
    grouped by month. Optionally filtered by date range.
    """
    cursor = conn.cursor()

    query = """
        SELECT
            strftime('%Y-%m', se.date) AS month,
            COUNT(DISTINCT st.speech_id)  AS speech_count
        FROM speech_topics st
        JOIN speeches sp ON st.speech_id = sp.id
        JOIN sessions se ON sp.session_id = se.id
        WHERE st.topic = ?
    """
    params: list = [topic]

    if from_date is not None:
        query += " AND se.date >= ?"
        params.append(from_date)

    if to_date is not None:
        query += " AND se.date <= ?"
        params.append(to_date)

    query += " GROUP BY month ORDER BY month"

    cursor.execute(query, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# MP Topic Profile

def get_mp_topics(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns all topics associated with a given member's speeches,
    ordered by frequency of appearance.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT st.topic, COUNT(*) AS count
            FROM speech_topics st
            JOIN speeches sp ON st.speech_id = sp.id
            WHERE sp.member_id = ?
            GROUP BY st.topic
            ORDER BY count DESC
            """,
            (member_id,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# Trending Topics

def get_trending_topics(conn, days: int = 30) -> list[dict]:
    """
    Returns the most discussed topics over the last N days,
    ordered by speech count descending.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT st.topic, COUNT(*) AS speech_count
        FROM speech_topics st
        JOIN speeches sp ON st.speech_id = sp.id
        JOIN sessions se ON sp.session_id = se.id
        WHERE se.date >= date('now', ? || ' days')
        GROUP BY st.topic
        ORDER BY speech_count DESC
        """,
        (f"-{days}",),
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Agenda Item Topic Derivation

def derive_topics_from_agenda_item(agenda_item: str) -> list[dict]:
    """
    Derives topic tags by matching the agenda item title against the TOPIC_MAP.
    This is more accurate than scanning full speech content because the title
    is a precise descriptor of what is being debated.

    Returns the same structure as classify_speech_topics so the pipeline
    can treat both interchangeably.
    """
    if not agenda_item:
        return []

    title_lower = agenda_item.lower()
    results = []

    for topic, keywords in TOPIC_MAP.items():
        matched = [kw for kw in keywords if kw.lower() in title_lower]

        if matched:
            confidence = round(len(matched) / len(keywords), 2)
            results.append({
                "topic": topic,
                "confidence": confidence,
                "matches": matched,
            })

    if not results:
        results = classify_speech_topics(agenda_item)

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results