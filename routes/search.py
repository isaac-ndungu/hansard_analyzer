from flask import Blueprint, render_template, request, jsonify
from analyzer.database.seed import get_connection
from analyzer.database.queries import (
    search_agenda_items,
    search_mp_participation,
    search_members_by_name,
    search_sessions_by_date,
)

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


@search_bp.route("/quick")
def quick_search():
    """
    JSON endpoint for the navbar live-search omnibox.
    Returns grouped results: agenda items, MPs, sessions.
    Limited to a small number of results per category for fast rendering.
    """
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({"agenda": [], "mps": [], "sessions": []})

    conn = get_connection()

    # Agenda items — existing query, slice to top 4
    agenda_raw = search_agenda_items(conn, query, limit=4)

    # MPs — direct name search
    mps_raw = search_members_by_name(conn, query, limit=4)

    # Sessions — partial date search
    sessions_raw = search_sessions_by_date(conn, query, limit=3)

    conn.close()

    return jsonify({
        "agenda": [
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "date": item["date"],
            }
            for item in agenda_raw
        ],
        "mps": [
            {
                "id": mp["id"],
                "name": mp["name"],
                "constituency": mp["constituency"],
                "party": mp["party"],
            }
            for mp in mps_raw
        ],
        "sessions": [
            {
                "id": s["id"],
                "date": s["date"],
                "chamber": s["chamber"],
                "speech_count": s["speech_count"],
            }
            for s in sessions_raw
        ],
    })