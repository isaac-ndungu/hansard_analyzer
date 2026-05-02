from flask import Blueprint, render_template, abort, request
from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    get_agenda_item_by_id,
    get_speeches_by_agenda_item,
    get_topics_for_agenda_item,
)
from analyzer.analytics.sentiment import score_label
from analyzer.utils.pagination import paginate

agenda_items_bp = Blueprint("agenda_items", __name__)


@agenda_items_bp.route("/<int:agenda_item_id>")
def agenda_item_detail(agenda_item_id):
    page     = request.args.get("page", 1, type=int)
    per_page = 20

    conn = get_connection()
    item = get_agenda_item_by_id(conn, agenda_item_id)
    if not item:
        conn.close()
        abort(404)

    all_speeches = get_speeches_by_agenda_item(conn, agenda_item_id)
    topics = get_topics_for_agenda_item(conn, agenda_item_id)
    conn.close()

    scored = [s["sentiment_score"] for s in all_speeches if s["sentiment_score"] is not None]
    avg_sentiment = round(sum(scored) / len(scored), 3) if scored else 0.0
    sentiment_label = score_label(avg_sentiment)
    total_words = sum(s["word_count"] or 0 for s in all_speeches)

    speakers = {}
    for speech in all_speeches:
        mid = speech["member_id"]
        if mid not in speakers:
            speakers[mid] = {
                "member_id": mid,
                "name": speech["member_name"],
                "constituency": speech["constituency"],
                "party": speech["party"],
                "count": 0,
            }
        speakers[mid]["count"] += 1

    top_speakers = sorted(speakers.values(), key=lambda x: x["count"], reverse=True)
    p = paginate(all_speeches, page, per_page)

    return render_template(
        "agenda_item.html",
        item=item,
        speeches=p["items"],
        pagination=p,
        topics=topics,
        top_speakers=top_speakers,
        avg_sentiment=avg_sentiment,
        sentiment_label=sentiment_label,
        total_words=total_words,
        total_speeches=len(all_speeches),
    )

@agenda_items_bp.route("/<int:agenda_item_id>/summary", methods=["POST"])
def agenda_item_summary(agenda_item_id):
    """
    Generates or retrieves a cached AI summary for an agenda item.
    Returns JSON: {summary: str, cached: bool}
    """
    from flask import jsonify
    from analyzer.ai.cache import get_cached_summary, save_summary
    from analyzer.ai.summarizer import summarize_agenda_item
    from config import DB_PATH

    cached = get_cached_summary("agenda_item", agenda_item_id, DB_PATH)
    if cached:
        return jsonify({"summary": cached["summary"], "cached": True})

    summary = summarize_agenda_item(agenda_item_id, DB_PATH)

    fallback_responses = {
        "Summary could not be generated.",
        "Summary could not be generated — API key not configured.",
        "No speeches found for this agenda item.",
    }
    if summary and summary not in fallback_responses:
        save_summary("agenda_item", agenda_item_id, summary, DB_PATH)

    return jsonify({"summary": summary, "cached": False})