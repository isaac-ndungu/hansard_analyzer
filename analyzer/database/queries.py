import sqlite3
from datetime import datetime
from typing import Optional


# Session Queries

def insert_session(
    conn: sqlite3.Connection,
    date: str,
    chamber: str,
    parliament_number: Optional[int],
    volume: Optional[int],
    issue: Optional[int],
    session_time: Optional[str],
    pdf_path: str,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO sessions
            (date, chamber, parliament_number, volume, issue, session_time, pdf_path, parsed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            date,
            chamber,
            parliament_number,
            volume,
            issue,
            session_time,
            pdf_path,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_session_by_date_and_time(
    conn: sqlite3.Connection,
    date: str,
    session_time: Optional[str],
) -> Optional[dict]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessions WHERE date = ? AND session_time IS ?",
        (date, session_time),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


# Member Queries

def get_or_create_member(
    conn: sqlite3.Connection,
    name: str,
    constituency: str,
    party: str,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM members WHERE name = ? AND constituency = ?",
        (name, constituency),
    )
    row = cursor.fetchone()

    today = datetime.utcnow().date().isoformat()

    if row is not None:
        member_id = row[0]
        cursor.execute(
            "UPDATE members SET last_seen = ?, party = ? WHERE id = ?",
            (today, party, member_id),
        )
        conn.commit()
        return member_id

    cursor.execute(
        """
        INSERT INTO members (name, constituency, party, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, constituency, party, today, today),
    )
    conn.commit()
    return cursor.lastrowid


def get_all_members(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members ORDER BY name")
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_member_by_name(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM members WHERE name LIKE ?",
        (f"%{name}%",),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


# Speech Queries

def insert_speech(
    conn: sqlite3.Connection,
    session_id: int,
    member_id: int,
    section: str,
    agenda_item: Optional[str],
    content: str,
    word_count: int,
    sentiment_score: Optional[float] = None,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO speeches (session_id, member_id, section, agenda_item, content, word_count, sentiment_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            member_id,
            section,
            agenda_item,
            content,
            word_count,
            sentiment_score,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_speeches_by_member(
    conn: sqlite3.Connection,
    member_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    cursor = conn.cursor()

    query = """
        SELECT sp.*, se.date, se.chamber
        FROM speeches sp
        JOIN sessions se ON sp.session_id = se.id
        WHERE sp.member_id = ?
    """
    params: list = [member_id]

    if from_date is not None:
        query += " AND se.date >= ?"
        params.append(from_date)

    if to_date is not None:
        query += " AND se.date <= ?"
        params.append(to_date)

    query += " ORDER BY se.date DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_speeches_by_topic(
    conn: sqlite3.Connection,
    topic: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    cursor = conn.cursor()

    query = """
        SELECT sp.*, se.date, m.name AS member_name, m.constituency, m.party
        FROM speeches sp
        JOIN sessions se ON sp.session_id = se.id
        JOIN members m ON sp.member_id = m.id
        JOIN speech_topics st ON st.speech_id = sp.id
        WHERE st.topic = ?
    """
    params: list = [topic]

    if from_date is not None:
        query += " AND se.date >= ?"
        params.append(from_date)

    if to_date is not None:
        query += " AND se.date <= ?"
        params.append(to_date)

    query += " ORDER BY se.date DESC"

    cursor.execute(query, params)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def search_speeches(conn: sqlite3.Connection, keyword: str) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sp.id, sp.content, sp.word_count, se.date, m.name AS member_name, m.constituency
        FROM speeches sp
        JOIN sessions se ON sp.session_id = se.id
        JOIN members m ON sp.member_id = m.id
        WHERE sp.content LIKE ?
        ORDER BY se.date DESC
        """,
        (f"%{keyword}%",),
    )
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Speech Topic Queries

def insert_speech_topic(
    conn: sqlite3.Connection,
    speech_id: int,
    topic: str,
    confidence: float,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO speech_topics (speech_id, topic, confidence) VALUES (?, ?, ?)",
        (speech_id, topic, confidence),
    )
    conn.commit()
    return cursor.lastrowid


# Summary Queries

def get_database_stats(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    stats = {}

    for table in ("sessions", "members", "speeches", "speech_topics"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]

    return stats