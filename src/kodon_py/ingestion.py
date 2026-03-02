"""
Two-phase ingestion pipeline for TEI XML documents.

Phase 1: Parse TEI XML files to JSON

Progress is tracked by file existence:
- Phase 1 complete: JSON file exists for the TEI source

Resumability:
- Parse phase skips files that already have JSON output
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

from kodon_py.tei_parser import TEIParser

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

    return parsed_data


def json_to_parser_like(parsed_data: dict) -> SimpleNamespace:
    """
    Wrap parsed JSON data in an object that mimics TEIParser's interface.

    This allows reusing save_to_db which expects a TEIParser-like object.

    Args:
        parsed_data: Dict loaded from a parsed JSON file.

    Returns:
        SimpleNamespace with TEIParser-compatible attributes.
    """
    return SimpleNamespace(
        author=parsed_data.get("author"),
        editionStmt=parsed_data.get("editionStmt"),
        language=parsed_data.get("language"),
        publicationStmt=parsed_data.get("publicationStmt"),
        respStmt=parsed_data.get("respStmt"),
        sourceDesc=parsed_data.get("sourceDesc"),
        title=parsed_data.get("title"),
        urn=parsed_data.get("urn"),
        textpart_labels=parsed_data.get("textpart_labels", []),
        textparts=parsed_data.get("textparts", []),
        elements=parsed_data.get("elements", []),
    )
