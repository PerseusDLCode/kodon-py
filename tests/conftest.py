"""Pytest fixtures for kodon-py tests."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmpdir = Path(tempfile.mkdtemp())
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def test_tei_dir():
    """Path to the test TEI files directory."""
    return Path(__file__).parent.parent / "test_tei"


@pytest.fixture
def test_tei_file(test_tei_dir):
    """Path to a test TEI XML file."""
    files = list(test_tei_dir.glob("*.xml"))
    if not files:
        pytest.skip("No test TEI files available in test_tei/")
    return files[0]


@pytest.fixture
def json_output_dir(temp_dir):
    """Create a temporary directory for JSON output."""
    path = temp_dir / "json_output"
    path.mkdir()
    return path


@pytest.fixture
def sample_parsed_data():
    """Sample parsed TEI data for testing."""
    return {
        "source_file": "/path/to/test.xml",
        "author": "Test Author",
        "editionStmt": "<editionStmt>Test Edition</editionStmt>",
        "language": "grc",
        "publicationStmt": "<publicationStmt>Test Publication</publicationStmt>",
        "respStmt": "<respStmt>Test Resp</respStmt>",
        "sourceDesc": "<sourceDesc>Test Source</sourceDesc>",
        "title": "Test Title",
        "urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1",
        "textpart_labels": ["chapter", "section"],
        "textparts": [
            {
                "index": 0,
                "location": ["1"],
                "n": "1",
                "subtype": "chapter",
                "type": "textpart",
                "urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
            },
        ],
        "elements": [
            {
                "index": 0,
                "tagname": "p",
                "textpart_index": 0,
                "textpart_urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
                "urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]",
                "children": [
                    {
                        "tagname": "text_run",
                        "index": 1,
                        "tokens": [
                            {
                                "text": "Test",
                                "urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@Test[1]",
                                "whitespace": True,
                            },
                            {
                                "text": "content",
                                "urn": "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@content[1]",
                                "whitespace": False,
                            },
                        ],
                    },
                ],
            },
        ],
    }


@pytest.fixture
def sample_json_file(json_output_dir, sample_parsed_data):
    """Create a sample JSON file for testing."""
    json_path = json_output_dir / "test.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sample_parsed_data, f)
    return json_path
