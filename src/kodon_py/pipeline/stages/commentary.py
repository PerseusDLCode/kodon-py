"""
CommentaryStage — attaches commentary links to tokens.

For each textpart, all token URNs are collected and passed to the
``CommentarySource`` in a single batch call.  Returned links are merged
into each token's ``links`` list, preserving any links already attached
by earlier stages.
"""

import logging

from kodon_py.pipeline.protocols import CommentarySource

logger = logging.getLogger(__name__)


class CommentaryStage:
    """
    Attaches commentary links to tokens using a ``CommentarySource``.

    Parameters
    ----------
    source:
        Any object that satisfies the ``CommentarySource`` protocol.
        Built-in option: ``JSONCommentarySource``.

    Example::

        from kodon_py.pipeline.sources import JSONCommentarySource

        stage = CommentaryStage(source=JSONCommentarySource("annotations.json"))
    """

    def __init__(self, source: CommentarySource) -> None:
        self.source = source

    def process(self, document: dict) -> dict:
        for textpart in document.get("textparts", []):
            tokens = textpart.get("tokens", [])
            if not tokens:
                continue

            urns = [t["urn"] for t in tokens]
            try:
                links_by_urn = self.source.get_links(urns)
            except Exception:
                logger.exception(
                    "CommentarySource.get_links failed for textpart %s",
                    textpart.get("urn"),
                )
                continue

            for token in tokens:
                new_links = links_by_urn.get(token["urn"], [])
                if new_links:
                    token.setdefault("links", [])
                    token["links"].extend(new_links)

        return document
