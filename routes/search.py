from flask import Blueprint, render_template, request
from analyzer.database.seed import get_connection
from analyzer.database.queries import search_speeches

search_bp = Blueprint("search", __name__)


@search_bp.route("/")
def search():
    """Keyword search across all speeches with optional date filtering."""
    query = request.args.get("q", "").strip()
    from_date = request.args.get("from_date", "").strip() or None
    to_date = request.args.get("to_date", "").strip() or None

    results = []
    total = 0

    if query:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            sql = """
                SELECT
                    sp.id,
                    sp.content,
                    sp.word_count,
                    sp.section,
                    se.id   AS session_id,
                    se.date,
                    m.id    AS member_id,
                    m.name  AS member_name,
                    m.constituency,
                    m.party
                FROM speeches sp
                JOIN sessions se ON sp.session_id = se.id
                JOIN members  m  ON sp.member_id  = m.id
                WHERE sp.content LIKE ?
            """
            params = [f"%{query}%"]

            if from_date:
                sql += " AND se.date >= ?"
                params.append(from_date)
            if to_date:
                sql += " AND se.date <= ?"
                params.append(to_date)

            sql += " ORDER BY se.date DESC"

            cursor.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            results = [dict(zip(cols, row)) for row in cursor.fetchall()]
            total = len(results)
            conn.close()

        except Exception:
            results = []

    return render_template(
        "search.html",
        query=query,
        results=results,
        total=total,
        from_date=from_date or "",
        to_date=to_date or "",
    )