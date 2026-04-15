"""
NoOpCrossReferenceResolver — a no-op implementation of CrossReferenceResolver.

Useful as a default when no cross-reference resolution is needed, or as a
base class / test stub.
"""


class NoOpCrossReferenceResolver:
    """Returns an empty dict for every token list."""

    def resolve(self, tokens: list[dict]) -> dict[str, list[dict]]:
        return {}
