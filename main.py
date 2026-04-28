import logging
import sys

import click
from rich.console import Console
from rich.panel import Panel

from analyzer.database.seed import init_db
from analyzer.database.queries import get_database_stats
from analyzer.database.seed import get_connection
from analyzer.pipeline.scraper import sync_hansards
from analyzer.pipeline import run_pipeline
from config import PDF_DIR

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@click.group()
def cli():
    """Kenya Hansard Analyzer — Civic intelligence for Kenya's Parliament."""
    pass


@cli.command("init-db")
def cmd_init_db():
    """Initialize the local SQLite database."""
    init_db()
    console.print(Panel("Database initialized successfully.", title="init-db"))


@cli.command("sync")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
def cmd_sync(from_date):
    """Download and parse new Hansard documents."""
    console.print(Panel("Starting Hansard sync...", title="sync"))

    downloaded = sync_hansards(from_date=from_date)

    if not downloaded:
        console.print("No new documents downloaded.")
        return

    console.print(f"Downloaded {len(downloaded)} PDF(s). Parsing now...")

    for pdf_path in downloaded:
        count = run_pipeline(pdf_path)
        console.print(f"  {pdf_path.name}  ->  {count} speeches stored")


@cli.command("stats")
def cmd_stats():
    """Show overall database statistics."""
    conn = get_connection()
    stats = get_database_stats(conn)
    conn.close()

    console.print(Panel(
        "\n".join(f"  {table:<20} {count:>6} rows" for table, count in stats.items()),
        title="Database Statistics",
    ))


if __name__ == "__main__":
    cli()