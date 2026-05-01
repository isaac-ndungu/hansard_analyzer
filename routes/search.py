from flask import Blueprint, render_template, request
from analyzer.database.seed import get_connection
from analyzer.database.queries import search_agenda_items, search_mp_participation

search_bp = Blueprint("search", __name__)

@search_bp.route("/")
def search():
    query     = request.args.get("q", "").strip()
    item_type = request.args.get("type", "").strip() or None
    from_date = request.args.get("from_date", "").strip() or None
    to_date   = request.args.get("to_date", "").strip() or None

    agenda_results = []
    mp_results = []

    if query:
        conn = get_connection()
        agenda_results = search_agenda_items(conn, query, from_date, to_date, item_type)
        mp_results = search_mp_participation(conn, query)
        conn.close()

    return render_template(
        "search.html",
        query=query,
        agenda_results=agenda_results,
        mp_results=mp_results,
        item_type=item_type or "",
        from_date=from_date or "",
        to_date=to_date or "",
    )