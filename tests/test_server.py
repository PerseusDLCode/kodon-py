"""Tests for the server module."""

import pytest

from kodon_py.server import create_app
from kodon_py.ingestion import get_chunk_dir, ingest_tei_file


@pytest.fixture
def app(tmp_dir, test_tei_file):
    """Create application for testing with ingested data."""
    app = create_app({"TESTING": True})

    # Chunk the test TEI file
    with app.app_context():
        source_dir = test_tei_file.parent
        chunk_output_dir = tmp_dir / "chunks"
        chunk_output_dir.mkdir()
        chunk_dir = get_chunk_dir(test_tei_file, source_dir, chunk_output_dir)
        ingest_tei_file(test_tei_file, chunk_dir)

    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestPassageRoute:
    """Tests for the passage route."""

    def test_passage_returns_404_for_nonexistent_urn(self, client):
        """Should return 404 for a URN that doesn't exist."""
        response = client.get("/urn:cts:greekLit:tlg9999.tlg999.fake-grc1:1")
        assert response.status_code == 404

    def test_passage_returns_404_for_invalid_urn(self, client):
        """Should return 404 for URN without colon."""
        response = client.get("/invalid-urn-no-colon")
        assert response.status_code == 404
