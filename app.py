from flask import Flask

from routes.home import home_bp
from routes.members import members_bp
from routes.search import search_bp
from routes.sessions import sessions_bp
from routes.topics import topics_bp
from routes.agenda_items import agenda_items_bp
from routes.bills import bills_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    app.register_blueprint(home_bp)
    app.register_blueprint(members_bp,      url_prefix="/members")
    app.register_blueprint(search_bp,       url_prefix="/search")
    app.register_blueprint(sessions_bp,     url_prefix="/sessions")
    app.register_blueprint(topics_bp,       url_prefix="/topics")
    app.register_blueprint(agenda_items_bp, url_prefix="/agenda")
    app.register_blueprint(bills_bp,        url_prefix="/bills")

    @app.route("/health")
    def health():
        """Returns database statistics as JSON. Used for monitoring."""
        from flask import jsonify
        from analyzer.database.seed import get_connection
        from analyzer.database.queries import get_database_stats
        try:
            conn = get_connection()
            stats = get_database_stats(conn)
            conn.close()
            return jsonify({"status": "ok", "stats": stats})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.template_filter('format_date')
    def format_date_filter(date_str):
        if not date_str:
            return ""
        from datetime import datetime
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day = dt.day
            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = "th"
            else:
                suffix = ["st", "nd", "rd"][day % 10 - 1]
            return f"{dt.strftime('%A')}, {day}{suffix} {dt.strftime('%B %Y')}"
        except ValueError:
            return date_str

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
