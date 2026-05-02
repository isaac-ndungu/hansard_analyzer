import sqlite3
import logging
from pathlib import Path

from config import DB_PATH
from analyzer.database.seed import get_connection

logger = logging.getLogger(__name__)


# MP Speech Count

def get_mp_speech_count(member_id: int, db_path: Path = DB_PATH) -> int:
    """Returns total number of speeches given by this MP across all sessions."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM speeches WHERE member_id = ?",
            (member_id,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()

# MP Word Count

def get_mp_word_count(member_id: int, db_path: Path = DB_PATH) -> int:
    """Returns total words spoken by this MP across all sessions."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(word_count), 0) FROM speeches WHERE member_id = ?",
            (member_id,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


# MP Sessions Attended

def get_mp_sessions_attended(member_id: int, db_path: Path = DB_PATH) -> int:
    """Returns number of unique sessions where this MP gave at least one speech."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT session_id) FROM speeches WHERE member_id = ?",
            (member_id,),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


# MP Average Speech Length

def get_mp_avg_speech_length(member_id: int, db_path: Path = DB_PATH) -> float:
    """Returns average word count per speech for this MP, rounded to 2 decimal places."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT AVG(word_count) FROM speeches WHERE member_id = ?",
            (member_id,),
        )
        result = cursor.fetchone()[0]
        return round(result, 2) if result is not None else 0.0
    finally:
        conn.close()


# MP Active Sections

def get_mp_active_sections(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Returns the top 5 sections this MP speaks in most frequently, ordered by count descending."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT section, COUNT(*) AS count
            FROM speeches
            WHERE member_id = ?
            GROUP BY section
            ORDER BY count DESC
            LIMIT 5
            """,
            (member_id,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# MP Activity Over Time

def get_mp_activity_over_time(member_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Returns monthly speech count for this MP, ordered by month ascending."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                strftime('%Y-%m', se.date) AS month,
                COUNT(*) AS count
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


# Most Active MPs

def get_most_active_mps(limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Returns top N MPs by total speech count, ordered by speech count descending."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                m.id AS member_id,
                m.name,
                m.constituency,
                m.party,
                COUNT(sp.id)                    AS speech_count,
                COALESCE(SUM(sp.word_count), 0) AS word_count
            FROM members m
            LEFT JOIN speeches sp ON sp.member_id = m.id
            GROUP BY m.id
            ORDER BY speech_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# MP Recent Speeches

def get_mp_recent_speeches(
    member_id: int,
    limit: int = 5,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Returns the most recent N speeches by this MP with session date and section."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                sp.id,
                sp.content,
                sp.word_count,
                sp.section,
                ai.title AS agenda_item,
                sp.sentiment_score,
                se.date
            FROM speeches sp
            LEFT JOIN agenda_items ai ON sp.agenda_item_id = ai.id
            JOIN sessions se ON sp.session_id = se.id
            WHERE sp.member_id = ?
            ORDER BY se.date DESC
            LIMIT ?
            """,
            (member_id, limit),
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


# MP Full Profile

def get_mp_full_profile(member_id: int, db_path: Path = DB_PATH) -> dict:
    """Aggregates all MP metrics into a single dict for use in Flask routes."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        if row is None:
            return {}
        columns = [d[0] for d in cursor.description]
        member = dict(zip(columns, row))
    finally:
        conn.close()

    return {
        **member,
        "speech_count":       get_mp_speech_count(member_id, db_path),
        "word_count":         get_mp_word_count(member_id, db_path),
        "avg_speech_length":  get_mp_avg_speech_length(member_id, db_path),
        "sessions_attended":  get_mp_sessions_attended(member_id, db_path),
        "active_sections":    get_mp_active_sections(member_id, db_path),
        "activity_over_time": get_mp_activity_over_time(member_id, db_path),
        "recent_speeches":    get_mp_recent_speeches(member_id, 5, db_path),
    }