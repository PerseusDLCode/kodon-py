"""
TEIXMLReader — reads a TEI XML file and produces a DocumentDict.

Wraps the existing ``TEIParser`` so it fits the ``DocumentReader``
protocol without duplicating any parsing logic.
"""

from pathlib import Path

from kodon_py.tei_parser import TEIParser


class TEIXMLReader:
    """
    Reads a TEI XML file and returns a DocumentDict.

    Example::

        reader = TEIXMLReader()
        document = reader.read(Path("text.xml"))
    """

    def read(self, source: Path | str) -> dict:
        parser = TEIParser(source)
        return {
            "source_file": str(source),
            "author": parser.author,
            "editionStmt": parser.editionStmt,
            "language": parser.language,
            "publicationStmt": parser.publicationStmt,
            "respStmt": parser.respStmt,
            "sourceDesc": parser.sourceDesc,
            "title": parser.title,
            "urn": parser.urn,
            "textpart_labels": parser.textpart_labels,
            "textparts": parser.textparts,
            "elements": parser.elements,
        }
