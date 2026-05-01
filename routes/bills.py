from flask import Blueprint, render_template, abort
from analyzer.database.seed import get_connection
from analyzer.database.queries import get_all_bills, get_bill_with_readings

bills_bp = Blueprint("bills", __name__)


@bills_bp.route("/")
def bills_list():
    conn = get_connection()
    bills = get_all_bills(conn)

    conn.close()

    return render_template("bills.html", bills=bills)


@bills_bp.route("/<int:bill_id>")
def bill_detail(bill_id):
    conn = get_connection()
    bill = get_bill_with_readings(conn, bill_id)

    conn.close()

    if not bill:
        abort(404)
        
    return render_template("bill_detail.html", bill=bill)
