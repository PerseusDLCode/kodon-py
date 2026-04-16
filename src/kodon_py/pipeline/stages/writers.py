"""
DocumentWriter implementations for the kodon-py pipeline.

``JSONWriter``
    Mirrors the output of ``ingestion.py::parse_tei_to_json``, including
    the ``.metadata.json`` sidecar file.

``TEIXMLWriter``
    Builds a new XML file by walking the document JSON depth-first and
    emitting lxml elements, copying the ``<teiHeader>`` from the source
    file verbatim.  Every token in a ``text_run`` becomes a ``<w>``
    element carrying its URN and morphological attributes.
"""

import copy
import json
import logging
from pathlib import Path

from lxml import etree

from kodon_py.tei_parser import create_table_of_contents

logger = logging.getLogger(__name__)

TEI_NS = "http://www.tei-c.org/ns/1.0"
TEI = f"{{{TEI_NS}}}"

# Keys in an element dict that are internal bookkeeping, not XML attributes.
_ELEMENT_SKIP_KEYS = frozenset(
    {"children", "index", "tagname", "textpart_index", "textpart_urn", "urn", "tokens"}
)


# ---------------------------------------------------------------------------
# JSONWriter
# ---------------------------------------------------------------------------


class JSONWriter:
    """
    Writes a DocumentDict as JSON, plus a ``.metadata.json`` sidecar.

    Parameters
    ----------
    write_metadata:
        When ``True`` (the default), also write the metadata sidecar that
        ``server.py`` uses for table-of-contents loading.
    """

    def __init__(self, *, write_metadata: bool = True) -> None:
        self.write_metadata = write_metadata

    def write(self, document: dict, destination: Path | str) -> None:
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved JSON: {dest}")

        if self.write_metadata:
            self._write_metadata(document, dest)

    def _write_metadata(self, document: dict, dest: Path) -> None:
        toc = create_table_of_contents(
            document["textparts"], document["textpart_labels"]
        )
        metadata = {
            "author": document.get("author"),
            "language": document.get("language"),
            "table_of_contents": toc,
            "title": document.get("title"),
            "urn": document.get("urn"),
        }
        metadata_path = dest.with_stem(f"{dest.stem}.metadata")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved metadata: {metadata_path}")


# ---------------------------------------------------------------------------
# TEIXMLWriter
# ---------------------------------------------------------------------------


class TEIXMLWriter:
    """
    Produces annotated TEI XML by walking the document JSON depth-first.

    The ``<teiHeader>`` is copied verbatim from the source file.  The body
    is reconstructed entirely from the JSON: each element dict becomes an
    lxml element, and each token in a ``text_run`` becomes a ``<w>`` element
    carrying its URN and morphological attributes as XML attributes.
    """

    def write(self, document: dict, destination: Path | str) -> None:
        source_path = document.get("source_file")
        if not source_path:
            raise ValueError("DocumentDict must contain 'source_file' for TEIXMLWriter")

        # Copy the header from the source file verbatim.
        source_tree = etree.parse(source_path)
        source_root = source_tree.getroot()
        header = source_root.find(f"{TEI}teiHeader")
        if header is None:
            raise ValueError("No <teiHeader> found in source TEI XML")

        # Build the output tree.
        nsmap = {None: TEI_NS}
        root = etree.Element(f"{TEI}TEI", nsmap=nsmap)
        root.append(copy.deepcopy(header))

        text_el = etree.SubElement(root, f"{TEI}text")
        text_el.set(
            "{http://www.w3.org/XML/1998/namespace}lang", document.get("language", "")
        )
        body_el = etree.SubElement(text_el, f"{TEI}body")

        doc_urn = document.get("urn", "")
        div_edition = etree.SubElement(body_el, f"{TEI}div")
        div_edition.set("type", "edition")
        div_edition.set("n", doc_urn)

        for element_dict in document.get("elements", []):
            _emit_element(element_dict, div_edition)

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        etree.indent(root, space="  ")
        etree.ElementTree(root).write(
            str(dest),
            encoding="UTF-8",
            xml_declaration=True,
        )
        logger.info(f"Saved annotated TEI XML: {dest}")


def _emit_element(element_dict: dict, parent: etree._Element) -> None:
    """
    Recursively emit *element_dict* as an lxml child of *parent*.

    ``text_run`` pseudo-elements are not emitted as XML tags; instead their
    tokens are emitted directly as ``<w>`` children of *parent*.
    """
    tagname = element_dict.get("tagname")
    if tagname is None:
        return

    if tagname == "text_run":
        for token in element_dict.get("tokens", []):
            parent.append(_make_token_element(token))
        return

    el = etree.SubElement(parent, f"{TEI}{tagname}")
    for key, val in element_dict.items():
        if key not in _ELEMENT_SKIP_KEYS and val is not None:
            el.set(key, str(val))

    for child in element_dict.get("children", []):
        _emit_element(child, el)


def _make_token_element(token: dict) -> etree._Element:
    """
    Build a ``<w>`` element from a TokenDict, attaching URN, lemma, POS,
    xpos, and all morphological features as XML attributes.
    """
    w = etree.Element(f"{TEI}w")
    w.set("n", token["urn"])
    if token.get("lemma"):
        w.set("lemma", token["lemma"])
    if token.get("pos"):
        w.set("pos", token["pos"])
    if token.get("xpos"):
        w.set("xpos", token["xpos"])
    for feat_key, feat_val in token.get("morphology", {}).items():
        w.set(feat_key.lower(), feat_val)
    w.text = token["text"]

    if token.get("whitespace"):
        w.set("rend", "space-after")

    return w
