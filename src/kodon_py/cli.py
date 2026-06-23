"""
CLI for kodon-py TEI ingestion pipeline.

Usage:
    kodon ingest parse ./tei-sources
"""

import logging
from pathlib import Path

import click

from kodon_py.ingestion import DEFAULT_OUTPUT_DIR, discover_tei_files, get_chunk_dir, ingest_tei_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Kodon TEI ingestion CLI."""
    pass


@cli.group()
def ingest():
    """TEI XML ingestion commands."""
    pass


@ingest.command("parse")
@click.argument("source_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory for chunked works (default: {DEFAULT_OUTPUT_DIR})",
)
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    show_default=True,
    help="Skip works that already have chunk output.",
)
def parse_command(source_dir: Path, output_dir: Path, skip_existing: bool):
    """Chunk TEI XML files into per-passage fragments with metadata.json."""
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    tei_files = [
        t for t in list(discover_tei_files(source_dir)) if "__cts__" not in t.name
    ]
    total = len(tei_files)

    if total == 0:
        click.echo("No TEI XML files found.")
        return

    click.echo(f"Found {total} TEI XML files in {source_dir}")

    parsed = 0
    skipped = 0
    errors = 0

    with click.progressbar(tei_files, label="Chunking") as files:
        for tei_path in files:
            chunk_dir = get_chunk_dir(tei_path, source_dir, output_dir)

            if skip_existing and (chunk_dir / "metadata.json").exists():
                skipped += 1
                continue

            try:
                ingest_tei_file(tei_path, chunk_dir)
                parsed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to chunk {tei_path}: {e}")

    click.echo(f"\nChunked: {parsed}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    cli()
