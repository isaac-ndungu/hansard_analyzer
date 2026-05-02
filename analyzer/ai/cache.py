import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 14  # Regenerate summaries older than 7 days


def get_cached_summary(entity_type: str, entity_id: int, db_path: Path = DB_PATH):
    """
    Returns a cached summary dict if one exists and is not stale.
    Returns None if no cache entry exists or if it has expired.
    Dict keys: summary, generated_at
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT summary, generated_at FROM ai_summaries WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Check if cache is stale
        if is_cache_stale(row["generated_at"]):
            return None

        return {"summary": row["summary"], "generated_at": row["generated_at"]}

    except Exception as e:
        logger.error(f"Error retrieving cached summary: {e}")
        return None


def save_summary(
    entity_type: str, entity_id: int, summary: str, db_path: Path = DB_PATH
):
    """
    Saves or replaces a summary in the cache.
    Uses INSERT OR REPLACE to handle the UNIQUE constraint on (entity_type, entity_id).
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        generated_at = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO ai_summaries (entity_type, entity_id, summary, generated_at)
            VALUES (?, ?, ?, ?)
        """,
            (entity_type, entity_id, summary, generated_at),
        )

        conn.commit()

    except Exception as e:
        logger.error("Error saving summary: %s", e)
    finally:
        conn.close()


def is_cache_stale(generated_at: str) -> bool:
    """
    Returns True if the summary was generated more than CACHE_TTL_DAYS ago.
    generated_at is an ISO format datetime string.
    """
    try:
        generated_dt = datetime.fromisoformat(generated_at)
        now = datetime.now()
        delta = now - generated_dt
        return delta.days >= CACHE_TTL_DAYS

    except Exception as e:
        logger.error(f"Error checking cache staleness: {e}")
        return True  # Consider stale if we can't parse the date
