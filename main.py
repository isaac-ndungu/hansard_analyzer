import logging
import sys
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from analyzer.database.seed import init_db, get_connection
from analyzer.database.queries import get_database_stats
from analyzer.pipeline.scraper import sync_hansards, get_available_hansards
from analyzer.pipeline.parser import parse_document
from analyzer.pipeline.normalizer import normalize
from analyzer.pipeline.pipeline import run_pipeline
from config import PDF_DIR

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@click.group()
def cli():
    """Kenya Hansard Analyzer — parliamentary data pipeline and query tool."""
    pass

# Database

@cli.command("init-db")
def cmd_init_db():
    """Initialize the local SQLite database."""
    init_db()
    console.print(Panel("Database initialized successfully.", title="init-db"))


@cli.command("stats")
def cmd_stats():
    """Show overall database statistics."""
    conn = get_connection()
    stats = get_database_stats(conn)
    conn.close()

    table = Table(title="Database Statistics", show_header=True)
    table.add_column("Table", style="cyan")
    table.add_column("Rows", justify="right")

    for table_name, count in stats.items():
        table.add_row(table_name, str(count))

    console.print(table)

# Sync

@cli.command("sync")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True, default=False,
              help="List what would be downloaded without storing anything.")
def cmd_sync(from_date, dry_run):
    """
    Download and parse new Hansard documents.

    Use --dry-run to see what the scraper finds on the parliament website
    without downloading or storing anything.
    """
    if dry_run:
        from datetime import datetime
        start = from_date or f"{datetime.utcnow().year}-01-01"
        end = datetime.utcnow().strftime("%Y-%m-%d")
        console.print(Panel(f"Dry run — scanning {start} to {end}", title="sync --dry-run"))

        available = get_available_hansards(start, end)

        if not available:
            console.print("No Hansard documents found in the given date range.")
            return

        table = Table(title=f"Found {len(available)} document(s)", show_header=True)
        table.add_column("Date")
        table.add_column("Chamber")
        table.add_column("Vol")
        table.add_column("No")
        table.add_column("URL")

        for doc in available:
            table.add_row(
                doc.get("date", ""),
                doc.get("chamber", ""),
                str(doc.get("volume") or ""),
                str(doc.get("issue") or ""),
                doc.get("url", ""),
            )

        console.print(table)
        return

    console.print(Panel("Starting Hansard sync...", title="sync"))

    downloaded = sync_hansards(from_date=from_date)

    if not downloaded:
        console.print("No new documents downloaded.")
        return

    console.print(f"Downloaded {len(downloaded)} PDF(s). Parsing now...")

    for pdf_path in downloaded:
        count = run_pipeline(pdf_path)
        console.print(f"  {pdf_path.name}  ->  {count} speeches stored")


# Parse a local PDF

@cli.command("parse")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option("--store", is_flag=True, default=False,
              help="Store the result in the database after parsing.")
def cmd_parse(pdf_path, store):
    """
    Parse a local Hansard PDF and display what was extracted.

    Pass --store to also write the result to the database.

    Example:
      python main.py parse data/pdfs/national_assembly_2026-03-11.pdf
      python main.py parse data/pdfs/national_assembly_2026-03-11.pdf --store
    """
    console.print(Panel(f"Parsing: {pdf_path.name}", title="parse"))

    parsed = parse_document(pdf_path)

    if not parsed:
        console.print("[red]No data could be extracted from this file.[/red]")
        sys.exit(1)

    normalized = normalize(parsed)

    # Metadata summary
    meta_table = Table(title="Document Metadata", show_header=False)
    meta_table.add_column("Field", style="cyan")
    meta_table.add_column("Value")

    meta_table.add_row("Date", normalized.get("date") or "NOT FOUND")
    meta_table.add_row("Chamber", normalized.get("chamber") or "NOT FOUND")
    meta_table.add_row("Parliament", str(normalized.get("parliament_number") or "NOT FOUND"))
    meta_table.add_row("Volume", str(normalized.get("volume") or "NOT FOUND"))
    meta_table.add_row("Issue", str(normalized.get("issue") or "NOT FOUND"))
    meta_table.add_row("Session Time", normalized.get("session_time") or "NOT FOUND")
    meta_table.add_row("Speeches found", str(len(normalized.get("speeches", []))))

    console.print(meta_table)

    # Sections found
    sections = normalized.get("sections", [])
    if sections:
        console.print(f"\nSections detected: {', '.join(s['title'] for s in sections)}")

    # First 5 speeches preview
    speeches = normalized.get("speeches", [])
    if speeches:
        speech_table = Table(title="First 5 Speeches (preview)", show_header=True)
        speech_table.add_column("Name", style="cyan")
        speech_table.add_column("Constituency")
        speech_table.add_column("Party")
        speech_table.add_column("Section")
        speech_table.add_column("Words", justify="right")
        speech_table.add_column("Content preview")

        for speech in speeches[:5]:
            speech_table.add_row(
                speech.get("name", ""),
                speech.get("constituency", ""),
                speech.get("party", ""),
                speech.get("section", ""),
                str(speech.get("word_count", 0)),
                speech.get("content", "")[:60] + "...",
            )

        console.print(speech_table)

    if store:
        count = run_pipeline(pdf_path)
        console.print(
            Panel(f"{count} speeches stored to database.", title="stored")
        )


# MP List

@cli.command("mp-list")
def cmd_mp_list():
    """List all MPs currently in the database."""
    conn = get_connection()
    from analyzer.database.queries import get_all_members
    members = get_all_members(conn)
    conn.close()

    if not members:
        console.print("No members in the database yet. Run sync or parse first.")
        return

    table = Table(title=f"{len(members)} Members", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Constituency")
    table.add_column("Party")
    table.add_column("First Seen")
    table.add_column("Last Seen")

    for member in members:
        table.add_row(
            member["name"],
            member["constituency"] or "",
            member["party"] or "",
            member["first_seen"] or "",
            member["last_seen"] or "",
        )

    console.print(table)


@cli.command("update-sentiments")
def cmd_update_sentiments():
    """Score sentiment for all speeches that currently have NULL sentiment_score."""
    from analyzer.analytics.sentiment import update_speech_sentiments

    console.print(Panel("Running sentiment batch update...", title="update-sentiments"))
    count = update_speech_sentiments()
    console.print(f"Updated sentiment scores for {count} speech(es).")


if __name__ == "__main__":
    cli()