from flask import Blueprint, render_template, abort, request
from analyzer.database.seed import get_connection
from analyzer.database.queries import get_all_bills, get_bill_with_readings
from analyzer.utils.pagination import paginate

bills_bp = Blueprint("bills", __name__)


@bills_bp.route("/")
def bills_list():
    page     = request.args.get("page", 1, type=int)
    per_page = 25

    conn = get_connection()
    all_bills = get_all_bills(conn)
    conn.close()

    p = paginate(all_bills, page, per_page)
    return render_template("bills.html", bills=p["items"], pagination=p)


@bills_bp.route("/<int:bill_id>")
def bill_detail(bill_id):
    conn = get_connection()
    bill = get_bill_with_readings(conn, bill_id)

    conn.close()

    if not bill:
        abort(404)
        
    return render_template("bill_detail.html", bill=bill)
