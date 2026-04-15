"""
TypedDict definitions for the kodon-py pipeline document model.

These types describe the dict structure that flows through the pipeline.
They are for IDE support and stage-author guidance; no runtime enforcement
is applied. Existing consumers that only read ``text``, ``urn``, and
``whitespace`` from token dicts are unaffected — the new fields are simply
absent when the corresponding stage has not run.
"""

from typing import Required, TypedDict


class LinkDict(TypedDict):
    """A link from a token to an external resource identified by a CTS URN."""

    type: str  # "commentary" | "cross_reference"
    target_urn: str
    display_label: str | None


class TokenDict(TypedDict, total=False):
    # Always present (set by TEIParser / TEIXMLReader)
    text: Required[str]
    urn: Required[str]
    whitespace: Required[bool]
    # Added by MorphologyStage
    lemma: str
    pos: str  # Universal Dependencies POS tag
    xpos: str  # language-specific POS tag
    morphology: dict[str, str]  # e.g. {"Case": "Nom", "Number": "Sing"}
    # Added by CommentaryStage or CrossReferenceStage
    links: list[LinkDict]


class TextRunDict(TypedDict):
    tagname: str  # always "text_run"
    index: int
    tokens: list[TokenDict]


class ElementDict(TypedDict, total=False):
    tagname: Required[str]
    index: Required[int]
    urn: Required[str]
    textpart_index: Required[int]
    textpart_urn: Required[str]
    children: Required[list]  # list[ElementDict | TextRunDict]


class TextpartDict(TypedDict, total=False):
    type: Required[str]  # always "textpart"
    subtype: Required[str]
    n: str
    index: Required[int]
    location: Required[list[str]]
    urn: Required[str]
    tokens: list[TokenDict]


class DocumentDict(TypedDict, total=False):
    source_file: Required[str]
    author: str | None
    language: Required[str]
    urn: Required[str]
    textpart_labels: Required[list[str]]
    textparts: Required[list[TextpartDict]]
    elements: Required[list[ElementDict]]
    # Metadata fields preserved from ingestion.py
    editionStmt: str | None
    publicationStmt: str | None
    respStmt: str | None
    sourceDesc: str | None
    title: str | None
