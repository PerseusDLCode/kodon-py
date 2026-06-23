"""
Ingestion pipeline for TEI XML documents.

Chunks a TEI XML file into per-passage XML fragments (one file per
citable unit at the most granular CTS level declared in its <refsDecl>),
plus a metadata.json sidecar containing document-level publication
metadata and a nested table of contents.

Each chunk file is a small <chunk> wrapper carrying base_urn/cts_urn/
prev_urn/next_urn/unit attributes around an <elements> element holding
the actual TEI content for that passage. Downstream consumers (e.g. the
server) load a single chunk's <elements> and feed it to TEIParser.

Resumability:
- Chunking skips works that already have a metadata.json in their output
  directory.
"""

import json
import logging
import re
from pathlib import Path
from typing import Iterator

from lxml import etree

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("./tei_chunks")

NAMESPACES = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_NS = "{http://www.w3.org/XML/1998/namespace}"
WORK_TYPES = frozenset({"commentary", "edition", "translation"})
DIV_PATTERN_RE = re.compile(r"tei:div\[@n='\$\d+'\]")


class TEIParserError(Exception):
    pass


def discover_tei_files(source_dir: Path) -> Iterator[Path]:
    """
    Find all TEI XML files in the source directory.

    Args:
        source_dir: Root directory containing TEI XML files.

    Yields:
        Path objects for each .xml file found.
    """
    yield from source_dir.rglob("*.xml")


def get_chunk_dir(tei_path: Path, source_dir: Path, output_dir: Path) -> Path:
    """
    Compute the chunk output directory that mirrors the source directory
    structure.

    Args:
        tei_path: Path to the TEI XML file.
        source_dir: Root source directory.
        output_dir: Root output directory for chunked works.

    Returns:
        Directory where the chunk files and metadata.json should be stored.
    """
    relative = tei_path.relative_to(source_dir)
    return output_dir / relative.with_suffix("")


def is_int(s: str) -> bool:
    try:
        int(s)
    except (TypeError, ValueError):
        return False
    return True


def stringify_text(el) -> str | None:
    if el is None:
        return None

    text = etree.tostring(el, encoding="unicode", method="text", xml_declaration=False)
    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def find_work_div(tei_root):
    """Find the work-level <div> (type in WORK_TYPES) directly under <body>."""
    for div in tei_root.findall(".//tei:body/tei:div", namespaces=NAMESPACES):
        if div.get("type") in WORK_TYPES:
            return div

    raise TEIParserError(f"No work-level div found (type in {sorted(WORK_TYPES)})")


def get_chunk_unit(tei_root) -> str | None:
    """
    Determine the most granular CTS citable unit that is expressed as a
    chain of <div> elements in the document's <refsDecl>, e.g. "chapter".

    Returns None if no div-based cRefPattern is declared (e.g. a
    line-only citation scheme), in which case callers should fall back to
    chunking at the top level of textpart divs.
    """
    best_unit = None
    best_depth = 0

    for cref in tei_root.findall(
        ".//tei:refsDecl[@n='CTS']/tei:cRefPattern", namespaces=NAMESPACES
    ):
        replacement = cref.get("replacementPattern", "")
        depth = len(DIV_PATTERN_RE.findall(replacement))

        if depth > best_depth:
            best_depth = depth
            best_unit = cref.get("n")

    if best_unit is None:
        logger.warning(
            "No div-based CTS cRefPattern found; chunking at top-level textpart divs."
        )

    return best_unit


def build_toc_and_chunks(work_div, target_unit: str | None):
    """
    Walk the textpart <div> hierarchy under the work-level div.

    Returns (toc_nodes, chunk_nodes):
    - toc_nodes: flat list of dicts (depth, n, subtype, location) for every
      textpart div encountered, in document order.
    - chunk_nodes: list of (toc_node, div_element) pairs for the divs that
      should each become a chunk file: divs whose subtype matches
      target_unit, or top-level textpart divs when target_unit is None.
    """
    toc_nodes: list[dict] = []
    chunk_nodes: list[tuple[dict, object]] = []

    def walk(div, depth, location):
        child_index = 0

        for child in div.findall("tei:div", namespaces=NAMESPACES):
            if child.get("type") != "textpart":
                continue

            child_index += 1
            n = child.get("n") or str(child_index)
            child_location = location + [n]
            subtype = child.get("subtype", "")

            node = {
                "depth": depth,
                "n": n,
                "subtype": subtype,
                "location": child_location,
            }
            toc_nodes.append(node)

            is_chunk_boundary = subtype == target_unit if target_unit else depth == 0

            if is_chunk_boundary:
                chunk_nodes.append((node, child))
            else:
                walk(child, depth + 1, child_location)

    walk(work_div, 0, [])

    return toc_nodes, chunk_nodes


def make_label(node: dict) -> str:
    n = node["n"]

    if is_int(n):
        return f"{node['subtype'].capitalize()} {n}".strip()

    return n


def nest_textparts(textparts: list[dict]) -> list[dict]:
    """Build a tree from a flat, depth-annotated, document-ordered list.

    Each item becomes a child of the nearest preceding item with a
    strictly smaller depth; items with no such ancestor are roots.
    """
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []

    for item in textparts:
        level = item["depth"]

        while stack and stack[-1][0] >= level:
            stack.pop()

        if stack:
            stack[-1][1].setdefault("subpassages", []).append(item)
        else:
            roots.append(item)

        stack.append((level, item))

    return roots


def create_table_of_contents(toc_nodes: list[dict]) -> list[dict]:
    entries = []

    for node in toc_nodes:
        entry = {
            "depth": node["depth"],
            "label": make_label(node),
            "subtype": node["subtype"],
            "urn": node["urn"],
        }

        if "path" in node:
            entry["path"] = node["path"]

        entries.append(entry)

    if all(e["depth"] == 0 for e in entries):
        return entries

    return nest_textparts(entries)


def get_document_metadata(tei_root) -> dict:
    title_el = tei_root.find(".//tei:titleStmt/tei:title", namespaces=NAMESPACES)
    author_el = tei_root.find(".//tei:titleStmt/tei:author", namespaces=NAMESPACES)
    editors = [
        text
        for e in tei_root.findall(".//tei:titleStmt/tei:editor", namespaces=NAMESPACES)
        if (text := stringify_text(e))
    ]
    pub_place_el = tei_root.find(
        ".//tei:publicationStmt/tei:pubPlace", namespaces=NAMESPACES
    )
    pub_date_el = tei_root.find(".//tei:publicationStmt/tei:date", namespaces=NAMESPACES)

    return {
        "title": stringify_text(title_el),
        "author": stringify_text(author_el),
        "editors": editors,
        "pub_place": stringify_text(pub_place_el),
        "pub_date": stringify_text(pub_date_el),
    }


def chunk_tei_file(tei_path: Path, chunk_dir: Path) -> dict:
    """
    Chunk a TEI XML file into per-passage fragments and write them, along
    with a metadata.json sidecar, into chunk_dir.

    Args:
        tei_path: Path to the TEI XML file.
        chunk_dir: Directory where chunk XML files and metadata.json should
            be written.

    Returns:
        The metadata dict (the same one written to metadata.json).
    """
    tree = etree.parse(str(tei_path))
    root = tree.getroot()

    work_div = find_work_div(root)
    base_urn = work_div.get("n")

    if not base_urn:
        raise TEIParserError(f"Work div is missing @n (CTS urn): {tei_path}")

    language = work_div.get(f"{XML_NS}lang")
    unit = get_chunk_unit(root)

    toc_nodes, chunk_nodes = build_toc_and_chunks(work_div, unit)

    for node in toc_nodes:
        node["urn"] = f"{base_urn}:{'.'.join(node['location'])}"

    chunk_dir.mkdir(parents=True, exist_ok=True)

    chunk_urns = [node["urn"] for node, _div in chunk_nodes]

    for i, (node, div) in enumerate(chunk_nodes):
        attrib = {"base_urn": base_urn, "cts_urn": node["urn"], "unit": unit or ""}

        if i > 0:
            attrib["prev_urn"] = chunk_urns[i - 1]
        if i < len(chunk_urns) - 1:
            attrib["next_urn"] = chunk_urns[i + 1]

        chunk_root = etree.Element("chunk", attrib=attrib)
        elements_el = etree.SubElement(chunk_root, "elements")

        for child in list(div):
            elements_el.append(child)

        filename = "_".join(node["location"]) + ".xml"
        node["path"] = filename

        etree.ElementTree(chunk_root).write(
            str(chunk_dir / filename), encoding="utf-8", xml_declaration=True
        )

    toc = create_table_of_contents(toc_nodes)
    document_metadata = get_document_metadata(root)
    document_metadata["language"] = language

    metadata = {
        "document": document_metadata,
        "urn": base_urn,
        "table_of_contents": toc,
    }

    with open(chunk_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


def ingest_tei_file(tei_path: Path, chunk_dir: Path) -> dict:
    """
    Chunk a TEI XML file and report progress.

    Args:
        tei_path: Path to the TEI XML file.
        chunk_dir: Directory where chunk files and metadata.json are written.

    Returns:
        The metadata dict written to chunk_dir/metadata.json.
    """
    logger.info(f"Chunking: {tei_path}")

    metadata = chunk_tei_file(tei_path, chunk_dir)

    logger.info(f"Wrote {len(metadata['table_of_contents'])} top-level entries to {chunk_dir}")

    return metadata
