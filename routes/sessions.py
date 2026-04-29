from flask import Blueprint, render_template, abort
from analyzer.database.seed import get_connection
from analyzer.analytics.trends import get_all_sessions_list
from config import DB_PATH

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/")
def session_list():
    """Lists all sessions ordered by most recent first."""
    try:
        sessions = get_all_sessions_list(DB_PATH)
    except Exception:
        sessions = []

    return render_template("sessions.html", sessions=sessions)


@sessions_bp.route("/<int:session_id>")
def session_detail(session_id):
    """Full session detail — metadata, top speakers, and complete speech log."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Session metadata
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            abort(404)
        columns = [d[0] for d in cursor.description]
        session = dict(zip(columns, row))

        # All speeches in this session with member info
        cursor.execute(
            """
            SELECT
                sp.id,
                sp.content,
                sp.word_count,
                sp.section,
                sp.sentiment_score,
                m.id   AS member_id,
                m.name AS member_name,
                m.constituency,
                m.party
            FROM speeches sp
            JOIN members m ON sp.member_id = m.id
            WHERE sp.session_id = ?
            ORDER BY sp.id ASC
            """,
            (session_id,),
        )
        cols = [d[0] for d in cursor.description]
        speeches = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Top speakers — aggregate by member
        from collections import Counter
        speaker_counts = Counter(s["member_name"] for s in speeches)
        top_speakers = [
            {"name": name, "count": count}
            for name, count in speaker_counts.most_common(10)
        ]

        # Unique sections covered
        sections = sorted(set(s["section"] for s in speeches if s["section"]))

        # Summary stats
        total_words = sum(s["word_count"] or 0 for s in speeches)

        conn.close()

    except Exception as exc:
        abort(500)

    return render_template(
        "session.html",
        session=session,
        speeches=speeches,
        top_speakers=top_speakers,
        sections=sections,
        total_words=total_words,
        total_speakers=len(speaker_counts),
    )