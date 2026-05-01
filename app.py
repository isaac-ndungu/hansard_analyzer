import click
from flask import Flask
from analyzer.database.seed import init_db, get_connection
from analyzer.analytics.sentiment import update_speech_sentiments
from analyzer.pipeline.scraper import sync_hansards
from analyzer.pipeline.pipeline import run_pipeline
from routes.home import home_bp
from routes.members import members_bp
from routes.sessions import sessions_bp
from routes.search import search_bp
from routes.topics import topics_bp
from routes.agenda_items import agenda_items_bp
from routes.bills import bills_bp


def create_app():
    app = Flask(__name__)

    #  Load config ─
    app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"

    from config import DB_PATH
    app.config["DB_PATH"] = str(DB_PATH)

    #  Register blueprints ─
    

    app.register_blueprint(home_bp)
    app.register_blueprint(members_bp,     url_prefix="/members")
    app.register_blueprint(search_bp,      url_prefix="/search")
    app.register_blueprint(sessions_bp,    url_prefix="/sessions")
    app.register_blueprint(topics_bp,      url_prefix="/topics")
    app.register_blueprint(agenda_items_bp, url_prefix="/agenda")
    app.register_blueprint(bills_bp,       url_prefix="/bills")

    #  Register Flask CLI commands ─
    app.cli.add_command(cmd_init_db)
    app.cli.add_command(cmd_sync)
    app.cli.add_command(cmd_update_sentiments)

    return app


#  Flask CLI Commands ─

@click.command("init-db")
def cmd_init_db():
    """Initialize the database and create all tables."""
    init_db()
    click.echo("Database initialized.")


@click.command("sync")
@click.option("--from-date", default=None, help="Sync from this date (YYYY-MM-DD)")
def cmd_sync(from_date):
    """Download and parse new Hansard PDFs."""
    paths = sync_hansards(from_date=from_date)
    if not paths:
        click.echo("No new documents found.")
        return
    for pdf_path in paths:
        count = run_pipeline(pdf_path)
        click.echo(f"  {pdf_path.name} -> {count} speeches stored")
    click.echo(f"Sync complete. {len(paths)} document(s) processed.")


@click.command("update-sentiments")
def cmd_update_sentiments():
    """Batch update sentiment scores for all unscored speeches."""
    count = update_speech_sentiments()
    click.echo(f"Updated sentiment for {count} speeches.")


#  Entry point 

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)