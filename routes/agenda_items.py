from flask import Blueprint, render_template, abort
from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    get_agenda_item_by_id,
    get_speeches_by_agenda_item,
    get_topics_for_agenda_item,
)
from analyzer.analytics.sentiment import score_label

agenda_items_bp = Blueprint("agenda_items", __name__)


@agenda_items_bp.route("/<int:agenda_item_id>")
def agenda_item_detail(agenda_item_id):
    conn = get_connection()
    item = get_agenda_item_by_id(conn, agenda_item_id)
    if not item:
        conn.close()
        abort(404)

    speeches = get_speeches_by_agenda_item(conn, agenda_item_id)
    topics = get_topics_for_agenda_item(conn, agenda_item_id)
    
    conn.close()

    scored = [s["sentiment_score"] for s in speeches if s["sentiment_score"] is not None]
    avg_sentiment = round(sum(scored) / len(scored), 3) if scored else 0.0
    sentiment_label = score_label(avg_sentiment)

    speakers = {}
    for speech in speeches:
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

    return render_template(
        "agenda_item.html",
        item=item,
        speeches=speeches,
        topics=topics,
        top_speakers=top_speakers,
        avg_sentiment=avg_sentiment,
        sentiment_label=sentiment_label,
        total_words=sum(s["word_count"] or 0 for s in speeches),
    )
