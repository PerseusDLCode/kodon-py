"""
CrossReferenceStage — identifies and links cross-text references.

For each textpart, the full token list is passed to a ``CrossReferenceResolver``
which returns a mapping of token URN → link list.  Returned links are merged
into each token's ``links`` list, preserving any links already attached by
earlier stages (e.g. ``CommentaryStage``).

The resolver receives the complete token list (not individual tokens) so that
multi-token patterns such as "Hom. Il. 1.1" can be matched using lookahead
and context.  If ``MorphologyStage`` has already run, resolvers may use
``token["lemma"]`` for lemma-based pattern matching.
"""

import logging

from kodon_py.pipeline.protocols import CrossReferenceResolver

logger = logging.getLogger(__name__)


class CrossReferenceStage:
    """
    Attaches cross-reference links to tokens using a ``CrossReferenceResolver``.

    Parameters
    ----------
    resolver:
        Any object that satisfies the ``CrossReferenceResolver`` protocol.
        Built-in option: ``NoOpCrossReferenceResolver`` (does nothing).

    Example::

        class MyResolver:
            def resolve(self, tokens):
                # examine token texts / lemmas, return {urn: [link, ...]}
                return {}

        stage = CrossReferenceStage(resolver=MyResolver())
    """

    def __init__(self, resolver: CrossReferenceResolver) -> None:
        self.resolver = resolver

    def process(self, document: dict) -> dict:
        for textpart in document.get("textparts", []):
            tokens = textpart.get("tokens", [])
            if not tokens:
                continue

            try:
                links_by_urn = self.resolver.resolve(tokens)
            except Exception:
                logger.exception(
                    "CrossReferenceResolver.resolve failed for textpart %s",
                    textpart.get("urn"),
                )
                continue

            for token in tokens:
                new_links = links_by_urn.get(token["urn"], [])
                if new_links:
                    token.setdefault("links", [])
                    token["links"].extend(new_links)

        return document
