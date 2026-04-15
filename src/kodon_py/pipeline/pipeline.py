"""
Pipeline orchestrator for kodon-py.

A ``Pipeline`` chains a reader, zero or more stages, and a writer:

    pipeline = Pipeline(
        reader=TEIXMLReader(),
        stages=[MorphologyStage(), CommentaryStage(source=...)],
        writer=TEIXMLWriter(),
    )
    pipeline.run(Path("text.xml"), Path("text_annotated.xml"))
"""

from pathlib import Path

from kodon_py.pipeline.protocols import DocumentReader, DocumentStage, DocumentWriter


class Pipeline:
    def __init__(
        self,
        reader: DocumentReader,
        stages: list[DocumentStage],
        writer: DocumentWriter,
    ) -> None:
        self.reader = reader
        self.stages = stages
        self.writer = writer

    def run(self, source: object, destination: object) -> dict:
        """
        Process a single source through all stages and write the result.

        Returns the final DocumentDict so callers can inspect or further
        process the enriched document programmatically.
        """
        document = self.reader.read(source)
        for stage in self.stages:
            document = stage.process(document)
        self.writer.write(document, destination)
        return document

    def run_batch(
        self,
        sources: list[tuple[object, object]],
        *,
        skip_existing: bool = True,
    ) -> None:
        """
        Process multiple ``(source, destination)`` pairs.

        When ``skip_existing=True`` (the default), destinations that
        already exist as files on disk are skipped — mirroring the
        resumable behaviour of ``ingestion.py``.
        """
        for source, destination in sources:
            if skip_existing and isinstance(destination, Path) and destination.exists():
                continue
            self.run(source, destination)
