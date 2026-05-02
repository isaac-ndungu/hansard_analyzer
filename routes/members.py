from flask import Blueprint, render_template, abort
from analyzer.database.seed import get_connection
from analyzer.database.queries import get_all_members_with_stats, get_mp_agenda_items
from analyzer.analytics.mp_stats import get_mp_full_profile
from analyzer.analytics.sentiment import get_mp_sentiment_profile, score_label
from analyzer.analytics.topics import get_mp_topics
from analyzer.analytics.trends import get_participation_trend
from config import DB_PATH

from flask import jsonify
from analyzer.ai.cache import get_cached_summary, save_summary
from analyzer.ai.summarizer import summarize_mp
from config import DB_PATH
from analyzer.analytics.mp_stats import get_mp_speech_count, get_mp_word_count

members_bp = Blueprint("members", __name__)


@members_bp.route("/")
def member_list():
    conn = get_connection()
    members = get_all_members_with_stats(conn)
    conn.close()
    return render_template("members.html", members=members)

@members_bp.route("/<int:member_id>")
def member_detail(member_id):
    profile = get_mp_full_profile(member_id)
    if not profile:
        abort(404)

    conn = get_connection()
    agenda_items = get_mp_agenda_items(conn, member_id)
    conn.close()

    sentiment = get_mp_sentiment_profile(member_id)
    topics = get_mp_topics(member_id)           # no longer takes conn
    activity = get_participation_trend(member_id)

    return render_template(
        "member.html",
        profile=profile,
        sentiment=sentiment,
        topics=topics[:8],
        agenda_items=agenda_items[:20],
        chart_labels=[r["month"] for r in activity],
        chart_data=[r["count"] for r in activity],
    )


@members_bp.route("/<int:member_id>")
def mp_scorecard(member_id):
    """Full MP scorecard page with participation metrics and sentiment."""
    profile = get_mp_full_profile(member_id, DB_PATH)

    if not profile:
        abort(404)

    sentiment = get_mp_sentiment_profile(member_id, DB_PATH)
    topics = get_mp_topics(member_id, DB_PATH)
    activity = get_participation_trend(member_id, DB_PATH)

    # Prepare Chart.js data
    chart_labels = [row["month"] for row in activity]
    chart_data = [row["count"] for row in activity]

    return render_template(
        "member.html",
        profile=profile,
        sentiment=sentiment,
        topics=topics[:8],
        chart_labels=chart_labels,
        chart_data=chart_data,
    )


@members_bp.route("/<int:member_id>/summary", methods=["POST"])
def mp_summary(member_id):
    """
    Generates or retrieves a cached AI summary for an MP.
    Returns JSON: {summary: str, cached: bool}
    """

    cached = get_cached_summary("mp", member_id, DB_PATH)
    if cached:
        return jsonify({"summary": cached["summary"], "cached": True})

    summary = summarize_mp(member_id, DB_PATH)
    if summary and summary != "Summary could not be generated.":
        save_summary("mp", member_id, summary, DB_PATH)

    return jsonify({"summary": summary, "cached": False})