"""Pytest fixtures for kodon-py tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir():
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
