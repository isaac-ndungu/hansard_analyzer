from flask import Blueprint, render_template, abort
from collections import defaultdict
from analyzer.database.seed import get_connection
from analyzer.analytics.trends import get_all_sessions_list
from flask import jsonify
from analyzer.ai.cache import get_cached_summary, save_summary
from analyzer.ai.summarizer import summarize_session
from config import DB_PATH
from analyzer.database.queries import get_agenda_items_by_session


sessions_bp = Blueprint("sessions", __name__)


sessions_bp = Blueprint("sessions", __name__)

@sessions_bp.route("/")
def session_list():
    sessions = get_all_sessions_list()
    return render_template("session_list.html", sessions=sessions)

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

    agenda_items = get_agenda_items_by_session(conn, session_id)

    cursor.execute(
        "SELECT COUNT(DISTINCT member_id) FROM speeches WHERE session_id = ?",
        (session_id,),
    )
    total_speakers = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COALESCE(SUM(word_count), 0) FROM speeches WHERE session_id = ?",
        (session_id,),
    )
    total_words = cursor.fetchone()[0]
    
    conn.close()

    items_by_type = defaultdict(list)
    for item in agenda_items:
        items_by_type[item["type"]].append(item)

    type_order = ["BILL", "MOTION", "PETITION", "STATEMENT", "QUESTION", "PAPER", "OTHER"]
    ordered_items_by_type = {
        t: items_by_type[t] for t in type_order if t in items_by_type
    }

    return render_template(
        "session.html",
        session=session,
        agenda_items=agenda_items,
        items_by_type=ordered_items_by_type,
        total_speakers=total_speakers,
        total_words=total_words,
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