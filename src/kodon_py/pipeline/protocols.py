"""
Protocol interfaces for the kodon-py pipeline.

Users implement these protocols via duck typing — no inheritance required.
All protocols are decorated with ``@runtime_checkable`` so ``isinstance``
checks work in tests and CLI validation code.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class DocumentStage(Protocol):
    """A stage that transforms a DocumentDict and returns it (or a new one)."""

    def process(self, document: dict) -> dict: ...


@runtime_checkable
class DocumentReader(Protocol):
    """Reads a source and produces a DocumentDict."""

    def read(self, source: object) -> dict: ...


@runtime_checkable
class DocumentWriter(Protocol):
    """Writes a DocumentDict to an output destination."""

    def write(self, document: dict, destination: object) -> None: ...


@runtime_checkable
class CommentarySource(Protocol):
    """
    Resolves commentary links for a batch of token URNs.

    Accepts a list of URNs so that implementations can issue a single
    bulk query (e.g., one SQL ``IN`` clause or one HTTP request) per
    textpart rather than one query per token.

    Returns a mapping of ``token_urn -> list[LinkDict]``.  Missing keys
    mean no links for that token.
    """

    def get_links(self, token_urns: list[str]) -> dict[str, list[dict]]: ...


@runtime_checkable
class CrossReferenceResolver(Protocol):
    """
    Identifies cross-text references within a sequence of tokens.

    Receives the full token list for a textpart so that multi-token
    patterns (e.g., "Hom. Il.") can be matched with lookahead context.
    If ``MorphologyStage`` has already run, implementations may use
    ``token["lemma"]`` for more reliable lemma-based matching.

    Returns a sparse mapping of ``token_urn -> list[LinkDict]`` — only
    URNs that participate in a cross-reference need be included.
    """

    def resolve(self, tokens: list[dict]) -> dict[str, list[dict]]: ...
