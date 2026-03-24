"""
Ingestion pipeline for TEI XML documents.

Parses TEI XML files to JSON

Progress is tracked by file existence.

Resumability:
- Parse phase skips files that already have JSON output
"""

import json
import logging
from pathlib import Path
from typing import Iterator

from kodon_py.tei_parser import TEIParser, create_table_of_contents

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("./tei_json")


def discover_tei_files(source_dir: Path) -> Iterator[Path]:
    """
    Find all TEI XML files in the source directory.

    Args:
        source_dir: Root directory containing TEI XML files.

    Yields:
        Path objects for each .xml file found.
    """
    yield from source_dir.rglob("*.xml")


def get_json_path(tei_path: Path, source_dir: Path, output_dir: Path) -> Path:
    """
    Compute the JSON output path that mirrors the source directory structure.

    Args:
        tei_path: Path to the TEI XML file.
        source_dir: Root source directory.
        output_dir: Root output directory for JSON files.

    Returns:
        Path where the JSON file should be stored.
    """
    relative = tei_path.relative_to(source_dir)
    return output_dir / relative.with_suffix(".json")


def parse_tei_to_json(tei_path: Path, output_path: Path) -> dict:
    """
    Parse a TEI XML file and save the result as JSON.

    Args:
        tei_path: Path to the TEI XML file.
        output_path: Path where JSON output should be written.

    Returns:
        The parsed data dictionary.
    """
    logger.info(f"Parsing: {tei_path}")

    parser = TEIParser(tei_path)

    parsed_data = {
        "source_file": str(tei_path),
        "author": parser.author,
        "editionStmt": parser.editionStmt,
        "language": parser.language,
        "publicationStmt": parser.publicationStmt,
        "respStmt": parser.respStmt,
        "sourceDesc": parser.sourceDesc,
        "title": parser.title,
        "urn": parser.urn,
        "textpart_labels": parser.textpart_labels,
        "textparts": parser.textparts,
        "elements": parser.elements,
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved JSON: {output_path}")

    metadata_path = str(output_path).replace(
        output_path.stem, f"{output_path.stem}.metadata"
    )

    toc = create_table_of_contents(parser.textparts, parser.textpart_labels)

    metadata = {
        "author": parser.author,
        "language": parser.language,
        "table_of_contents": toc,
        "title": parser.title,
        "urn": parser.urn,
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved metadata: {metadata_path}")

    return parsed_data
