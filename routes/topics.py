from flask import Blueprint, render_template, abort
from analyzer.database.seed import get_connection
from analyzer.database.queries import get_speeches_by_topic
from analyzer.analytics.topics import get_trending_topics
from analyzer.analytics.trends import get_topic_trend
from analyzer.analytics.sentiment import get_topic_sentiment
from config import DB_PATH, TOPIC_MAP

topics_bp = Blueprint("topics", __name__)


@topics_bp.route("/")
def topics_overview():
    """Overview of all topics with mention counts."""
    try:
        conn = get_connection()
        # Get mention counts for every topic in TOPIC_MAP
        cursor = conn.cursor()
        topic_data = []
        for topic in TOPIC_MAP.keys():
            cursor.execute(
                "SELECT COUNT(*) FROM speech_topics WHERE topic = ?",
                (topic,),
            )
            count = cursor.fetchone()[0]
            topic_data.append({"topic": topic, "count": count})

        # Sort by count descending
        topic_data.sort(key=lambda x: x["count"], reverse=True)
        conn.close()

    except Exception:
        topic_data = []

    return render_template("topics.html", topics=topic_data)


@topics_bp.route("/<topic_name>")
def topic_detail(topic_name):
    """Detail page for a single topic — trend chart and recent speeches."""
    if topic_name not in TOPIC_MAP:
        abort(404)

    try:
        conn = get_connection()

        # Recent speeches tagged with this topic
        speeches = get_speeches_by_topic(conn, topic_name)[:20]

        # Sentiment profile
        sentiment = get_topic_sentiment(topic_name, DB_PATH)

        # Trend data for Chart.js
        trend = get_topic_trend(topic_name, db_path=DB_PATH)
        chart_labels = [row["period"] for row in trend]
        chart_data = [row["count"] for row in trend]

        # Top MPs who discuss this topic
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT m.id, m.name, m.constituency, m.party, COUNT(*) AS count
            FROM speech_topics st
            JOIN speeches sp ON st.speech_id = sp.id
            JOIN members m ON sp.member_id = m.id
            WHERE st.topic = ?
            GROUP BY m.id
            ORDER BY count DESC
            LIMIT 5
            """,
            (topic_name,),
        )
        cols = [d[0] for d in cursor.description]
        top_mps = [dict(zip(cols, row)) for row in cursor.fetchall()]

        total_mentions = sum(chart_data) if chart_data else len(speeches)

        conn.close()

    except Exception:
        speeches = []
        sentiment = {"average_score": 0.0, "label": "Neutral", "sample_count": 0}
        chart_labels = []
        chart_data = []
        top_mps = []
        total_mentions = 0

    return render_template(
        "topic_detail.html",
        topic=topic_name,
        speeches=speeches,
        sentiment=sentiment,
        chart_labels=chart_labels,
        chart_data=chart_data,
        top_mps=top_mps,
        total_mentions=total_mentions,
    )