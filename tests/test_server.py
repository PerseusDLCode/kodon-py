"""Tests for the server module."""

import pytest

from kodon_py.server import create_app
from kodon_py.ingestion import get_json_path, parse_tei_to_json


@pytest.fixture
def app(temp_dir, test_tei_file):
    """Create application for testing with ingested data."""
    app = create_app({"TESTING": True})

    # Parse and load the test TEI file as JSON
    with app.app_context():
        source_dir = test_tei_file.parent
        json_output_dir = temp_dir / "json"
        json_output_dir.mkdir()
        json_path = get_json_path(test_tei_file, source_dir, json_output_dir)
        parse_tei_to_json(test_tei_file, json_path)

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

    def test_passage_returns_400_for_invalid_urn(self, client):
        """Should return 400 for URN without colon."""
        response = client.get("/invalid-urn-no-colon")
        assert response.status_code == 400

    def test_passage_returns_200_for_valid_urn(self, client):
        """Should return 200 for a valid URN."""
        response = client.get("/urn:cts:greekLit:tlg0057.tlg111.verbatim-grc1:1")
        assert response.status_code == 200

    def test_passage_renders_template(self, client):
        """Should render the ReadingEnvironment template."""
        response = client.get("/urn:cts:greekLit:tlg0057.tlg111.verbatim-grc1:1")
        assert response.status_code == 200
        assert b"article" in response.data
