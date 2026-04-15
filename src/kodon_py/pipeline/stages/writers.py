"""
DocumentWriter implementations for the kodon-py pipeline.

``JSONWriter``
    Mirrors the output of ``ingestion.py::parse_tei_to_json``, including
    the ``.metadata.json`` sidecar file.

``TEIXMLWriter``
    Builds a new XML file from the output of JSON writer, converting
    inline annotations to standoff and (TODO) normalizing the TEI
    elements that are used.
"""

import copy
import json
import logging
import re
from pathlib import Path

from lxml import etree

from kodon_py.tei_parser import create_table_of_contents

logger = logging.getLogger(__name__)

TEI_NS = "http://www.tei-c.org/ns/1.0"
TEI = f"{{{TEI_NS}}}"

# TEI elements whose text content should be tokenised into <w> elements.
# Other elements (pb, lb, milestone, gap …) carry no prose text.
_PROSE_TAGS = frozenset(["p", "head", "l", "q", "quote", "hi", "label", "foreign"])

# TEI elements that should be extracted from the body and placed in <standOff>.
# <choice> carries its <sic>/<corr> or <orig>/<reg> children along with it.
_STANDOFF_TAGS = frozenset(["note", "choice", "del", "gap"])


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

# Regex to extract tagname and index from element URNs like
# "urn:cts:...@<p>[0]"
_ELEMENT_URN_RE = re.compile(r"@<(\w+)>\[(\d+)\]$")


class TEIXMLWriter:
    """
    Produces (standoff) annotated and normalized TEI XML with ``<w>`` elements for each token.
    """

    def write(self, document: dict, destination: Path | str) -> None:
        source_path = document.get("source_file")
        if not source_path:
            raise ValueError("DocumentDict must contain 'source_file' for TEIXMLWriter")

        tree = etree.parse(source_path)
        root = tree.getroot()

        # Build element lookup keyed by (textpart_urn, tagname, index)
        element_lookup: dict[tuple[str, str, int], dict] = {}
        for el in document.get("elements", []):
            m = _ELEMENT_URN_RE.search(el.get("urn", ""))
            if m:
                key = (el["textpart_urn"], m.group(1), int(m.group(2)))
                element_lookup[key] = el

        body = root.find(f".//{TEI}body")
        if body is None:
            raise ValueError("No <body> element found in source TEI XML")

        standoff_el = etree.Element(f"{TEI}standOff")
        walker = _TreeWalker(element_lookup, standoff_el)
        walker.walk(body)

        if len(standoff_el):
            root.append(standoff_el)

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tree.write(
            str(dest),
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )
        logger.info(f"Saved annotated TEI XML: {dest}")


class _TreeWalker:
    """
    Walks an lxml element tree and replaces text nodes in prose elements
    with sequences of ``<w>`` (and optionally ``<ref>`` / ``<interp>``)
    elements drawn from the document dict.
    """

    def __init__(self, element_lookup: dict, standoff: etree._Element) -> None:
        self._lookup = element_lookup
        self._standoff = standoff
        # Per-type <listAnnotation> children of <standOff>, created on demand.
        self._standoff_lists: dict[str, etree._Element] = {}
        # Per-textpart, per-tagname occurrence counters — mirrors the
        # counting in TEIParser.handle_element.
        self._counters: dict[str, dict[str, int]] = {}
        self._current_textpart_urn: str | None = None

    def walk(self, node: etree._Element) -> None:
        localname = etree.QName(node).localname

        # Track textpart URN as we descend into <div type="textpart"> elements.
        if localname == "div":
            div_type = node.get("type")
            if div_type == "edition":
                doc_urn = node.get("n", "")
                # Reset state for a new document
                self._counters = {}
                self._current_textpart_urn = None
                self._doc_urn = doc_urn
            elif div_type == "textpart":
                self._current_textpart_urn = self._compute_textpart_urn(node)
                if self._current_textpart_urn not in self._counters:
                    self._counters[self._current_textpart_urn] = {}

        if localname in _PROSE_TAGS and self._current_textpart_urn is not None:
            self._patch_prose_element(node, localname)
        else:
            for child in list(node):
                if etree.QName(child).localname in _STANDOFF_TAGS:
                    self._move_to_standoff(child)
                    node.remove(child)
                else:
                    self.walk(child)

    def _compute_textpart_urn(self, div_node: etree._Element) -> str:
        """
        Reconstruct the textpart URN by walking up to collect @n values.
        This mirrors the location-building logic in TEIParser.
        """
        n_parts: list[str] = []
        node: etree._Element | None = div_node
        while node is not None:
            if etree.QName(node).localname == "div" and node.get("type") == "textpart":
                n = node.get("n")
                if n:
                    n_parts.insert(0, n)
            elif etree.QName(node).localname == "div" and node.get("type") == "edition":
                break
            node = node.getparent()
        doc_urn = getattr(self, "_doc_urn", "")
        return f"{doc_urn}:{'.'.join(n_parts)}" if n_parts else doc_urn

    def _move_to_standoff(self, node: etree._Element) -> None:
        """
        Deep-copy *node* into the appropriate ``<listAnnotation>`` inside
        ``<standOff>``, annotated with the current textpart URN as ``target``.
        """
        tagname = etree.QName(node).localname
        list_ann = self._standoff_lists.get(tagname)
        if list_ann is None:
            list_ann = etree.SubElement(self._standoff, f"{TEI}listAnnotation")
            list_ann.set("type", tagname)
            self._standoff_lists[tagname] = list_ann

        annotation = etree.SubElement(list_ann, f"{TEI}annotation")
        annotation.set("target", self._current_textpart_urn or "")
        annotation.append(copy.deepcopy(node))

    def _patch_prose_element(self, node: etree._Element, tagname: str) -> None:
        """
        Replace the text content of a prose element with ``<w>`` elements.

        Any standoff-candidate children (``<note>``, ``<choice>`` etc.) are
        extracted into ``<standOff>`` before the element is rebuilt so that
        their tokens do not appear inline.
        """
        # Extract any embedded standoff elements before clearing the node.
        for child in list(node):
            if etree.QName(child).localname in _STANDOFF_TAGS:
                self._move_to_standoff(child)
                node.remove(child)

        tp_urn = self._current_textpart_urn
        counter = self._counters.setdefault(tp_urn, {})
        idx = counter.get(tagname, 0)
        counter[tagname] = idx + 1

        key = (tp_urn, tagname, idx)
        element_dict = self._lookup.get(key)
        if element_dict is None:
            # No matching ElementDict — walk children normally
            for child in node:
                self.walk(child)
            return

        # Collect tokens, stopping at standoff-candidate children so their
        # text does not appear inline.
        tokens = _collect_tokens(element_dict)
        if not tokens:
            for child in node:
                self.walk(child)
            return

        # Clear the element's text and children, then repopulate with <w> nodes
        node.text = None
        # Remove child elements that are pure text containers; keep structural
        # children (lb, pb, milestone) that carry no text tokens.
        structural_children = [
            c for c in list(node) if etree.QName(c).localname not in _PROSE_TAGS
        ]
        for c in list(node):
            node.remove(c)

        prev: etree._Element | None = None
        for token in tokens:
            w_or_ref = _make_token_element(token)

            if prev is None:
                node.text = (node.text or "") + ""
            else:
                # whitespace is encoded on w.tail
                pass

            node.append(w_or_ref)
            prev = w_or_ref

            # Commentary interp elements come as siblings after the <w>
            for link in token.get("links", []):
                if link.get("type") == "commentary":
                    interp = etree.SubElement(node, f"{TEI}interp")
                    interp.set("ana", "commentary")
                    interp.set("corresp", token["urn"])
                    interp.set("target", link["target_urn"])
                    if link.get("display_label"):
                        interp.set("n", link["display_label"])

        # Re-append any structural children that were present originally
        for c in structural_children:
            node.append(c)
            self.walk(c)


def _collect_tokens(element_dict: dict) -> list[dict]:
    """
    Recursively collect tokens from an ElementDict's children, preserving
    document order.  Descent stops at standoff-candidate children
    (``_STANDOFF_TAGS``) so their tokens are not included in the inline text.
    """
    tokens: list[dict] = []
    for child in element_dict.get("children", []):
        if child.get("tagname") == "text_run":
            tokens.extend(child.get("tokens", []))
        elif child.get("tagname") in _STANDOFF_TAGS:
            continue
        else:
            tokens.extend(_collect_tokens(child))
    return tokens


def _make_token_element(token: dict) -> etree._Element:
    """
    Build a ``<w>`` element (or ``<ref><w/></ref>`` for cross-references)
    from a TokenDict.
    """
    cross_ref_links = [
        lnk for lnk in token.get("links", []) if lnk.get("type") == "cross_reference"
    ]

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
    w.tail = " " if token.get("whitespace") else ""

    if not cross_ref_links:
        return w

    # Wrap in <ref> for the first cross-reference link.
    # Multiple cross-reference links on the same token are unusual;
    # we wrap once and set the first target.
    ref = etree.Element(f"{TEI}ref")
    ref.set("target", cross_ref_links[0]["target_urn"])
    if cross_ref_links[0].get("display_label"):
        ref.set("n", cross_ref_links[0]["display_label"])
    ref.append(w)
    ref.tail = w.tail
    w.tail = None
    return ref
