import sqlite3
import pytest
from datetime import datetime


# In-memory database fixture

@pytest.fixture
def conn():
    """Fresh in-memory SQLite database with schema for every test."""
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE sessions (
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
        CREATE TABLE members (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            constituency TEXT,
            party        TEXT,
            first_seen   TEXT,
            last_seen    TEXT
        );
        CREATE TABLE speeches (
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
        CREATE TABLE agenda_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES sessions(id),
            title        TEXT NOT NULL,
            type         TEXT NOT NULL,
            sequence     INTEGER,
            raw_heading  TEXT,
            created_at   TEXT
        );
        CREATE TABLE agenda_item_topics (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id),
            topic          TEXT NOT NULL,
            confidence     REAL,
            UNIQUE(agenda_item_id, topic)
        );
        CREATE TABLE bills (
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
    """)
    yield connection
    connection.close()


# Session query tests─

class TestInsertSession:
    def test_returns_integer_id(self, conn):
        from analyzer.database.queries import insert_session
        result = insert_session(conn, "2026-04-14", "National Assembly", 13, 5, 28, None, "pdfs/test.pdf")
        assert isinstance(result, int)
        assert result > 0

    def test_session_stored_in_database(self, conn):
        from analyzer.database.queries import insert_session
        insert_session(conn, "2026-04-14", "National Assembly", 13, 5, 28, None, "pdfs/test.pdf")
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        assert row[0] == 1

    def test_multiple_sessions_get_unique_ids(self, conn):
        from analyzer.database.queries import insert_session
        id1 = insert_session(conn, "2026-04-07", "National Assembly", 13, 5, 27, None, "pdfs/s1.pdf")
        id2 = insert_session(conn, "2026-04-14", "National Assembly", 13, 5, 28, None, "pdfs/s2.pdf")
        assert id1 != id2


class TestGetSessionByDateAndTime:
    def test_returns_dict_for_existing_session(self, conn):
        from analyzer.database.queries import insert_session, get_session_by_date_and_time
        insert_session(conn, "2026-04-14", "National Assembly", 13, 5, 28, None, "pdfs/test.pdf")
        result = get_session_by_date_and_time(conn, "2026-04-14", None)
        assert result is not None
        assert result["date"] == "2026-04-14"

    def test_returns_none_for_missing_session(self, conn):
        from analyzer.database.queries import get_session_by_date_and_time
        result = get_session_by_date_and_time(conn, "2099-01-01", None)
        assert result is None


# Member query tests

class TestGetOrCreateMember:
    def test_returns_integer_id(self, conn):
        from analyzer.database.queries import get_or_create_member
        result = get_or_create_member(conn, "Kimani Ichung'wah", "Kikuyu", "UDA")
        assert isinstance(result, int)
        assert result > 0

    def test_deduplicates_same_name_and_constituency(self, conn):
        from analyzer.database.queries import get_or_create_member
        id1 = get_or_create_member(conn, "Millie Odhiambo", "Suba North", "ODM")
        id2 = get_or_create_member(conn, "Millie Odhiambo", "Suba North", "ODM")
        assert id1 == id2
        row = conn.execute("SELECT COUNT(*) FROM members").fetchone()
        assert row[0] == 1

    def test_different_constituency_creates_new_record(self, conn):
        from analyzer.database.queries import get_or_create_member
        id1 = get_or_create_member(conn, "John Doe", "Nairobi", "UDA")
        id2 = get_or_create_member(conn, "John Doe", "Mombasa", "UDA")
        assert id1 != id2

    def test_updates_party_on_second_call(self, conn):
        from analyzer.database.queries import get_or_create_member
        member_id = get_or_create_member(conn, "Jane Doe", "Nairobi", "UDA")
        get_or_create_member(conn, "Jane Doe", "Nairobi", "ODM")
        row = conn.execute("SELECT party FROM members WHERE id = ?", (member_id,)).fetchone()
        assert row[0] == "ODM"


class TestGetOrCreateBill:
    def test_creates_bill_record_for_title(self, conn):
        
        from analyzer.database.queries import get_or_create_bill

        conn.execute(
            "INSERT INTO sessions (date, chamber, pdf_path) VALUES ('2026-04-07', 'National Assembly', 'pdfs/test.pdf')"
        )
        conn.execute(
            "INSERT INTO agenda_items (session_id, title, type, sequence) VALUES (1, 'Test Item', 'BILL', 1)"
        )

        from analyzer.database.queries import get_or_create_bill
        bill_id = get_or_create_bill(
            conn,
            title="Quality Healthcare and Patient Safety Bill",
            agenda_item_id=1,
            bill_number="8",
            bill_year=2026,
            introduced_date="2026-04-14",
        )
        assert isinstance(bill_id, int)
        row = conn.execute("SELECT bill_number, bill_year FROM bills WHERE id = ?", (bill_id,)).fetchone()
        assert row == ("8", 2026)

    def test_updates_existing_bill_with_missing_metadata(self, conn):
        
        from analyzer.database.queries import get_or_create_bill
        conn.execute(
                "INSERT INTO sessions (date, chamber, pdf_path) VALUES ('2026-04-07', 'National Assembly', 'pdfs/test.pdf')"
            )
        conn.execute(
                "INSERT INTO agenda_items (session_id, title, type, sequence) VALUES (1, 'Test Item', 'BILL', 1)"
            )
        bill_id = get_or_create_bill(
            conn,
            title="Quality Healthcare and Patient Safety Bill",
            agenda_item_id=1,
            bill_number=None,
            bill_year=None,
            introduced_date="2026-04-14",
        )
        assert bill_id > 0
        updated_id = get_or_create_bill(
            conn,
            title="Quality Healthcare and Patient Safety Bill",
            agenda_item_id=1,
            bill_number="8",
            bill_year=2026,
            introduced_date="2026-04-14",
        )
        assert updated_id == bill_id
        row = conn.execute("SELECT bill_number, bill_year FROM bills WHERE id = ?", (bill_id,)).fetchone()
        assert row == ("8", 2026)


class TestGetAllMembers:
    def test_returns_list(self, conn):
        from analyzer.database.queries import get_all_members
        result = get_all_members(conn)
        assert isinstance(result, list)

    def test_returns_empty_list_when_no_members(self, conn):
        from analyzer.database.queries import get_all_members
        assert get_all_members(conn) == []

    def test_returns_all_members_ordered_by_name(self, conn):
        from analyzer.database.queries import get_or_create_member, get_all_members
        get_or_create_member(conn, "Zara Ahmed", "Mombasa", "ODM")
        get_or_create_member(conn, "Anna Wanjiru", "Nairobi", "UDA")
        members = get_all_members(conn)
        names = [m["name"] for m in members]
        assert names == sorted(names)


class TestGetMemberByName:
    def test_finds_by_partial_name(self, conn):
        from analyzer.database.queries import get_or_create_member, get_member_by_name
        get_or_create_member(conn, "Kimani Ichung'wah", "Kikuyu", "UDA")
        result = get_member_by_name(conn, "Kimani")
        assert result is not None
        assert "Kimani" in result["name"]

    def test_returns_none_for_unknown_name(self, conn):
        from analyzer.database.queries import get_member_by_name
        assert get_member_by_name(conn, "Nobody Knowsme") is None


# Speech query tests

@pytest.fixture
def seeded_conn(conn):
    """Connection with one session, two members, and three speeches."""
    from analyzer.database.queries import insert_session, get_or_create_member, insert_speech
    s_id = insert_session(conn, "2026-04-14", "National Assembly", 13, 5, 28, None, "pdfs/test.pdf")
    m1 = get_or_create_member(conn, "Hon MP One", "Nairobi", "UDA")
    m2 = get_or_create_member(conn, "Hon MP Two", "Mombasa", "ODM")
    insert_speech(conn, s_id, m1, None, "BILLS", "We support the healthcare bill fully.", 7)
    insert_speech(conn, s_id, m1, None, "PETITIONS", "Roads in this county are terrible.", 7)
    insert_speech(conn, s_id, m2, None, "BILLS", "The education budget must be increased.", 7)
    return conn


class TestInsertSpeech:
    def test_returns_integer_id(self, seeded_conn):
        from analyzer.database.queries import insert_speech
        s_id = seeded_conn.execute("SELECT id FROM sessions LIMIT 1").fetchone()[0]
        m_id = seeded_conn.execute("SELECT id FROM members LIMIT 1").fetchone()[0]
        result = insert_speech(seeded_conn, s_id, m_id, None, "MOTIONS", "I support this motion.", 5)
        assert isinstance(result, int)

    def test_speech_stored_in_database(self, seeded_conn):
        row = seeded_conn.execute("SELECT COUNT(*) FROM speeches").fetchone()
        assert row[0] == 3


class TestGetSpeechesByMember:
    def test_filters_by_member_id(self, seeded_conn):
        from analyzer.database.queries import get_speeches_by_member
        m1_id = seeded_conn.execute("SELECT id FROM members WHERE name = 'Hon MP One'").fetchone()[0]
        result = get_speeches_by_member(seeded_conn, m1_id)
        assert len(result) == 2
        assert all(r["member_id"] == m1_id for r in result)

    def test_returns_empty_for_unknown_member(self, seeded_conn):
        from analyzer.database.queries import get_speeches_by_member
        assert get_speeches_by_member(seeded_conn, 999) == []

    def test_ordered_by_date_descending(self, seeded_conn):
        from analyzer.database.queries import get_speeches_by_member
        m1_id = seeded_conn.execute("SELECT id FROM members LIMIT 1").fetchone()[0]
        result = get_speeches_by_member(seeded_conn, m1_id)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True)


# Database stats tests

class TestGetDatabaseStats:
    def test_returns_dict(self, seeded_conn):
        from analyzer.database.queries import get_database_stats
        result = get_database_stats(seeded_conn)
        assert isinstance(result, dict)

    def test_counts_all_tables(self, seeded_conn):
        from analyzer.database.queries import get_database_stats
        result = get_database_stats(seeded_conn)
        assert "sessions" in result
        assert "members" in result
        assert "agenda_items" in result
        assert "speeches" in result
        assert "agenda_item_topics" in result

    def test_correct_counts(self, seeded_conn):
        from analyzer.database.queries import get_database_stats
        result = get_database_stats(seeded_conn)
        assert result["sessions"] == 1
        assert result["members"] == 2
        assert result["speeches"] == 3