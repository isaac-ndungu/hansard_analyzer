import pytest
import sqlite3
from unittest.mock import patch, MagicMock


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL, chamber TEXT NOT NULL,
            parliament_number INTEGER, volume INTEGER, issue INTEGER,
            session_time TEXT, pdf_path TEXT, parsed_at TEXT
        );
        CREATE TABLE members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, constituency TEXT, party TEXT,
            first_seen TEXT, last_seen TEXT
        );
        CREATE TABLE agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, title TEXT NOT NULL,
            type TEXT NOT NULL, sequence INTEGER, raw_heading TEXT, created_at TEXT
        );
        CREATE TABLE speeches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, member_id INTEGER NOT NULL,
            agenda_item_id INTEGER, section TEXT, content TEXT NOT NULL,
            word_count INTEGER, sentiment_score REAL, created_at TEXT
        );
        CREATE TABLE agenda_item_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agenda_item_id INTEGER NOT NULL, topic TEXT NOT NULL, confidence REAL
        );
        CREATE TABLE ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
            summary TEXT NOT NULL, generated_at TEXT NOT NULL,
            UNIQUE(entity_type, entity_id)
        );
        INSERT INTO sessions (date, chamber, pdf_path, parsed_at)
            VALUES ('2026-04-14', 'National Assembly', 'test.pdf', '2026-04-14');
        INSERT INTO members (name, constituency, party, first_seen, last_seen)
            VALUES ('Test MP', 'Test Constituency', 'UDA', '2026-04-14', '2026-04-14');
        INSERT INTO agenda_items (session_id, title, type, sequence, raw_heading, created_at)
            VALUES (1, 'Quality Healthcare Bill', 'BILL', 1,
                    'THE QUALITY HEALTHCARE BILL', '2026-04-14');
        INSERT INTO speeches (session_id, member_id, agenda_item_id, section,
                              content, word_count, sentiment_score, created_at)
            VALUES (1, 1, 1, 'BILLS',
                    'This healthcare bill is very important for all Kenyans.',
                    10, 0.5, '2026-04-14');
        INSERT INTO agenda_item_topics (agenda_item_id, topic, confidence)
            VALUES (1, 'healthcare', 0.8);
    """)
    conn.commit()
    conn.close()
    return path


class TestSummarizeSessionFallback:

    def test_returns_string_when_no_api_key(self, db_path):
        from analyzer.ai.summarizer import summarize_session
        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", None):
            result = summarize_session(1, db_path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_fallback_message_when_no_key(self, db_path):
        from analyzer.ai.summarizer import summarize_session
        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", None):
            result = summarize_session(1, db_path)
        assert "could not be generated" in result.lower()

    def test_returns_fallback_for_nonexistent_session(self, db_path):
        from analyzer.ai.summarizer import summarize_session
        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", None):
            result = summarize_session(9999, db_path)
        assert isinstance(result, str)

    def test_with_mocked_gemini_returns_summary(self, db_path):
        from analyzer.ai.summarizer import summarize_session
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a mock summary of the healthcare bill debate."
        mock_client.models.generate_content.return_value = mock_response

        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", "fake-key"):
            with patch("analyzer.ai.summarizer._get_client", return_value=mock_client):
                result = summarize_session(1, db_path)

        assert isinstance(result, str)
        assert len(result) > 0


class TestSummarizeSession:

    def test_returns_fallback_when_no_api_key(self, db_path):
        from analyzer.ai.summarizer import summarize_session
        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", None):
            result = summarize_session(1, db_path)
        assert isinstance(result, str)
        assert "could not be generated" in result.lower()


class TestSummarizeMp:

    def test_returns_fallback_when_no_api_key(self, db_path):
        from analyzer.ai.summarizer import summarize_mp
        with patch("analyzer.ai.summarizer.GEMINI_API_KEY", None):
            result = summarize_mp(1, db_path)
        assert isinstance(result, str)
        assert "could not be generated" in result.lower()


class TestCache:

    def test_get_cached_returns_none_when_empty(self, db_path):
        from analyzer.ai.cache import get_cached_summary
        assert get_cached_summary("agenda_item", 1, db_path) is None

    def test_save_and_retrieve(self, db_path):
        from analyzer.ai.cache import save_summary, get_cached_summary
        save_summary("agenda_item", 1, "This is a cached summary.", db_path)
        result = get_cached_summary("agenda_item", 1, db_path)
        assert result is not None
        assert result["summary"] == "This is a cached summary."
        assert "generated_at" in result

    def test_stale_cache_returns_none(self, db_path):
        from analyzer.ai.cache import get_cached_summary, CACHE_TTL_DAYS
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 1)).isoformat()
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT OR REPLACE INTO ai_summaries "
            "(entity_type, entity_id, summary, generated_at) VALUES (?,?,?,?)",
            ("agenda_item", 99, "Old summary", old_date),
        )
        conn.commit()
        conn.close()
        assert get_cached_summary("agenda_item", 99, db_path) is None

    def test_save_replaces_existing(self, db_path):
        from analyzer.ai.cache import save_summary, get_cached_summary
        save_summary("agenda_item", 1, "First summary.", db_path)
        save_summary("agenda_item", 1, "Second summary.", db_path)
        result = get_cached_summary("agenda_item", 1, db_path)
        assert result["summary"] == "Second summary."

    def test_is_cache_stale_with_fresh_date(self):
        from analyzer.ai.cache import is_cache_stale
        from datetime import datetime
        assert is_cache_stale(datetime.now().isoformat()) is False

    def test_is_cache_stale_with_old_date(self):
        from analyzer.ai.cache import is_cache_stale, CACHE_TTL_DAYS
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 1)).isoformat()
        assert is_cache_stale(old) is True

    def test_is_cache_stale_with_invalid_string(self):
        from analyzer.ai.cache import is_cache_stale
        assert is_cache_stale("not-a-date") is True
