import re
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from config import TOPIC_MAP, DB_PATH
from analyzer.database.seed import get_connection

logger = logging.getLogger(__name__)


# Agenda Title Classification

def classify_agenda_title(title: str) -> list[dict]:
    """
    Classifies an agenda item title against the TOPIC_MAP.

    Returns a list of matched topics sorted by confidence descending.
    Each dict: {topic, confidence, matches}

    """
    if not title:
        return []

    title_lower = title.lower()
    results = []

    for topic, keywords in TOPIC_MAP.items():
        matched = []

        for keyword in keywords:
            pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
            if pattern.search(title_lower):
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
    conn: sqlite3.Connection,
    topic: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    """
    Returns how many agenda items were tagged with a given topic per month.
    Each dict: {month, item_count}
    """
    cursor = conn.cursor()
    query = """
        SELECT
            strftime('%Y-%m', se.date) AS month,
            COUNT(DISTINCT ait.agenda_item_id) AS item_count
        FROM agenda_item_topics ait
        JOIN agenda_items ai ON ait.agenda_item_id = ai.id
        JOIN sessions se ON ai.session_id = se.id
        WHERE ait.topic = ?
    """
    params: list = [topic]
    if from_date:
        query += " AND se.date >= ?"
        params.append(from_date)

    if to_date:
        query += " AND se.date <= ?"
        params.append(to_date)

    query += " GROUP BY month ORDER BY month ASC"
    cursor.execute(query, params)
    columns = [d[0] for d in cursor.description]


    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# MP Topic Profile

def get_mp_topics(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns topics an MP has engaged with, derived from the agenda items
    they spoke in. Replaces the old speech_topics based version.
    Each dict: {topic, count}
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ait.topic, COUNT(DISTINCT ai.id) AS count
            FROM speeches sp
            JOIN agenda_items ai ON sp.agenda_item_id = ai.id
            JOIN agenda_item_topics ait ON ait.agenda_item_id = ai.id
            WHERE sp.member_id = ?
            GROUP BY ait.topic
            ORDER BY count DESC
            """,
            (member_id,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# Trending Topics

def get_trending_topics(
    conn: sqlite3.Connection,
    days: int = 30,
    limit: int = 10,
) -> list[dict]:
    """
    Returns most discussed topics in the last N days, based on speech count
    across agenda items tagged with each topic.
    Each dict: {topic, speech_count}
    """
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT ait.topic, COUNT(DISTINCT sp.id) AS speech_count
        FROM agenda_item_topics ait
        JOIN agenda_items ai ON ait.agenda_item_id = ai.id
        JOIN speeches sp ON sp.agenda_item_id = ai.id
        JOIN sessions se ON ai.session_id = se.id
        WHERE se.date >= date('now', ? || ' days')
        GROUP BY ait.topic
        ORDER BY speech_count DESC
        LIMIT {int(limit)}
        """,
        (f"-{days}",),
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]