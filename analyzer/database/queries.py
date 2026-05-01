import sqlite3
from datetime import datetime, timezone
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
            datetime.now(timezone.utc).isoformat(),
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

    if session_time is None:
        cursor.execute(
            "SELECT * FROM sessions WHERE date = ? AND session_time IS NULL",
            (date,),
        )
    else:
        cursor.execute(
            "SELECT * FROM sessions WHERE date = ? AND session_time = ?",
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

    today = datetime.now(timezone.utc).date().isoformat()

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
            datetime.now(timezone.utc).isoformat(),
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


def insert_agenda_item(
    conn: sqlite3.Connection,
    session_id: int,
    title: str,
    item_type: str,
    sequence: int,
    raw_heading: str,
) -> int:
    """Inserts a new agenda item and returns its id."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO agenda_items (session_id, title, type, sequence, raw_heading, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            title,
            item_type,
            sequence,
            raw_heading,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_agenda_items_by_session(
    conn: sqlite3.Connection,
    session_id: int,
) -> list[dict]:
    """Returns all agenda items for a session ordered by sequence."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT ai.*, COUNT(sp.id) AS speech_count
        FROM agenda_items ai
        LEFT JOIN speeches sp ON sp.agenda_item_id = ai.id
        WHERE ai.session_id = ?
        GROUP BY ai.id
        ORDER BY ai.sequence ASC
        """,
        (session_id,),
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_agenda_item_by_id(
    conn: sqlite3.Connection,
    agenda_item_id: int,
) -> Optional[dict]:
    """Returns a single agenda item by id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM agenda_items WHERE id = ?",
        (agenda_item_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [d[0] for d in cursor.description]
    return dict(zip(columns, row))


def get_agenda_items_by_topic(
    conn: sqlite3.Connection,
    topic: str,
    item_type: Optional[str] = None,
) -> list[dict]:
    """
    Returns all agenda items tagged with a given topic.
    Optionally filter by type (BILL, MOTION, etc.)
    Each result includes session date and speech count.
    """
    cursor = conn.cursor()
    query = """
        SELECT ai.*, se.date, COUNT(sp.id) AS speech_count
        FROM agenda_items ai
        JOIN agenda_item_topics ait ON ait.agenda_item_id = ai.id
        JOIN sessions se ON ai.session_id = se.id
        LEFT JOIN speeches sp ON sp.agenda_item_id = ai.id
        WHERE ait.topic = ?
    """
    params: list = [topic]

    if item_type:
        query += " AND ai.type = ?"
        params.append(item_type)

    query += " GROUP BY ai.id ORDER BY se.date DESC"
    cursor.execute(query, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_speeches_by_agenda_item(
    conn: sqlite3.Connection,
    agenda_item_id: int,
) -> list[dict]:
    """Returns all speeches under a specific agenda item with member info."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sp.*, m.name AS member_name, m.constituency, m.party, m.id AS member_id
        FROM speeches sp
        JOIN members m ON sp.member_id = m.id
        WHERE sp.agenda_item_id = ?
        ORDER BY sp.id ASC
        """,
        (agenda_item_id,),
    )

    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def insert_agenda_item_topic(
    conn: sqlite3.Connection,
    agenda_item_id: int,
    topic: str,
    confidence: float,
) -> Optional[int]:
    """
    Tags an agenda item with a topic.
    Returns the new row id, or None if the tag already exists (UNIQUE constraint).
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO agenda_item_topics (agenda_item_id, topic, confidence)
            VALUES (?, ?, ?)
            """,
            (agenda_item_id, topic, confidence),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_topics_for_agenda_item(
    conn: sqlite3.Connection,
    agenda_item_id: int,
) -> list[dict]:
    """Returns all topics tagged against a given agenda item."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT topic, confidence FROM agenda_item_topics
        WHERE agenda_item_id = ?
        ORDER BY confidence DESC
        """,
        (agenda_item_id,),
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_topic_agenda_item_counts(conn: sqlite3.Connection) -> list[dict]:
    """
    Returns all topics with the count of agenda items tagged with each.
    Used for the topics overview page.
    Each dict: {topic, count}
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT topic, COUNT(DISTINCT agenda_item_id) AS count
        FROM agenda_item_topics
        GROUP BY topic
        ORDER BY count DESC
        """
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_mp_agenda_items(
    conn: sqlite3.Connection,
    member_id: int,
) -> list[dict]:
    """
    Returns all agenda items an MP has spoken in, with session date and type.
    This replaces the old get_speeches_by_member for the MP profile page.
    Each dict: {agenda_item_id, title, type, date, speech_count, session_id}
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            ai.id AS agenda_item_id,
            ai.title,
            ai.type,
            ai.session_id,
            se.date,
            COUNT(sp.id) AS speech_count,
            GROUP_CONCAT(DISTINCT ait.topic) AS topics
        FROM speeches sp
        JOIN agenda_items ai ON sp.agenda_item_id = ai.id
        JOIN sessions se ON ai.session_id = se.id
        LEFT JOIN agenda_item_topics ait ON ait.agenda_item_id = ai.id
        WHERE sp.member_id = ?
        GROUP BY ai.id
        ORDER BY se.date DESC
        """,
        (member_id,),
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_or_create_bill(
    conn: sqlite3.Connection,
    title: str,
    agenda_item_id: Optional[int] = None,
    bill_number: Optional[str] = None,
    bill_year: Optional[int] = None,
    introduced_date: Optional[str] = None,
) -> int:
    """Returns existing bill id if title matches, otherwise creates a new record."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM bills WHERE title = ?", (title,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        """
        INSERT INTO bills
            (agenda_item_id, bill_number, bill_year, title,
             current_status, introduced_date, last_activity)
        VALUES (?, ?, ?, ?, 'In Progress', ?, ?)
        """,
        (agenda_item_id, bill_number, bill_year, title,
         introduced_date, introduced_date),
    )
    conn.commit()
    return cursor.lastrowid


def insert_bill_reading(
    conn: sqlite3.Connection,
    bill_id: int,
    session_id: int,
    reading: Optional[str],
    outcome: Optional[str],
    date: str,
) -> int:
    """Inserts a reading event for a bill and updates bill status if outcome is known."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bill_readings (bill_id, session_id, reading, outcome, date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (bill_id, session_id, reading, outcome, date),
    )
    if outcome == "Passed":
        conn.execute(
            "UPDATE bills SET current_status = 'Passed', last_activity = ? WHERE id = ?",
            (date, bill_id),
        )
    elif outcome == "Rejected":
        conn.execute(
            "UPDATE bills SET current_status = 'Rejected', last_activity = ? WHERE id = ?",
            (date, bill_id),
        )
    conn.commit()
    return cursor.lastrowid


def get_all_bills(conn: sqlite3.Connection) -> list[dict]:
    """Returns all bills with reading count and latest reading date, ordered by most recent."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            b.*,
            COUNT(br.id)    AS reading_count,
            MAX(br.date)    AS latest_reading_date
        FROM bills b
        LEFT JOIN bill_readings br ON br.bill_id = b.id
        GROUP BY b.id
        ORDER BY latest_reading_date DESC
        """
    )
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_bill_with_readings(
    conn: sqlite3.Connection,
    bill_id: int,
) -> Optional[dict]:
    """Returns a bill with all its readings and the sessions they appeared in."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    row = cursor.fetchone()
    if not row:
        return None
    columns = [d[0] for d in cursor.description]
    bill = dict(zip(columns, row))
    cursor.execute(
        """
        SELECT br.*, se.date, se.chamber
        FROM bill_readings br
        JOIN sessions se ON br.session_id = se.id
        WHERE br.bill_id = ?
        ORDER BY se.date ASC
        """,
        (bill_id,),
    )
    cols = [d[0] for d in cursor.description]
    bill["readings"] = [dict(zip(cols, r)) for r in cursor.fetchall()]
    return bill


def search_agenda_items(
    conn: sqlite3.Connection,
    keyword: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    item_type: Optional[str] = None,
) -> list[dict]:
    """
    Searches agenda item titles for a keyword.
    Returns matching agenda items with session info and speech counts.
    Each dict includes: id, title, type, date, speaker_count, speech_count, topics
    """
    cursor = conn.cursor()
    query = """
        SELECT
            ai.id,
            ai.title,
            ai.type,
            ai.session_id,
            se.date,
            COUNT(DISTINCT sp.member_id) AS speaker_count,
            COUNT(sp.id)                 AS speech_count,
            GROUP_CONCAT(DISTINCT ait.topic) AS topics
        FROM agenda_items ai
        JOIN sessions se ON ai.session_id = se.id
        LEFT JOIN speeches sp ON sp.agenda_item_id = ai.id
        LEFT JOIN agenda_item_topics ait ON ait.agenda_item_id = ai.id
        WHERE ai.title LIKE ?
    """
    params: list = [f"%{keyword}%"]
    if from_date:
        query += " AND se.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND se.date <= ?"
        params.append(to_date)
    if item_type:
        query += " AND ai.type = ?"
        params.append(item_type)
    query += " GROUP BY ai.id ORDER BY se.date DESC"
    cursor.execute(query, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def search_mp_participation(
    conn: sqlite3.Connection,
    keyword: str,
) -> list[dict]:
    """
    Returns MPs who have spoken in agenda items matching the keyword.
    Used for the secondary search results — 'MPs who spoke about X'.
    Each dict: {id, name, constituency, party, speech_count, agenda_items}
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT
            m.id,
            m.name,
            m.constituency,
            m.party,
            COUNT(sp.id) AS speech_count,
            GROUP_CONCAT(DISTINCT ai.title) AS agenda_items
        FROM speeches sp
        JOIN members m ON sp.member_id = m.id
        JOIN agenda_items ai ON sp.agenda_item_id = ai.id
        WHERE ai.title LIKE ?
        GROUP BY m.id
        ORDER BY speech_count DESC
        """,
        (f"%{keyword}%",),
    )
    columns = [d[0] for d in cursor.description]
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
    """Returns row counts for all primary tables."""
    cursor = conn.cursor()
    stats = {}

    for table in ("sessions", "members", "agenda_items", "speeches",
                  "agenda_item_topics", "bills"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]
        
    return stats