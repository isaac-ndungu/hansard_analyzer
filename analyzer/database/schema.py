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

AGENDA_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS agenda_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    title        TEXT NOT NULL,
    type         TEXT NOT NULL,
    sequence     INTEGER,
    raw_heading  TEXT,
    created_at   TEXT
);
"""

SPEECHES_TABLE = """
CREATE TABLE IF NOT EXISTS speeches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    member_id       INTEGER NOT NULL REFERENCES members(id),
    agenda_item_id  INTEGER REFERENCES agenda_items(id),
    section         TEXT,
    content         TEXT NOT NULL,
    word_count      INTEGER,
    sentiment_score REAL,
    created_at      TEXT
);
"""

AGENDA_ITEM_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS agenda_item_topics (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id),
    topic          TEXT NOT NULL,
    confidence     REAL,
    UNIQUE(agenda_item_id, topic)
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

BILLS_TABLE = """
CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agenda_item_id  INTEGER REFERENCES agenda_items(id),
    bill_number     TEXT,
    bill_year       INTEGER,
    title           TEXT NOT NULL,
    sponsor_id      INTEGER REFERENCES members(id),
    current_status  TEXT,
    introduced_date TEXT,
    last_activity   TEXT
);
"""

BILL_READINGS_TABLE = """
CREATE TABLE IF NOT EXISTS bill_readings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id    INTEGER NOT NULL REFERENCES bills(id),
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    reading    TEXT,
    outcome    TEXT,
    date       TEXT
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


# Index Definitions

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_speeches_member      ON speeches(member_id);",
    "CREATE INDEX IF NOT EXISTS idx_speeches_session     ON speeches(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_speeches_agenda      ON speeches(agenda_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_speeches_section     ON speeches(section);",
    "CREATE INDEX IF NOT EXISTS idx_agenda_items_session ON agenda_items(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_agenda_items_type    ON agenda_items(type);",
    "CREATE INDEX IF NOT EXISTS idx_agenda_item_topics   ON agenda_item_topics(agenda_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_agenda_topic_name    ON agenda_item_topics(topic);",
    "CREATE INDEX IF NOT EXISTS idx_bills_agenda         ON bills(agenda_item_id);",
]


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    tables = [
        SESSIONS_TABLE,
        MEMBERS_TABLE,
        AGENDA_ITEMS_TABLE,
        SPEECHES_TABLE,
        AGENDA_ITEM_TOPICS_TABLE,
        AI_SUMMARIES_TABLE,
        BILLS_TABLE,
        BILL_READINGS_TABLE,
        TRACKED_TOPICS_TABLE,
    ]

    for table_sql in tables:
        cursor.execute(table_sql)

    for index_sql in INDEXES:
        cursor.execute(index_sql)

    conn.commit()