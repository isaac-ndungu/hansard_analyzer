import sqlite3
import logging
from pathlib import Path

from config import DB_PATH
from analyzer.database.seed import get_connection

logger = logging.getLogger(__name__)


def get_topic_trend(
    topic: str,
    period: str = "monthly",
    db_path: Path = DB_PATH,
) -> list[dict]:
    """
    Returns frequency of a topic over time grouped by month or week.
    Each dict contains: {period: str, count: int}.
    Ordered by period ascending.
    """
    if period == "weekly":
        strftime_format = "%Y-W%W"
    else:
        strftime_format = "%Y-%m"

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                strftime('{strftime_format}', se.date) AS period,
                COUNT(DISTINCT st.speech_id)           AS count
            FROM speech_topics st
            JOIN speeches sp ON st.speech_id = sp.id
            JOIN sessions se ON sp.session_id = se.id
            WHERE st.topic = ?
            GROUP BY period
            ORDER BY period ASC
            """,
            (topic,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_house_activity_trend(db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns total speeches and word count per month across all sessions.
    Each dict contains: {month: str, speech_count: int, word_count: int}.
    Ordered by month ascending.
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
            """,
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_participation_trend(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns monthly speech count for a specific MP.
    Each dict contains: {month: str, count: int}.
    Ordered by month ascending.
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


def get_trending_topics(days: int = 30, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns the top 10 most discussed topics in the last N days.
    Each dict contains: {topic: str, count: int}.
    Ordered by count descending.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                st.topic,
                COUNT(*) AS count
            FROM speech_topics st
            JOIN speeches sp ON st.speech_id = sp.id
            JOIN sessions se ON sp.session_id = se.id
            WHERE se.date >= date('now', ? || ' days')
            GROUP BY st.topic
            ORDER BY count DESC
            LIMIT 10
            """,
            (f"-{days}",),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_sessions_list(db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns all sessions ordered by date descending, with speech count per session.
    Each dict contains: {id, date, chamber, volume, issue, speech_count}.
    Used by the sessions list page.
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
                COUNT(sp.id) AS speech_count
            FROM sessions se
            LEFT JOIN speeches sp ON sp.session_id = se.id
            GROUP BY se.id
            ORDER BY se.date DESC
            """,
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_recent_sessions(limit: int = 5, db_path: Path = DB_PATH) -> list[dict]:
    """
    Returns the N most recent sessions for display on the homepage.
    Each dict contains: {id, date, chamber, volume, issue}.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, date, chamber, volume, issue
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