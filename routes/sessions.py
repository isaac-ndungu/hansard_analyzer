from flask import Blueprint, render_template, abort

from analyzer.database.seed import get_connection
from analyzer.analytics.trends import get_all_sessions_list
from flask import jsonify
from analyzer.ai.cache import get_cached_summary, save_summary
from analyzer.ai.summarizer import summarize_session
from config import DB_PATH

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/")
def session_list():
    sessions = get_all_sessions_list()
    return render_template("sessions.html", sessions=sessions)


@sessions_bp.route("/<int:session_id>")
def session_detail(session_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        abort(404)

    columns = [d[0] for d in cursor.description]
    session = dict(zip(columns, row))

    cursor.execute(
        """
        SELECT
            sp.id,
            sp.content,
            sp.word_count,
            sp.section,
            sp.agenda_item,
            sp.sentiment_score,
            m.name AS member_name,
            m.constituency,
            m.party,
            m.id AS member_id
        FROM speeches sp
        JOIN members m ON sp.member_id = m.id
        WHERE sp.session_id = ?
        ORDER BY sp.id ASC
        """,
        (session_id,),
    )
    columns = [d[0] for d in cursor.description]
    speeches = [dict(zip(columns, r)) for r in cursor.fetchall()]

    cursor.execute(
        """
        SELECT m.id, m.name, m.constituency, m.party, COUNT(sp.id) AS speech_count
        FROM speeches sp
        JOIN members m ON sp.member_id = m.id
        WHERE sp.session_id = ?
        GROUP BY m.id
        ORDER BY speech_count DESC
        """,
        (session_id,),
    )
    columns = [d[0] for d in cursor.description]
    speakers = [dict(zip(columns, r)) for r in cursor.fetchall()]

    sections = sorted(set(s["section"] for s in speeches if s["section"]))
    agenda_items = sorted(set(
        s["agenda_item"] for s in speeches if s["agenda_item"]
    ))

    # Calculate totals
    total_speakers = len(speakers)
    total_words = sum(s["word_count"] for s in speeches if s["word_count"])
    top_speakers = speakers[:5]  # Top 5 speakers

    conn.close()

    return render_template(
        "session.html",
        session=session,
        speeches=speeches,
        top_speakers=top_speakers,
        total_speakers=total_speakers,
        total_words=total_words,
        sections=sections,
        agenda_items=agenda_items,
    )


@sessions_bp.route("/<int:session_id>/summary", methods=["POST"])
def session_summary(session_id):
    """
    Generates or retrieves a cached AI summary for a session.
    Called via fetch() from the session detail page.
    Returns JSON: {summary: str, cached: bool}
    """
    

    cached = get_cached_summary("session", session_id, DB_PATH)
    if cached:
        return jsonify({"summary": cached["summary"], "cached": True})

    summary = summarize_session(session_id, DB_PATH)
    if summary and summary != "Summary could not be generated.":
        save_summary("session", session_id, summary, DB_PATH)

    return jsonify({"summary": summary, "cached": False})