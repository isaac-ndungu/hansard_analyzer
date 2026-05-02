import sqlite3
import logging
from pathlib import Path

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from config import DB_PATH
from analyzer.database.seed import get_connection

nltk.download("vader_lexicon", quiet=True)

logger = logging.getLogger(__name__)

# Module-level analyzer instance — avoids re-initializing on every call
_analyzer = SentimentIntensityAnalyzer()


def score_speech(content: str) -> float:
    """
    Returns VADER compound sentiment score for a speech.
    Range: -1.0 (most negative) to 1.0 (most positive).
    """
    if not content or not content.strip():
        return 0.0
    return _analyzer.polarity_scores(content)["compound"]


def score_label(score: float) -> str:
    """
    Converts a numeric sentiment score to a human-readable label.
      >= 0.05  → Constructive
      <= -0.05 → Heated
      otherwise → Neutral
    """
    if score >= 0.05:
        return "Constructive"
    if score <= -0.05:
        return "Heated"
    return "Neutral"


def get_mp_sentiment_profile(member_id: int, db_path: Path = DB_PATH) -> dict:
    """
    Computes the average sentiment score across all speeches by this MP.
    Returns average_score, label, and the list of individual speech scores.
    Returns zeroed defaults if the MP has no speeches.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM speeches WHERE member_id = ?",
            (member_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return {"average_score": 0.0, "label": "Neutral", "speech_scores": []}

    scores = [score_speech(row[0]) for row in rows]
    average = round(sum(scores) / len(scores), 4)

    return {
        "average_score": average,
        "label": score_label(average),
        "speech_scores": scores,
    }


def get_topic_sentiment(topic: str, db_path: Path = DB_PATH) -> dict:
    """
    Computes average sentiment for all speeches tagged with the given topic.
    Returns topic, average_score, label, and sample_count.
    Returns zeroed defaults if no speeches are tagged with this topic.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sp.content
            FROM speeches sp
            JOIN agenda_items ai ON sp.agenda_item_id = ai.id
            JOIN agenda_item_topics ait ON ait.agenda_item_id = ai.id
            WHERE ait.topic = ?
            """,
            (topic,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "topic": topic,
            "average_score": 0.0,
            "label": "Neutral",
            "sample_count": 0,
        }

    scores = [score_speech(row[0]) for row in rows]
    average = round(sum(scores) / len(scores), 4)

    return {
        "topic": topic,
        "average_score": average,
        "label": score_label(average),
        "sample_count": len(scores),
    }


def update_speech_sentiments(db_path: Path = DB_PATH) -> int:
    """
    Batch updates sentiment_score for all speeches where it is currently NULL.
    Returns the count of speeches updated.
    This should be run after each pipeline ingestion.
    """
    conn = get_connection(db_path)
    updated = 0
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content FROM speeches WHERE sentiment_score IS NULL"
        )
        rows = cursor.fetchall()

        for speech_id, content in rows:
            score = score_speech(content)
            cursor.execute(
                "UPDATE speeches SET sentiment_score = ? WHERE id = ?",
                (score, speech_id),
            )
            updated += 1

        conn.commit()
        logger.info("Updated sentiment scores for %d speeches.", updated)
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to update sentiment scores: %s", exc)
        raise
    finally:
        conn.close()

    return updated