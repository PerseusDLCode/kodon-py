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
XML_NS = "http://www.w3.org/XML/1998/namespace"
XML = f"{{{XML_NS}}}"

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

        content_by_parent = _build_textpart_tree(
            document.get("textparts", []),
            document.get("elements", []),
        )
        for item in content_by_parent.get(None, []):
            _emit_content_item(item, div_edition, content_by_parent)

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        etree.indent(root, space="  ")
        etree.ElementTree(root).write(
            str(dest),
            encoding="UTF-8",
            xml_declaration=True,
        )
        logger.info(f"Saved annotated TEI XML: {dest}")


def _build_textpart_tree(
    textparts: list[dict],
    elements: list[dict],
) -> dict[int | None, list[dict]]:
    """
    Pre-process textparts and elements into an ordered content map.

    Returns ``content_by_parent``: a dict keyed by parent textpart index
    (``None`` for the root / ``div[@type='edition']`` level).  Each value is
    a list of item dicts — either a textpart dict (``item['type'] ==
    'textpart'``) or an element dict — already sorted into document order.

    Document order is recovered by sorting on element ``index`` values, which
    the SAX-based ``TEIParser`` assigns in traversal order.  Child textpart
    blocks are positioned using the minimum element index in their subtree.
    """
    sorted_tps = sorted(textparts, key=lambda tp: tp["index"])

    # Group elements by their owning textpart (textpart_index == -1 → root).
    elements_by_tp: dict[int, list[dict]] = {}
    for el in elements:
        k = el.get("textpart_index", -1)
        elements_by_tp.setdefault(k, []).append(el)

    # Build parent → [child tp] mapping using a depth stack.
    # Textparts are in document-encounter order after sorting by index, so
    # popping items at the same or greater depth gives the correct parent.
    children_by_parent: dict[int | None, list[dict]] = {}
    stack: list[tuple[int, dict]] = []  # (depth, tp_dict)
    for tp in sorted_tps:
        depth = tp.get("depth", 0)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent_key: int | None = stack[-1][1]["index"] if stack else None
        children_by_parent.setdefault(parent_key, []).append(tp)
        stack.append((depth, tp))

    # Minimum element index across a textpart's whole subtree — used as its
    # "document position" when interleaving it with sibling elements.
    _min_cache: dict[int, float] = {}

    def _min_elem_idx(tp_idx: int) -> float:
        if tp_idx in _min_cache:
            return _min_cache[tp_idx]
        own = [e["index"] for e in elements_by_tp.get(tp_idx, [])]
        child_mins = [
            _min_elem_idx(c["index"]) for c in children_by_parent.get(tp_idx, [])
        ]
        result = min(own + child_mins) if (own or child_mins) else float("inf")
        _min_cache[tp_idx] = result
        return result

    def _ordered(own_elements: list[dict], child_tps: list[dict]) -> list[dict]:
        items: list[tuple[float, dict]] = [
            (el["index"], el) for el in own_elements
        ]
        items += [(_min_elem_idx(tp["index"]), tp) for tp in child_tps]
        return [item for _, item in sorted(items, key=lambda x: x[0])]

    # Root level (textpart_index == -1 elements + depth-0 textparts).
    content_by_parent: dict[int | None, list[dict]] = {
        None: _ordered(
            sorted(elements_by_tp.get(-1, []), key=lambda e: e["index"]),
            children_by_parent.get(None, []),
        )
    }

    # Per-textpart ordered content.
    for tp in sorted_tps:
        tp_idx = tp["index"]
        content_by_parent[tp_idx] = _ordered(
            sorted(elements_by_tp.get(tp_idx, []), key=lambda e: e["index"]),
            children_by_parent.get(tp_idx, []),
        )

    return content_by_parent


def _emit_content_item(
    item: dict,
    parent_el: etree._Element,
    content_by_parent: dict[int | None, list[dict]],
) -> None:
    """
    Emit one content item (textpart or element) as a child of *parent_el*.

    Textpart items open a ``<div type="textpart">`` element, recurse into
    their ordered children, then close — the SAX startElement / content /
    endElement pattern.  Element items delegate to :func:`_emit_element`.
    """
    if item.get("type") == "textpart":
        div_tp = etree.SubElement(parent_el, f"{TEI}div")
        div_tp.set("type", "textpart")
        if item.get("subtype") is not None:
            div_tp.set("subtype", item["subtype"])
        div_tp.set(f"{XML}id", f"textpart_{item['index']}")
        if item.get("corresp") is None and item.get("urn") is not None:
            div_tp.set("corresp", item["urn"])
        for child in content_by_parent.get(item["index"], []):
            _emit_content_item(child, div_tp, content_by_parent)
    else:
        _emit_element(item, parent_el)


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
