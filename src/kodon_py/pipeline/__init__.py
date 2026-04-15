"""
kodon_py.pipeline — pluggable pipeline for TEI XML processing.

Quick start::

    from pathlib import Path
    from kodon_py.pipeline import (
        Pipeline,
        TEIXMLReader,
        MorphologyStage,
        CommentaryStage,
        JSONCommentarySource,
        JSONWriter,
        TEIXMLWriter,
    )

    # TEI XML → JSON (same output as kodon ingest parse)
    pipeline = Pipeline(
        reader=TEIXMLReader(),
        stages=[],
        writer=JSONWriter(),
    )
    pipeline.run(Path("text.xml"), Path("text.json"))

    # TEI XML → annotated TEI XML with morphology + commentary
    pipeline = Pipeline(
        reader=TEIXMLReader(),
        stages=[
            MorphologyStage(language="grc"),
            CommentaryStage(source=JSONCommentarySource("annotations.json")),
        ],
        writer=TEIXMLWriter(),
    )
    pipeline.run(Path("text.xml"), Path("text_annotated.xml"))

Protocols for custom implementations::

    from kodon_py.pipeline import (
        DocumentReader,
        DocumentStage,
        DocumentWriter,
        CommentarySource,
        CrossReferenceResolver,
    )
"""

from kodon_py.pipeline.pipeline import Pipeline
from kodon_py.pipeline.protocols import (
    CommentarySource,
    CrossReferenceResolver,
    DocumentReader,
    DocumentStage,
    DocumentWriter,
)
from kodon_py.pipeline.sources.json_source import JSONCommentarySource
from kodon_py.pipeline.sources.noop_resolver import NoOpCrossReferenceResolver
from kodon_py.pipeline.stages.commentary import CommentaryStage
from kodon_py.pipeline.stages.cross_reference import CrossReferenceStage
from kodon_py.pipeline.stages.morphology import MorphologyStage
from kodon_py.pipeline.stages.tei_reader import TEIXMLReader
from kodon_py.pipeline.stages.writers import JSONWriter, TEIXMLWriter

__all__ = [
    # Core
    "Pipeline",
    # Protocols
    "DocumentReader",
    "DocumentStage",
    "DocumentWriter",
    "CommentarySource",
    "CrossReferenceResolver",
    # Built-in stages
    "TEIXMLReader",
    "MorphologyStage",
    "CommentaryStage",
    "CrossReferenceStage",
    # Built-in writers
    "JSONWriter",
    "TEIXMLWriter",
    # Built-in sources
    "JSONCommentarySource",
    "NoOpCrossReferenceResolver",
]
