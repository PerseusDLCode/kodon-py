"""
Copyright 2025 Galenus Verbatim

Ce projet a bénéficié du financement de
l'[Institut universitaire de France](https://www.iufrance.fr),
ainsi que de
l'[Initiative humanités biomédicales de l'Alliance Sorbonne Université](https://humanites-biomedicales.sorbonne-universite.fr)
pour sa partie latine.

TEI Parser with JSON export
---------------------------------------

This module parses TEI (Text Encoding Initiative) XML files
to JSON.

Usage:
    from kodon_py.tei_parser.tei_parser import TEIParser

    # Parse a TEI file
    parser = TEIParser("path/to/tei_file.xml")

    # Access parsed data in memory
    print(f"Document URN: {parser.urn}")
    print(f"Language: {parser.lang}")
    print(f"Textparts: {len(parser.textparts)}")
    print(f"Elements: {len(parser.elements)}")
"""

## TODO
# - [ ] Explore lemmatization options: https://github.com/bowphs/SIGTYP-2024-hierarchical-transformers/issues/1

import logging
from pathlib import Path
from xml.sax import xmlreader
from xml.sax.handler import ContentHandler

import lxml.sax  # pyright: ignore
import stanza
from lxml import etree

NAMESPACES = {"tei": "http://www.tei-c.org/ns/1.0"}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

tmp_dir = Path("tmp")

if not tmp_dir.exists():
    tmp_dir.mkdir()

log_filepath = tmp_dir / Path(f"{__name__}.log")

file_handler = logging.FileHandler(log_filepath, mode="w")

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


greek_tokenizer = stanza.Pipeline(
    "grc",
    processors="tokenize",
    package="perseus",
    model_dir="./stanza_models",
    download_method=stanza.DownloadMethod.REUSE_RESOURCES,
)

latin_tokenizer = stanza.Pipeline(
    "la",
    processors="tokenize",
    package="perseus",
    model_dir="./stanza_models",
    download_method=stanza.DownloadMethod.REUSE_RESOURCES,
)


def create_table_of_contents(textparts, textpart_labels):
    textparts = [
        dict(
            label=f"{t['subtype'].capitalize()} {t.get('n', '')}".strip(),
            urn=t["urn"],
            subtype=t["subtype"],
        )
        for t in textparts
        if t.get("type") == "textpart"
    ]

    if len(textpart_labels) == 1:
        return textparts

    hierarchy = list(textpart_labels)

    return nest_textparts(textparts, hierarchy)


def nest_textparts(textparts, hierarchy):
    stack = []

    for item in textparts:
        level = hierarchy.index(item["subtype"])

        if len(stack) == 0:
            stack.append((level, item))
            continue

        children = []

        while stack and stack[-1][0] > level:
            children.append(stack.pop()[1])

        if children:
            item["subpassages"] = list(reversed(children))

        stack.append((level, item))

    return [item for _level, item in stack]


def remove_ns_from_attrs(attrs: xmlreader.AttributesNSImpl):
    a = {}

    for k, v in attrs.items():
        _ns, localname = k

        a[localname] = v

    return a


class TEIParser(ContentHandler):
    """
    The TEIParser holds information from the TEI XML version
    of a given text.

    The XML structure of the editionStmt,
    publicationStmt, respStmt, and sourceDesc are stored
    as strings for later parsing and use.
    """

    def __init__(self, filename: Path | str):
        self.filename = filename
        self.tree = etree.parse(filename)
        self.tokenizer = None

        self.author = self.get_author()
        # citable_elements are those that are defined
        # in the refsDecl; we need to track these in
        # order to update the URN whenever we encounter
        # one.
        self.citable_elements = self.get_citable_elements()
        self.editionStmt = self.get_editionStmt()
        self.language = None
        self.publicationStmt = self.get_publicationStmt()
        self.refsDecl = self.get_refsDecl()
        self.respStmt = self.get_respStmt()
        self.sourceDesc = self.get_sourceDesc()
        self.title = self.get_title()
        self.urn = None

        self.current_tokens: list[str] = []
        self.current_textpart_location = None
        self.current_textpart_urn = None

        self.element_stack = []
        self.elements = []
        self.global_element_index = 0
        self.textpart_labels = []
        self.textpart_stack = []
        self.textparts = []
        self.unhandled_elements = set()

        for body in self.tree.iterfind(".//tei:body", namespaces=NAMESPACES):
            lxml.sax.saxify(body, self)

    def add_textpart_to_stack(self, attrs: dict):
        subtype = attrs.get("subtype")

        if subtype is not None and subtype not in self.textpart_labels:
            self.textpart_labels.append(subtype)

        location = self.determine_location(attrs)

        self.current_textpart_location = location
        self.current_textpart_urn = (
            f"{self.urn}:{'.'.join(self.current_textpart_location)}"
        )

        attrs.update(
            {
                "index": len(self.textpart_stack) + len(self.textparts),
                "location": location,
                "urn": self.current_textpart_urn,
            }
        )

        self.textpart_stack.append(attrs)

    def characters(self, content: str) -> None:
        if len(self.element_stack) == 0:
            if content.strip() != "":
                logger.warning(
                    f"{self.urn}\nCharacters must belong to an element, but no elements are available."
                )
                logger.warning(content)
            return

        parent_element = self.element_stack[-1]
        tokens = self.tokenize(content)
        text_run = self.process_tokens(tokens)

        if text_run is not None:
            parent_element["children"].append(text_run)

    def determine_location(self, attrs: dict):
        citation_n = attrs.get("n")

        if citation_n is None:
            logger.debug(f"{self.urn}\nUnnumbered textpart: {attrs}")

        location = []

        for n in [t.get("n") for t in self.textpart_stack]:
            if n is not None:
                location.append(n)

        if citation_n is not None:
            location.append(citation_n)

        return location

    def endElementNS(self, name: tuple[str | None, str], qname: str | None) -> None:
        _uri, localname = name

        if localname == "div" and len(self.textpart_stack) > 0:
            textpart = self.textpart_stack.pop()

            self.textparts.append(textpart)

        elif len(self.element_stack) > 0:
            el = self.element_stack.pop()

            el.update(
                {
                    "urn": el.get("urn", self.current_textpart_urn),
                }
            )

            if len(self.element_stack) > 0:
                if (
                    len(
                        [
                            x
                            for x in self.element_stack[-1]["children"]
                            if x.get("index") == el["index"]
                        ]
                    )
                    == 0
                ):
                    self.elements.append(el)
            else:
                self.elements.append(el)

    def get_author(self):
        el = self.tree.find(".//tei:author", namespaces=NAMESPACES)

        if el is not None:
            return etree.tostring(
                el, encoding="unicode", method="text", xml_declaration=False
            )

    def get_citable_elements(self):
        refsDecl = self.tree.find(".//tei:refsDecl", namespaces=NAMESPACES)

    def get_editionStmt(self):
        return self.get_stringifiedXML("editionStmt")

    def get_publicationStmt(self):
        return self.get_stringifiedXML("publicationStmt")

    def get_refsDecl(self):
        return self.get_stringifiedXML("refsDecl")

    def get_respStmt(self):
        return self.get_stringifiedXML("respStmt")

    def get_sourceDesc(self):
        return self.get_stringifiedXML("sourceDesc", required=True)

    def get_stringifiedXML(self, tagname: str, required=False):
        el = self.tree.find(f".//tei:{tagname}", namespaces=NAMESPACES)

        if required and el is None:
            raise ValueError(f"{tagname} is required! {self.filename}")

        if el is not None:
            return etree.tostring(el, encoding="unicode", xml_declaration=False)

    def get_title(self):
        el = self.tree.find(".//tei:title", namespaces=NAMESPACES)

        if el is not None:
            return etree.tostring(
                el, encoding="unicode", method="text", xml_declaration=False
            )

    def handle_div(self, attrs: dict):
        if attrs["type"] == "edition":
            self.language = attrs["lang"]
            self.urn = attrs["n"]

        elif attrs["type"] == "textpart":
            self.add_textpart_to_stack(attrs)

    def handle_element(self, tagname: str, attrs: dict):
        textpart = None

        if len(self.textpart_stack) == 0:
            logger.warning(
                f"{self.urn}\nElements should not appear outside of textparts: {tagname}, {attrs}"
            )

            if len(self.textparts) > 0:
                textpart = self.textparts[-1]
        else:
            textpart = self.textpart_stack[-1]

        textpart_index = -1
        urn_element_index = -1
        current_textpart_urn = self.current_textpart_urn
        if textpart is None:
            logger.warning(
                f"{self.urn}\nOrphaned element: {tagname}, {attrs} — no textpart available."
            )
            current_textpart_urn = f"{self.urn}:-1"
        else:
            textpart_index = textpart["index"]
            urn_element_index = sum(
                [
                    1
                    for el in self.elements + self.element_stack
                    if el["textpart_urn"] == current_textpart_urn
                    and el["tagname"] == tagname
                ]
            )

        element_index = self.global_element_index
        self.global_element_index += 1

        attrs.update(
            {
                "children": [],
                "index": element_index,
                "tagname": tagname,
                "textpart_index": textpart_index,
                "textpart_urn": current_textpart_urn,
                "urn": f"{current_textpart_urn}@<{tagname}>[{urn_element_index}]",
            }
        )

        # If there is an unclosed element at the end of the stack,
        # add this element to its children.
        if len(self.element_stack) > 0:
            if self.element_stack[-1]["textpart_index"] != attrs["textpart_index"]:
                logger.warning(
                    f"{self.urn}\nOpen element belongs to a different textpart than current element: {self.element_stack[-1]}\n{attrs}"
                )
            self.element_stack[-1]["children"].append(attrs)

        self.element_stack.append(attrs)

    def process_tokens(self, tokens):
        text_run = []

        textpart = None
        if len(self.textpart_stack) > 0:
            textpart = self.textpart_stack[-1]

        for tok in tokens:
            if tok.text.strip() == "":
                continue

            if textpart is not None:
                urn_token_index = (
                    sum(
                        [1 for t in textpart.get("tokens", []) if t["text"] == tok.text]
                    )
                    + 1
                )
            else:
                urn_token_index = 1

            token = {
                "text": tok.text,
                "urn": f"{self.current_textpart_urn}@{tok.text}[{urn_token_index}]",
                "whitespace": len(tok.spaces_after) > 0,
            }

            if textpart is not None:
                if textpart.get("tokens") is not None:
                    textpart["tokens"].append(token)
                else:
                    textpart["tokens"] = [token]

            text_run.append(token)

        if len(text_run) > 0:
            element_index = self.global_element_index
            self.global_element_index += 1

            return {"tagname": "text_run", "tokens": text_run, "index": element_index}

    def startElementNS(
        self,
        name: tuple[str | None, str],
        qname: str | None,
        attrs: xmlreader.AttributesNSImpl,
    ) -> None:
        _uri, localname = name
        clean_attrs = remove_ns_from_attrs(attrs)

        match localname:
            case "body":
                pass
            case "div":
                return self.handle_div(clean_attrs)
            # By keeping track of elements that we _don't_ handle, we can
            # incrementally identify edge-cases and add handlers for them
            # as needed.
            case (
                "choice"
                | "corr"
                | "del"
                | "foreign"
                | "gap"
                | "head"
                | "hi"
                | "l"
                | "label"
                | "lb"
                | "lg"
                | "milestone"
                | "note"
                | "num"
                | "p"
                | "pb"
                | "q"
                | "quote"
                | "sic"
            ):
                return self.handle_element(localname, clean_attrs)
            case _:
                logger.debug(
                    f"{self.urn}\nUnknown element {localname} in {self.current_textpart_urn}"
                )
                self.unhandled_elements.add(localname)
                self.handle_element(localname, clean_attrs)

    def tokenize(self, s: str):
        tokenizer = None

        if self.language == "grc":
            tokenizer = greek_tokenizer
        elif self.language in ("la", "lat"):
            tokenizer = latin_tokenizer
        else:
            tokenizer = greek_tokenizer

        doc = tokenizer(s)

        if doc is None:
            return []

        tokens = []
        for sentence in doc.sentences:  # pyright: ignore
            for token in sentence.tokens:
                tokens.append(token)

        return tokens
