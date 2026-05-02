import sqlite3
import logging
from pathlib import Path

from config import DB_PATH
from analyzer.database.seed import get_connection

logger = logging.getLogger(__name__)


# Topic Trend

def get_topic_trend(
    topic: str,
    period: str = "monthly",
    db_path: Path = DB_PATH,
) -> list[dict]:
    """
    Returns frequency of a topic over time grouped by month or week.
    Each dict contains: {period: str, count: int}.
    """
    strftime_format = "%Y-W%W" if period == "weekly" else "%Y-%m"

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                strftime('{strftime_format}', se.date) AS period,
                COUNT(DISTINCT sp.id)                 AS count
            FROM agenda_item_topics ait
            JOIN agenda_items ai ON ait.agenda_item_id = ai.id
            JOIN speeches sp ON sp.agenda_item_id = ai.id
            JOIN sessions se ON sp.session_id = se.id
            WHERE ait.topic = ?
            GROUP BY period
            ORDER BY period ASC
            """,
            (topic,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# House Activity Trend

def get_house_activity_trend(db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns total speeches and word count per month across all sessions.
    Each dict contains: {month: str, speech_count: int, word_count: int}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                strftime('%Y-%m', se.date)      AS month,
                COUNT(sp.id)                    AS speech_count,
                COALESCE(SUM(sp.word_count), 0) AS word_count
            FROM speeches sp
            JOIN sessions se ON sp.session_id = se.id
            GROUP BY month
            ORDER BY month ASC
            """
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# MP Participation Trend

def get_participation_trend(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns monthly speech count for a specific MP.
    Each dict contains: {month: str, count: int}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                strftime('%Y-%m', se.date) AS month,
                COUNT(sp.id)               AS count
            FROM speeches sp
            JOIN sessions se ON sp.session_id = se.id
            WHERE sp.member_id = ?
            GROUP BY month
            ORDER BY month ASC
            """,
            (member_id,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# Trending Topics

def get_trending_topics(days: int = 30, limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns the most discussed topics in the last N days, up to the given limit.
    Each dict contains: {topic: str, count: int}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                ait.topic,
                COUNT(DISTINCT sp.id) AS count
            FROM agenda_item_topics ait
            JOIN agenda_items ai ON ait.agenda_item_id = ai.id
            JOIN speeches sp ON sp.agenda_item_id = ai.id
            JOIN sessions se ON sp.session_id = se.id
            WHERE se.date >= date('now', ? || ' days')
            GROUP BY ait.topic
            ORDER BY count DESC
            LIMIT {int(limit)}
            """,
            (f"-{days}",),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# All Sessions List

def get_all_sessions_list(db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns all sessions ordered by date descending with speech count per session.
    Each dict contains: {id, date, chamber, volume, issue, session_time, speech_count}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                se.id,
                se.date,
                se.chamber,
                se.volume,
                se.issue,
                se.session_time,
                COUNT(sp.id) AS speech_count
            FROM sessions se
            LEFT JOIN speeches sp ON sp.session_id = se.id
            GROUP BY se.id
            ORDER BY se.date DESC
            """
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# Recent Sessions

def get_recent_sessions(limit: int = 5, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns the N most recent sessions for the homepage latest sessions list.
    Each dict contains: {id, date, chamber, volume, issue, session_time}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, date, chamber, volume, issue, session_time
            FROM sessions
            ORDER BY date DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()