"""
JSONCommentarySource — loads commentary annotations from a JSON file.

Expected file format::

    {
      "urn:cts:greekLit:...:1@word[1]": [
        {
          "type": "commentary",
          "target_urn": "urn:cts:...",
          "display_label": "note 1"
        }
      ]
    }

Keys are CTS token URNs (as produced by ``TEIParser``).  Values are lists
of ``LinkDict``-shaped objects.
"""

import json
from pathlib import Path


class JSONCommentarySource:
    """
    Resolves commentary links from a pre-built JSON mapping file.

    Parameters
    ----------
    path:
        Path to the JSON annotations file.
    """

    def __init__(self, path: Path | str) -> None:
        with open(path, encoding="utf-8") as f:
            self._data: dict[str, list[dict]] = json.load(f)

    def get_links(self, token_urns: list[str]) -> dict[str, list[dict]]:
        return {urn: self._data[urn] for urn in token_urns if urn in self._data}
