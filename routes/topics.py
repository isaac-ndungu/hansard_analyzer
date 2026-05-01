from flask import Blueprint, render_template, abort
from config import TOPIC_MAP, DB_PATH
from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    get_topic_agenda_item_counts,
    get_agenda_items_by_topic,
)
from analyzer.analytics.topics import get_topic_frequency, get_trending_topics
from analyzer.analytics.sentiment import get_topic_sentiment

topics_bp = Blueprint("topics", __name__)


@topics_bp.route("/")
def topics_overview():
    conn = get_connection()
    topic_data = get_topic_agenda_item_counts(conn)
    conn.close()
    return render_template("topics.html", topics=topic_data)


@topics_bp.route("/<topic_name>")
def topic_detail(topic_name):
    if topic_name not in TOPIC_MAP:
        abort(404)

    conn = get_connection()
    agenda_items = get_agenda_items_by_topic(conn, topic_name)
    bills = get_agenda_items_by_topic(conn, topic_name, item_type="BILL")
    motions = get_agenda_items_by_topic(conn, topic_name, item_type="MOTION")
    trend = get_topic_frequency(conn, topic_name)
    conn.close()

    sentiment = get_topic_sentiment(topic_name, DB_PATH)

    return render_template(
        "topic_detail.html",
        topic=topic_name,
        agenda_items=agenda_items,
        bills=bills,
        motions=motions,
        chart_labels=[r["month"] for r in trend],
        chart_data=[r["item_count"] for r in trend],
        sentiment=sentiment,
    )
