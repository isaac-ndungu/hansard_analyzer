import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch


# In-memory database fixture

@pytest.fixture
def db_conn():
    """
    Creates a fresh in-memory SQLite database with schema and seed data
    for every test that requests it. Never touches hansard.db.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
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
    """)

    # Seed sessions
    conn.execute(
        "INSERT INTO sessions (date, chamber, volume, issue, pdf_path, parsed_at) "
        "VALUES ('2026-04-07', 'National Assembly', 5, 27, 'pdfs/s1.pdf', '2026-04-07T12:00:00')"
    )
    conn.execute(
        "INSERT INTO sessions (date, chamber, volume, issue, pdf_path, parsed_at) "
        "VALUES ('2026-04-14', 'National Assembly', 5, 28, 'pdfs/s2.pdf', '2026-04-14T12:00:00')"
    )

    # Seed members
    conn.execute(
        "INSERT INTO members (name, constituency, party, first_seen, last_seen) "
        "VALUES ('Kimani Ichung''wah', 'Kikuyu', 'UDA', '2026-04-07', '2026-04-14')"
    )
    conn.execute(
        "INSERT INTO members (name, constituency, party, first_seen, last_seen) "
        "VALUES ('Millie Odhiambo', 'Suba North', 'ODM', '2026-04-07', '2026-04-07')"
    )

    # Seed agenda items
    conn.execute(
        "INSERT INTO agenda_items (session_id, title, type, sequence, raw_heading, created_at) "
        "VALUES (1, 'Healthcare Bill', 'BILL', 1, 'Healthcare Bill', '2026-04-07T13:00:00')"
    )

    # Seed speeches — member 1 has 3 speeches, member 2 has 1
    conn.execute(
        "INSERT INTO speeches (session_id, member_id, agenda_item_id, section, content, word_count, sentiment_score, created_at) "
        "VALUES (1, 1, 1, 'BILLS', 'The healthcare bill is excellent and we support it fully.', 10, 0.6, '2026-04-07T14:00:00')"
    )
    conn.execute(
        "INSERT INTO speeches (session_id, member_id, agenda_item_id, section, content, word_count, sentiment_score, created_at) "
        "VALUES (1, 1, 1, 'PETITIONS', 'Roads in my constituency are in a terrible state of disrepair.', 11, -0.3, '2026-04-07T15:00:00')"
    )
    conn.execute(
        "INSERT INTO speeches (session_id, member_id, agenda_item_id, section, content, word_count, sentiment_score, created_at) "
        "VALUES (2, 1, 1, 'BILLS', 'The education reforms are good and necessary for our children.', 11, 0.5, '2026-04-14T14:00:00')"
    )
    conn.execute(
        "INSERT INTO speeches (session_id, member_id, agenda_item_id, section, content, word_count, sentiment_score, created_at) "
        "VALUES (1, 2, NULL, 'PETITIONS', 'Human rights violations continue to be a serious concern for all Kenyans.', 13, -0.1, '2026-04-07T14:30:00')"
    )

    # Seed agenda item topics
    conn.execute("INSERT INTO agenda_item_topics (agenda_item_id, topic, confidence) VALUES (1, 'healthcare', 0.8)")
    conn.execute("INSERT INTO agenda_item_topics (agenda_item_id, topic, confidence) VALUES (1, 'infrastructure', 0.6)")
    conn.execute("INSERT INTO agenda_item_topics (agenda_item_id, topic, confidence) VALUES (1, 'education', 0.7)")

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def db_path(db_conn, tmp_path):
    """
    Writes the in-memory database to a temp file so analytics functions
    that open their own connection can use it.
    """
    path = tmp_path / "test_hansard.db"
    dest = sqlite3.connect(path)
    db_conn.backup(dest)
    dest.close()
    return path


# mp_stats tests

class TestGetMpSpeechCount:
    def test_returns_correct_count(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_speech_count
        assert get_mp_speech_count(1, db_path) == 3

    def test_returns_zero_for_unknown_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_speech_count
        assert get_mp_speech_count(999, db_path) == 0

    def test_returns_integer(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_speech_count
        result = get_mp_speech_count(1, db_path)
        assert isinstance(result, int)


class TestGetMpWordCount:
    def test_sums_correctly(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_word_count
        # member 1 has word counts 10 + 11 + 11 = 32
        assert get_mp_word_count(1, db_path) == 32

    def test_returns_zero_for_unknown_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_word_count
        assert get_mp_word_count(999, db_path) == 0


class TestGetMpSessionsAttended:
    def test_counts_unique_sessions_only(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_sessions_attended
        # member 1 spoke in session 1 (twice) and session 2 — should count as 2
        assert get_mp_sessions_attended(1, db_path) == 2

    def test_single_session_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_sessions_attended
        # member 2 only spoke in session 1
        assert get_mp_sessions_attended(2, db_path) == 1

    def test_returns_zero_for_unknown_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_sessions_attended
        assert get_mp_sessions_attended(999, db_path) == 0


class TestGetMpAvgSpeechLength:
    def test_rounds_to_two_decimals(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_avg_speech_length
        result = get_mp_avg_speech_length(1, db_path)
        # (10 + 11 + 11) / 3 = 10.666... → 10.67
        assert result == round((10 + 11 + 11) / 3, 2)

    def test_returns_float(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_avg_speech_length
        assert isinstance(get_mp_avg_speech_length(1, db_path), float)

    def test_returns_zero_for_unknown_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_avg_speech_length
        assert get_mp_avg_speech_length(999, db_path) == 0.0


class TestGetMpActiveSections:
    def test_returns_list_of_dicts(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_active_sections
        result = get_mp_active_sections(1, db_path)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_has_correct_keys(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_active_sections
        result = get_mp_active_sections(1, db_path)
        assert all("section" in r and "count" in r for r in result)

    def test_ordered_by_count_descending(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_active_sections
        result = get_mp_active_sections(1, db_path)
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)


class TestGetMostActiveMps:
    def test_returns_correct_limit(self, db_path):
        from analyzer.analytics.mp_stats import get_most_active_mps
        result = get_most_active_mps(limit=1, db_path=db_path)
        assert len(result) == 1

    def test_ordered_by_speech_count_descending(self, db_path):
        from analyzer.analytics.mp_stats import get_most_active_mps
        result = get_most_active_mps(db_path=db_path)
        counts = [r["speech_count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_returns_list_of_dicts(self, db_path):
        from analyzer.analytics.mp_stats import get_most_active_mps
        result = get_most_active_mps(db_path=db_path)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_top_mp_is_correct(self, db_path):
        from analyzer.analytics.mp_stats import get_most_active_mps
        result = get_most_active_mps(db_path=db_path)
        assert result[0]["speech_count"] == 3


class TestGetMpFullProfile:
    def test_returns_dict(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_full_profile
        result = get_mp_full_profile(1, db_path)
        assert isinstance(result, dict)

    def test_contains_expected_keys(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_full_profile
        result = get_mp_full_profile(1, db_path)
        expected_keys = [
            "name", "constituency", "party",
            "speech_count", "word_count", "avg_speech_length",
            "sessions_attended", "active_sections",
            "activity_over_time", "recent_speeches",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_returns_empty_dict_for_unknown_mp(self, db_path):
        from analyzer.analytics.mp_stats import get_mp_full_profile
        assert get_mp_full_profile(999, db_path) == {}


# sentiment tests─

class TestScoreSpeech:
    def test_returns_float(self):
        from analyzer.analytics.sentiment import score_speech
        assert isinstance(score_speech("This is a good day."), float)

    def test_score_between_minus_one_and_one(self):
        from analyzer.analytics.sentiment import score_speech
        score = score_speech("The situation is very bad and terrible.")
        assert -1.0 <= score <= 1.0

    def test_positive_speech_returns_positive_score(self):
        from analyzer.analytics.sentiment import score_speech
        score = score_speech(
            "This is an excellent, wonderful, and very positive development for all Kenyans."
        )
        assert score > 0

    def test_negative_speech_returns_negative_score(self):
        from analyzer.analytics.sentiment import score_speech
        score = score_speech(
            "This is terrible, awful, disastrous and completely unacceptable."
        )
        assert score < 0

    def test_empty_string_returns_zero(self):
        from analyzer.analytics.sentiment import score_speech
        assert score_speech("") == 0.0

    def test_whitespace_only_returns_zero(self):
        from analyzer.analytics.sentiment import score_speech
        assert score_speech("   ") == 0.0


class TestScoreLabel:
    def test_constructive_for_high_score(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(0.5) == "Constructive"

    def test_constructive_at_threshold(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(0.05) == "Constructive"

    def test_heated_for_low_score(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(-0.5) == "Heated"

    def test_heated_at_threshold(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(-0.05) == "Heated"

    def test_neutral_for_middle_score(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(0.0) == "Neutral"

    def test_neutral_just_below_constructive(self):
        from analyzer.analytics.sentiment import score_label
        assert score_label(0.04) == "Neutral"


class TestGetMpSentimentProfile:
    def test_returns_dict_with_correct_keys(self, db_path):
        from analyzer.analytics.sentiment import get_mp_sentiment_profile
        result = get_mp_sentiment_profile(1, db_path)
        assert "average_score" in result
        assert "label" in result
        assert "speech_scores" in result

    def test_average_score_is_float(self, db_path):
        from analyzer.analytics.sentiment import get_mp_sentiment_profile
        result = get_mp_sentiment_profile(1, db_path)
        assert isinstance(result["average_score"], float)

    def test_label_is_valid_string(self, db_path):
        from analyzer.analytics.sentiment import get_mp_sentiment_profile
        result = get_mp_sentiment_profile(1, db_path)
        assert result["label"] in ("Constructive", "Neutral", "Heated")

    def test_returns_defaults_for_unknown_mp(self, db_path):
        from analyzer.analytics.sentiment import get_mp_sentiment_profile
        result = get_mp_sentiment_profile(999, db_path)
        assert result["average_score"] == 0.0
        assert result["speech_scores"] == []


class TestUpdateSpeechSentiments:
    def test_updates_null_sentiments(self, tmp_path):
        from analyzer.analytics.sentiment import update_speech_sentiments

        # Create a database with one speech that has NULL sentiment_score
        path = tmp_path / "sentiment_test.db"
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, chamber TEXT NOT NULL,
                pdf_path TEXT, parsed_at TEXT
            );
            CREATE TABLE members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE speeches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER, member_id INTEGER,
                section TEXT, content TEXT NOT NULL,
                word_count INTEGER, sentiment_score REAL, created_at TEXT
            );
            INSERT INTO sessions (date, chamber, pdf_path, parsed_at)
                VALUES ('2026-01-01', 'National Assembly', 'x.pdf', '2026-01-01');
            INSERT INTO members (name) VALUES ('Test MP');
            INSERT INTO speeches (session_id, member_id, section, content, word_count, sentiment_score, created_at)
                VALUES (1, 1, 'BILLS', 'This is a great bill for Kenya.', 8, NULL, '2026-01-01');
        """)
        conn.commit()
        conn.close()

        count = update_speech_sentiments(db_path=path)
        assert count == 1

        # Verify the score was written
        conn = sqlite3.connect(path)
        row = conn.execute("SELECT sentiment_score FROM speeches WHERE id = 1").fetchone()
        conn.close()
        assert row[0] is not None
        assert isinstance(row[0], float)

    def test_skips_already_scored_speeches(self, db_path):
        from analyzer.analytics.sentiment import update_speech_sentiments
        # All speeches in the fixture already have sentiment_score set
        count = update_speech_sentiments(db_path=db_path)
        assert count == 0


# topics tests

class TestClassifyAgendaTitle:
    def test_returns_list(self):
        from analyzer.analytics.topics import classify_agenda_title
        result = classify_agenda_title("Health and social services bill")
        assert isinstance(result, list)

    def test_known_keyword_matches_correct_topic(self):
        from analyzer.analytics.topics import classify_agenda_title
        result = classify_agenda_title("A bill about hospitals and nurses")
        topics = [r["topic"] for r in result]
        assert "healthcare" in topics

    def test_no_keywords_returns_empty_list(self):
        from analyzer.analytics.topics import classify_agenda_title
        result = classify_agenda_title("Xyz qrs tuv wxy zab cde.")
        assert result == []

    def test_multiple_topics_detected(self):
        from analyzer.analytics.topics import classify_agenda_title
        result = classify_agenda_title(
            "Education and road infrastructure need urgent attention."
        )
        topics = [r["topic"] for r in result]
        assert len(topics) >= 2

    def test_empty_content_returns_empty_list(self):
        from analyzer.analytics.topics import classify_agenda_title
        assert classify_agenda_title("") == []

    def test_result_has_correct_keys(self):
        from analyzer.analytics.topics import classify_agenda_title
        result = classify_agenda_title("A bill to improve hospital care.")
        if result:
            assert "topic" in result[0]
            assert "confidence" in result[0]


class TestGetMpTopics:
    def test_returns_list_of_dicts(self, db_path):
        from analyzer.analytics.topics import get_mp_topics
        result = get_mp_topics(1, db_path)
        assert isinstance(result, list)

    def test_has_correct_keys(self, db_path):
        from analyzer.analytics.topics import get_mp_topics
        result = get_mp_topics(1, db_path)
        if result:
            assert "topic" in result[0]
            assert "count" in result[0]


# trends tests

class TestGetTopicTrend:
    def test_returns_list_of_dicts(self, db_path):
        from analyzer.analytics.trends import get_topic_trend
        result = get_topic_trend("healthcare", db_path=db_path)
        assert isinstance(result, list)

    def test_dicts_have_correct_keys(self, db_path):
        from analyzer.analytics.trends import get_topic_trend
        result = get_topic_trend("healthcare", db_path=db_path)
        if result:
            assert "period" in result[0]
            assert "count" in result[0]

    def test_ordered_ascending(self, db_path):
        from analyzer.analytics.trends import get_topic_trend
        result = get_topic_trend("healthcare", db_path=db_path)
        periods = [r["period"] for r in result]
        assert periods == sorted(periods)

    def test_weekly_period_format(self, db_path):
        from analyzer.analytics.trends import get_topic_trend
        result = get_topic_trend("healthcare", period="weekly", db_path=db_path)
        if result:
            # Weekly format should be YYYY-Www
            assert "W" in result[0]["period"]


class TestGetHouseActivityTrend:
    def test_returns_list(self, db_path):
        from analyzer.analytics.trends import get_house_activity_trend
        result = get_house_activity_trend(db_path=db_path)
        assert isinstance(result, list)

    def test_ordered_by_month_ascending(self, db_path):
        from analyzer.analytics.trends import get_house_activity_trend
        result = get_house_activity_trend(db_path=db_path)
        months = [r["month"] for r in result]
        assert months == sorted(months)

    def test_has_correct_keys(self, db_path):
        from analyzer.analytics.trends import get_house_activity_trend
        result = get_house_activity_trend(db_path=db_path)
        if result:
            assert "month" in result[0]
            assert "speech_count" in result[0]
            assert "word_count" in result[0]


class TestGetTrendingTopics:
    def test_returns_list(self, db_path):
        from analyzer.analytics.trends import get_trending_topics
        result = get_trending_topics(days=365, db_path=db_path)
        assert isinstance(result, list)

    def test_has_correct_keys(self, db_path):
        from analyzer.analytics.trends import get_trending_topics
        result = get_trending_topics(days=365, db_path=db_path)
        if result:
            assert "topic" in result[0]
            assert "count" in result[0]

    def test_ordered_by_count_descending(self, db_path):
        from analyzer.analytics.trends import get_trending_topics
        result = get_trending_topics(days=365, db_path=db_path)
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)