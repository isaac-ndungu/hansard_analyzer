from flask import Blueprint, render_template

from analyzer.analytics.trends import get_recent_sessions, get_trending_topics

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    recent_sessions = get_recent_sessions(limit=5)
    trending_topics = get_trending_topics(days=365, limit=5)

    return render_template(
        "index.html",
        recent_sessions=recent_sessions,
        trending_topics=trending_topics,
    )


@home_bp.route("/about")
def about():
    """About page with information about the Hansard Analyzer."""
    return render_template("about.html")