import sqlite3
from pathlib import Path


# Table Definitions

SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    chamber           TEXT NOT NULL,
    parliament_number INTEGER,
    volume            INTEGER,
    issue             INTEGER,
    session_time      TEXT,
    pdf_path          TEXT,
    parsed_at         TEXT
);
"""

MEMBERS_TABLE = """
CREATE TABLE IF NOT EXISTS members (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    constituency TEXT,
    party        TEXT,
    first_seen   TEXT,
    last_seen    TEXT
);
"""

SPEECHES_TABLE = """
CREATE TABLE IF NOT EXISTS speeches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    member_id       INTEGER NOT NULL REFERENCES members(id),
    section         TEXT,
    agenda_item     TEXT,
    content         TEXT NOT NULL,
    word_count      INTEGER,
    sentiment_score REAL,
    created_at      TEXT
);
"""

SPEECH_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS speech_topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    speech_id  INTEGER NOT NULL REFERENCES speeches(id),
    topic      TEXT NOT NULL,
    confidence REAL
);
"""

TRACKED_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS tracked_topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword    TEXT NOT NULL,
    email      TEXT,
    created_at TEXT
);
"""

AI_SUMMARIES_TABLE = """
CREATE TABLE IF NOT EXISTS ai_summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    summary      TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    UNIQUE(entity_type, entity_id)
);
"""


# Index Definitions

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_speeches_member  ON speeches(member_id);",
    "CREATE INDEX IF NOT EXISTS idx_speeches_session ON speeches(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_speeches_section ON speeches(section);",
    "CREATE INDEX IF NOT EXISTS idx_speech_topics_topic ON speech_topics(topic);",
]


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    tables = [
        SESSIONS_TABLE,
        MEMBERS_TABLE,
        SPEECHES_TABLE,
        SPEECH_TOPICS_TABLE,
        TRACKED_TOPICS_TABLE,
        AI_SUMMARIES_TABLE
    ]

    for table_sql in tables:
        cursor.execute(table_sql)

    for index_sql in INDEXES:
        cursor.execute(index_sql)

    conn.commit()