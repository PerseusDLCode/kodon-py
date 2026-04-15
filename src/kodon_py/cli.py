"""
CLI for kodon-py TEI ingestion pipeline.

Usage:
    kodon ingest parse ./tei-sources
    kodon ingest load
    kodon ingest all ./tei-sources
    kodon ingest status ./tei-sources
    kodon ingest pipeline ./tei-sources
"""

import logging
from pathlib import Path

import click

from kodon_py.ingestion import (
    DEFAULT_OUTPUT_DIR,
    discover_tei_files,
    get_json_path,
    parse_tei_to_json,
)

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
    help=f"Output directory for JSON files (default: {DEFAULT_OUTPUT_DIR})",
)
def parse_command(source_dir: Path, output_dir: Path):
    """Parse TEI XML files to JSON. Skips files that already have JSON output."""
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

    with click.progressbar(tei_files, label="Parsing") as files:
        for tei_path in files:
            json_path = get_json_path(tei_path, source_dir, output_dir)

            if json_path.exists():
                skipped += 1
                continue

            try:
                parse_tei_to_json(tei_path, json_path)
                parsed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to parse {tei_path}: {e}")

    click.echo(f"\nParsed: {parsed}, Skipped: {skipped}, Errors: {errors}")


@ingest.command("pipeline")
@click.argument("source_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
)
@click.option(
    "--with-morphology",
    is_flag=True,
    default=False,
    help="Run Stanza morphological analysis (adds lemma, pos, morphology to tokens).",
)
@click.option(
    "--commentary-source",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a JSON file mapping token URNs to commentary links.",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "tei"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Output format: 'json' (default) or 'tei' (annotated TEI XML with <w> tags).",
)
@click.option(
    "--stanza-model-dir",
    type=click.Path(),
    default="./stanza_models",
    show_default=True,
    help="Directory containing Stanza model files.",
)
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    show_default=True,
    help="Skip output files that already exist on disk.",
)
def pipeline_command(
    source_dir: Path,
    output_dir: Path,
    with_morphology: bool,
    commentary_source: Path | None,
    output_format: str,
    stanza_model_dir: str,
    skip_existing: bool,
):
    """
    Run the annotated pipeline on TEI XML files.

    Supports optional morphological analysis (--with-morphology), commentary
    linking (--commentary-source), and output as annotated TEI XML
    (--output-format tei).

    \b
    Examples:
      kodon ingest pipeline ./tei-sources
      kodon ingest pipeline ./tei-sources --with-morphology --output-format tei
      kodon ingest pipeline ./tei-sources --commentary-source ./notes.json
    """
    from kodon_py.pipeline import (
        CommentaryStage,
        JSONCommentarySource,
        JSONWriter,
        MorphologyStage,
        Pipeline,
        TEIXMLReader,
        TEIXMLWriter,
    )

    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    stages = []

    if with_morphology:
        stages.append(MorphologyStage(model_dir=stanza_model_dir))
        click.echo("Morphology stage enabled.")

    if commentary_source is not None:
        stages.append(CommentaryStage(source=JSONCommentarySource(commentary_source)))
        click.echo(f"Commentary stage enabled (source: {commentary_source}).")

    suffix = ".json" if output_format == "json" else ".xml"
    writer = JSONWriter() if output_format == "json" else TEIXMLWriter()

    pipeline = Pipeline(reader=TEIXMLReader(), stages=stages, writer=writer)

    tei_files = [t for t in discover_tei_files(source_dir) if "__cts__" not in t.name]
    total = len(tei_files)

    if total == 0:
        click.echo("No TEI XML files found.")
        return

    click.echo(f"Found {total} TEI XML files in {source_dir}")

    sources = [
        (
            tei_path,
            get_json_path(tei_path, source_dir, output_dir).with_suffix(suffix),
        )
        for tei_path in tei_files
    ]

    processed = 0
    skipped = 0
    errors = 0

    with click.progressbar(sources, label="Processing") as items:
        for src, dest in items:
            if skip_existing and dest.exists():
                skipped += 1
                continue
            try:
                pipeline.run(src, dest)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to process {src}: {e}")

    click.echo(f"\nProcessed: {processed}, Skipped: {skipped}, Errors: {errors}")


@ingest.command("render")
@click.argument("json_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory for XML files (default: {DEFAULT_OUTPUT_DIR})",
)
@click.option(
    "--suffix",
    default="annotated",
    show_default=True,
    help="Suffix inserted before the .xml extension in output filenames.",
)
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    show_default=True,
    help="Skip output files that already exist on disk.",
)
def render_command(json_dir: Path, output_dir: Path, suffix: str, skip_existing: bool):
    """
    Render previously parsed JSON files as annotated TEI XML.

    Reads each *.json file in JSON_DIR (excluding *.metadata.json sidecars)
    and writes a corresponding annotated TEI XML file produced by TEIXMLWriter.

    \b
    Example:
      kodon ingest render ./output/json --output-dir ./output/xml
    """
    import json

    from kodon_py.pipeline import TEIXMLWriter

    json_dir = json_dir.resolve()
    output_dir = output_dir.resolve()

    json_files = sorted(
        p for p in json_dir.rglob("*.json") if not p.name.endswith(".metadata.json")
    )
    total = len(json_files)

    if total == 0:
        click.echo("No JSON files found.")
        return

    click.echo(f"Found {total} JSON files in {json_dir}")

    writer = TEIXMLWriter()
    processed = 0
    skipped = 0
    errors = 0

    with click.progressbar(json_files, label="Rendering") as files:
        for json_path in files:
            rel = json_path.relative_to(json_dir)
            dest = output_dir / rel.with_name(f"{rel.stem}.{suffix}.xml")

            if skip_existing and dest.exists():
                skipped += 1
                continue

            try:
                with open(json_path, encoding="utf-8") as f:
                    document = json.load(f)
                writer.write(document, dest)
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to render {json_path}: {e}")

    click.echo(f"\nProcessed: {processed}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    cli()
