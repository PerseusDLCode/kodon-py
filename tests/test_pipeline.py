"""
Tests for the kodon_py.pipeline package.

These tests cover:
- Protocol isinstance checks
- Pipeline orchestration (reader → stages → writer)
- CommentaryStage link attachment
- CrossReferenceStage link attachment
- JSONWriter output format
- TEIXMLReader producing a DocumentDict equivalent to ingestion.py
- CLI pipeline command (smoke test)
"""

import json
from pathlib import Path

import pytest

from kodon_py.pipeline import (
    CommentarySource,
    CommentaryStage,
    CrossReferenceResolver,
    CrossReferenceStage,
    DocumentReader,
    DocumentStage,
    DocumentWriter,
    JSONCommentarySource,
    JSONWriter,
    MorphologyStage,
    NoOpCrossReferenceResolver,
    Pipeline,
    TEIXMLReader,
    TEIXMLWriter,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _EchoStage:
    """Stage that records the document it received and returns it unchanged."""

    def __init__(self):
        self.called_with = None

    def process(self, document: dict) -> dict:
        self.called_with = document
        return document


class _ConstantReader:
    """Reader that returns a pre-built document dict."""

    def __init__(self, document: dict):
        self._doc = document

    def read(self, source: object) -> dict:
        return dict(self._doc)


class _CaptureWriter:
    """Writer that captures the document instead of writing to disk."""

    def __init__(self):
        self.written = None
        self.destination = None

    def write(self, document: dict, destination: object) -> None:
        self.written = document
        self.destination = destination


# ---------------------------------------------------------------------------
# Protocol isinstance checks
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_tei_reader_satisfies_document_reader(self):
        assert isinstance(TEIXMLReader(), DocumentReader)

    def test_json_writer_satisfies_document_writer(self):
        assert isinstance(JSONWriter(), DocumentWriter)

    def test_tei_xml_writer_satisfies_document_writer(self):
        assert isinstance(TEIXMLWriter(), DocumentWriter)

    def test_noop_resolver_satisfies_cross_reference_resolver(self):
        assert isinstance(NoOpCrossReferenceResolver(), CrossReferenceResolver)

    def test_echo_stage_satisfies_document_stage(self):
        assert isinstance(_EchoStage(), DocumentStage)

    def test_constant_reader_satisfies_document_reader(self):
        assert isinstance(_ConstantReader({}), DocumentReader)

    def test_capture_writer_satisfies_document_writer(self):
        assert isinstance(_CaptureWriter(), DocumentWriter)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


class TestPipeline:
    def _make_pipeline(self, stages=None, writer=None):
        doc = {"urn": "urn:cts:test", "textparts": [], "elements": []}
        reader = _ConstantReader(doc)
        writer = writer or _CaptureWriter()
        return Pipeline(reader=reader, stages=stages or [], writer=writer), writer

    def test_run_returns_document(self):
        pipeline, writer = self._make_pipeline()
        result = pipeline.run("ignored_source", "ignored_dest")
        assert result == writer.written

    def test_stages_are_called_in_order(self):
        calls = []

        class _OrderStage:
            def __init__(self, n):
                self.n = n

            def process(self, doc):
                calls.append(self.n)
                return doc

        pipeline, _ = self._make_pipeline(stages=[_OrderStage(1), _OrderStage(2)])
        pipeline.run("src", "dst")
        assert calls == [1, 2]

    def test_stage_can_enrich_document(self):
        class _AddKeyStage:
            def process(self, doc):
                doc["added"] = True
                return doc

        pipeline, writer = self._make_pipeline(stages=[_AddKeyStage()])
        pipeline.run("src", "dst")
        assert writer.written.get("added") is True

    def test_run_batch_skips_existing(self, tmp_path):
        existing = tmp_path / "existing.json"
        existing.write_text("{}")
        new_dest = tmp_path / "new.json"

        processed = []

        class _TrackingWriter:
            def write(self, doc, dest):
                processed.append(dest)

        pipeline, _ = self._make_pipeline(writer=_TrackingWriter())
        pipeline.run_batch(
            [("src1", existing), ("src2", new_dest)], skip_existing=True
        )
        assert existing not in processed
        assert new_dest in processed

    def test_run_batch_no_skip(self, tmp_path):
        existing = tmp_path / "existing.json"
        existing.write_text("{}")

        processed = []

        class _TrackingWriter:
            def write(self, doc, dest):
                processed.append(dest)

        pipeline, _ = self._make_pipeline(writer=_TrackingWriter())
        pipeline.run_batch([("src1", existing)], skip_existing=False)
        assert existing in processed


# ---------------------------------------------------------------------------
# CommentaryStage
# ---------------------------------------------------------------------------


class TestCommentaryStage:
    def _make_doc(self, tokens):
        return {
            "textparts": [{"urn": "urn:cts:test:1", "tokens": tokens}],
            "elements": [],
        }

    def test_links_attached_to_matching_tokens(self):
        tokens = [
            {"text": "foo", "urn": "urn:cts:test:1@foo[1]", "whitespace": True},
            {"text": "bar", "urn": "urn:cts:test:1@bar[1]", "whitespace": False},
        ]
        doc = self._make_doc(tokens)

        class _Source:
            def get_links(self, urns):
                return {
                    "urn:cts:test:1@foo[1]": [
                        {
                            "type": "commentary",
                            "target_urn": "urn:cts:comment:1",
                            "display_label": None,
                        }
                    ]
                }

        stage = CommentaryStage(source=_Source())
        result = stage.process(doc)

        foo_token = result["textparts"][0]["tokens"][0]
        bar_token = result["textparts"][0]["tokens"][1]
        assert len(foo_token["links"]) == 1
        assert foo_token["links"][0]["type"] == "commentary"
        assert "links" not in bar_token

    def test_links_merged_with_existing(self):
        existing_link = {
            "type": "cross_reference",
            "target_urn": "urn:cts:other:1",
            "display_label": None,
        }
        tokens = [
            {
                "text": "foo",
                "urn": "urn:cts:test:1@foo[1]",
                "whitespace": True,
                "links": [existing_link],
            }
        ]
        doc = self._make_doc(tokens)

        class _Source:
            def get_links(self, urns):
                return {
                    "urn:cts:test:1@foo[1]": [
                        {
                            "type": "commentary",
                            "target_urn": "urn:cts:comment:1",
                            "display_label": None,
                        }
                    ]
                }

        stage = CommentaryStage(source=_Source())
        result = stage.process(doc)
        assert len(result["textparts"][0]["tokens"][0]["links"]) == 2

    def test_source_exception_is_logged_and_skipped(self, caplog):
        import logging

        tokens = [{"text": "x", "urn": "urn:cts:test:1@x[1]", "whitespace": False}]
        doc = self._make_doc(tokens)

        class _BrokenSource:
            def get_links(self, urns):
                raise RuntimeError("DB down")

        stage = CommentaryStage(source=_BrokenSource())
        with caplog.at_level(logging.ERROR):
            result = stage.process(doc)

        # Document returned unchanged, no crash
        assert result["textparts"][0]["tokens"][0] == tokens[0]


# ---------------------------------------------------------------------------
# CrossReferenceStage
# ---------------------------------------------------------------------------


class TestCrossReferenceStage:
    def test_noop_resolver_leaves_tokens_unchanged(self):
        tokens = [{"text": "foo", "urn": "urn:cts:test:1@foo[1]", "whitespace": True}]
        doc = {
            "textparts": [{"urn": "urn:cts:test:1", "tokens": tokens}],
            "elements": [],
        }
        stage = CrossReferenceStage(resolver=NoOpCrossReferenceResolver())
        result = stage.process(doc)
        assert "links" not in result["textparts"][0]["tokens"][0]

    def test_custom_resolver_attaches_links(self):
        tokens = [
            {"text": "Hom", "urn": "urn:cts:test:1@Hom[1]", "whitespace": False},
            {"text": "Il", "urn": "urn:cts:test:1@Il[1]", "whitespace": False},
        ]
        doc = {
            "textparts": [{"urn": "urn:cts:test:1", "tokens": tokens}],
            "elements": [],
        }

        class _MyResolver:
            def resolve(self, toks):
                return {
                    "urn:cts:test:1@Hom[1]": [
                        {
                            "type": "cross_reference",
                            "target_urn": "urn:cts:greekLit:tlg0012.tlg001",
                            "display_label": "Homer, Iliad",
                        }
                    ]
                }

        stage = CrossReferenceStage(resolver=_MyResolver())
        result = stage.process(doc)
        assert result["textparts"][0]["tokens"][0]["links"][0]["type"] == "cross_reference"


# ---------------------------------------------------------------------------
# JSONWriter
# ---------------------------------------------------------------------------


class TestJSONWriter:
    def test_writes_json_file(self, tmp_path, sample_parsed_data):
        dest = tmp_path / "out.json"
        writer = JSONWriter(write_metadata=False)
        writer.write(sample_parsed_data, dest)
        assert dest.exists()
        loaded = json.loads(dest.read_text())
        assert loaded["urn"] == sample_parsed_data["urn"]

    def test_writes_metadata_sidecar(self, tmp_path, sample_parsed_data):
        dest = tmp_path / "out.json"
        writer = JSONWriter(write_metadata=True)
        writer.write(sample_parsed_data, dest)
        metadata_path = tmp_path / "out.metadata.json"
        assert metadata_path.exists()
        meta = json.loads(metadata_path.read_text())
        assert meta["urn"] == sample_parsed_data["urn"]

    def test_creates_parent_directories(self, tmp_path, sample_parsed_data):
        dest = tmp_path / "nested" / "deep" / "out.json"
        writer = JSONWriter(write_metadata=False)
        writer.write(sample_parsed_data, dest)
        assert dest.exists()

    def test_pipeline_with_json_writer_round_trips(self, tmp_path, sample_parsed_data):
        dest = tmp_path / "out.json"
        pipeline = Pipeline(
            reader=_ConstantReader(sample_parsed_data),
            stages=[],
            writer=JSONWriter(write_metadata=False),
        )
        pipeline.run("ignored", dest)
        loaded = json.loads(dest.read_text())
        assert loaded["author"] == "Test Author"


# ---------------------------------------------------------------------------
# TEIXMLReader (integration — requires test_tei fixture)
# ---------------------------------------------------------------------------


class TestTEIXMLReader:
    def test_reader_produces_required_keys(self, test_tei_file):
        reader = TEIXMLReader()
        doc = reader.read(test_tei_file)
        for key in ("source_file", "language", "urn", "textpart_labels", "textparts", "elements"):
            assert key in doc, f"Missing key: {key}"

    def test_reader_output_matches_ingestion(self, test_tei_file, tmp_path):
        """JSONWriter output must be identical to ingestion.py output."""
        from kodon_py.ingestion import parse_tei_to_json

        ingestion_dest = tmp_path / "ingestion.json"
        parse_tei_to_json(test_tei_file, ingestion_dest)
        ingestion_output = json.loads(ingestion_dest.read_text())

        pipeline_dest = tmp_path / "pipeline.json"
        pipeline = Pipeline(
            reader=TEIXMLReader(),
            stages=[],
            writer=JSONWriter(write_metadata=False),
        )
        pipeline.run(test_tei_file, pipeline_dest)
        pipeline_output = json.loads(pipeline_dest.read_text())

        # Key structural fields must match
        assert pipeline_output["urn"] == ingestion_output["urn"]
        assert pipeline_output["language"] == ingestion_output["language"]
        assert len(pipeline_output["textparts"]) == len(ingestion_output["textparts"])
        assert len(pipeline_output["elements"]) == len(ingestion_output["elements"])


# ---------------------------------------------------------------------------
# JSONCommentarySource
# ---------------------------------------------------------------------------


class TestJSONCommentarySource:
    def test_loads_and_returns_matching_links(self, tmp_path):
        data = {
            "urn:cts:test:1@foo[1]": [
                {"type": "commentary", "target_urn": "urn:cts:c:1", "display_label": "n1"}
            ]
        }
        path = tmp_path / "annotations.json"
        path.write_text(json.dumps(data))

        source = JSONCommentarySource(path)
        result = source.get_links(["urn:cts:test:1@foo[1]", "urn:cts:test:1@bar[1]"])

        assert "urn:cts:test:1@foo[1]" in result
        assert "urn:cts:test:1@bar[1]" not in result
        assert result["urn:cts:test:1@foo[1]"][0]["type"] == "commentary"

    def test_returns_empty_dict_for_no_matches(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("{}")
        source = JSONCommentarySource(path)
        assert source.get_links(["urn:cts:test:1@x[1]"]) == {}


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


class TestCLI:
    def test_pipeline_command_json_output(self, tmp_path, test_tei_file):
        from click.testing import CliRunner

        from kodon_py.cli import cli

        source_dir = test_tei_file.parent
        output_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "ingest",
                "pipeline",
                str(source_dir),
                "--output-dir",
                str(output_dir),
                "--output-format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        json_files = list(output_dir.rglob("*.json"))
        # At least the main JSON (metadata excluded from glob check)
        main_jsons = [f for f in json_files if ".metadata." not in f.name]
        assert len(main_jsons) > 0
