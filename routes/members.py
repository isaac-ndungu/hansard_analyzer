from flask import Blueprint, render_template, abort, request, jsonify
from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    get_all_members_with_stats,            # for the paginated list
    get_mp_agenda_items,
)
from analyzer.analytics.mp_stats import get_mp_full_profile, get_most_active_mps
from analyzer.analytics.sentiment import get_mp_sentiment_profile
from analyzer.analytics.topics import get_mp_topics
from analyzer.analytics.trends import get_participation_trend
from analyzer.ai.cache import get_cached_summary, save_summary
from analyzer.ai.summarizer import summarize_mp
from analyzer.utils.pagination import paginate
from config import DB_PATH

members_bp = Blueprint("members", __name__)


@members_bp.route("/")
def member_list():
    """Paginated list of all members with stats."""
    page = request.args.get("page", 1, type=int)
    per_page = 30

    conn = get_connection()
    members = get_all_members_with_stats(conn)
    conn.close()

    top_mp = get_most_active_mps(limit=1)[0] if members else None

    p = paginate(members, page, per_page)
    return render_template("members.html", members=p["items"], pagination=p, top_mp=top_mp)


@members_bp.route("/<int:member_id>")
def mp_scorecard(member_id):
    """Full MP profile page with stats, agenda items, and sentiment."""
    profile = get_mp_full_profile(member_id, DB_PATH)
    if not profile:
        abort(404)

    # Load agenda items for this MP
    conn = get_connection()
    agenda_items = get_mp_agenda_items(conn, member_id)
    conn.close()

    sentiment = get_mp_sentiment_profile(member_id, DB_PATH)
    topics = get_mp_topics(member_id, DB_PATH)
    activity = get_participation_trend(member_id, DB_PATH)

    chart_labels = [row["month"] for row in activity]
    chart_data = [row["count"] for row in activity]

    return render_template(
        "member.html",
        profile=profile,
        sentiment=sentiment,
        topics=topics[:8],
        agenda_items=agenda_items[:20],
        chart_labels=chart_labels,
        chart_data=chart_data,
    )


@members_bp.route("/<int:member_id>/summary", methods=["POST"])
def mp_summary(member_id):
    """AJAX endpoint for AI summary generation / cache retrieval."""
    cached = get_cached_summary("mp", member_id, DB_PATH)
    if cached:
        return jsonify({"summary": cached["summary"], "cached": True})

    summary = summarize_mp(member_id, DB_PATH)
    if summary and summary != "Summary could not be generated.":
        save_summary("mp", member_id, summary, DB_PATH)

    return jsonify({"summary": summary, "cached": False})