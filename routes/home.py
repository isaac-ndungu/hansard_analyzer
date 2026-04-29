from flask import Blueprint, render_template
from analyzer.database.seed import get_connection
from analyzer.analytics.trends import get_recent_sessions, get_trending_topics

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    """Search-first homepage — recent sessions and trending topics only."""
    try:
        conn = get_connection()
        recent_sessions = get_recent_sessions(limit=5)
        trending_topics = get_trending_topics(days=90)
        conn.close()
    except Exception:
        recent_sessions = []
        trending_topics = []

    return render_template(
        "index.html",
        recent_sessions=recent_sessions,
        trending_topics=trending_topics,
    )