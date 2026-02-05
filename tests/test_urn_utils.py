"""Tests for URN parsing utilities."""

import pytest

from kodon_py.urn_utils import (
    extract_subreference,
    parse_alphanumeric,
    parse_passage,
    parse_single_citation,
    parse_urn,
    parse_work_component,
)


class TestParseAlphanumeric:
    """Tests for parse_alphanumeric function."""

    def test_plain_integer(self):
        """Should parse plain integers."""
        assert parse_alphanumeric("1") == [1]
        assert parse_alphanumeric("327") == [327]
        assert parse_alphanumeric("42") == [42]

    def test_stephanus_notation(self):
        """Should parse Stephanus notation (letter suffix)."""
        assert parse_alphanumeric("327a") == [327, 1]
        assert parse_alphanumeric("327b") == [327, 2]
        assert parse_alphanumeric("327c") == [327, 3]
        assert parse_alphanumeric("327d") == [327, 4]
        assert parse_alphanumeric("327e") == [327, 5]

    def test_stephanus_case_insensitive(self):
        """Should handle uppercase Stephanus letters."""
        assert parse_alphanumeric("327A") == [327, 1]
        assert parse_alphanumeric("327B") == [327, 2]

    def test_invalid_input(self):
        """Should return empty list for invalid input."""
        assert parse_alphanumeric("abc") == []
        assert parse_alphanumeric("") == []


class TestParseSingleCitation:
    """Tests for parse_single_citation function."""

    def test_simple_citation(self):
        """Should parse simple dotted citations."""
        assert parse_single_citation("1") == [1]
        assert parse_single_citation("1.2") == [1, 2]
        assert parse_single_citation("1.2.3") == [1, 2, 3]

    def test_stephanus_citation(self):
        """Should parse citations with Stephanus notation."""
        assert parse_single_citation("327a") == [327, 1]
        assert parse_single_citation("1.327a") == [1, 327, 1]

    def test_deep_nesting(self):
        """Should handle deeply nested citations."""
        assert parse_single_citation("1.2.3.4.5") == [1, 2, 3, 4, 5]


class TestParsePassage:
    """Tests for parse_passage function."""

    def test_single_citation(self):
        """Should parse single citations."""
        citations, int_citations = parse_passage("1.2.3")
        assert citations == ["1.2.3"]
        assert int_citations == [[1, 2, 3]]

    def test_range_citation(self):
        """Should parse range citations."""
        citations, int_citations = parse_passage("1.1-1.2")
        assert citations == ["1.1", "1.2"]
        assert int_citations == [[1, 1], [1, 2]]

    def test_stephanus_range(self):
        """Should parse Stephanus ranges."""
        citations, int_citations = parse_passage("327a-327c")
        assert citations == ["327a", "327c"]
        assert int_citations == [[327, 1], [327, 3]]

    def test_empty_passage(self):
        """Should handle empty passage."""
        citations, int_citations = parse_passage("")
        assert citations == []
        assert int_citations == []


class TestParseWorkComponent:
    """Tests for parse_work_component function."""

    def test_standard_work_component(self):
        """Should parse standard work components."""
        text_group, work, version, exemplar = parse_work_component(
            "tlg0001.tlg001.test-grc1"
        )
        assert text_group == "tlg0001"
        assert work == "tlg001"
        assert version == "test-grc1"
        assert exemplar is None

    def test_with_exemplar(self):
        """Should parse work components with exemplar."""
        text_group, work, version, exemplar = parse_work_component(
            "tlg0001.tlg001.test-grc1.exemplar1"
        )
        assert text_group == "tlg0001"
        assert work == "tlg001"
        assert version == "test-grc1"
        assert exemplar == "exemplar1"

    def test_partial_work_component(self):
        """Should handle partial work components."""
        text_group, work, version, exemplar = parse_work_component("tlg0001")
        assert text_group == "tlg0001"
        assert work == ""
        assert version == ""
        assert exemplar is None


class TestExtractSubreference:
    """Tests for extract_subreference function."""

    def test_no_subreference(self):
        """Should return original passage when no subreference."""
        passage, token, idx = extract_subreference("1.2.3")
        assert passage == "1.2.3"
        assert token is None
        assert idx is None

    def test_word_subreference(self):
        """Should extract word subreferences."""
        passage, token, idx = extract_subreference("1.1@Rage[1]")
        assert passage == "1.1"
        assert token == "Rage"
        assert idx == 1

    def test_element_subreference(self):
        """Should extract element subreferences."""
        passage, token, idx = extract_subreference("1@<p>[0]")
        assert passage == "1"
        assert token == "<p>"
        assert idx == 0

    def test_higher_index(self):
        """Should handle higher occurrence indexes."""
        passage, token, idx = extract_subreference("1.1@word[5]")
        assert passage == "1.1"
        assert token == "word"
        assert idx == 5


class TestParseUrn:
    """Tests for parse_urn function."""

    def test_document_urn(self):
        """Should parse document URNs (no passage component)."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1")

        assert result.urn == "urn:cts:greekLit:tlg0001.tlg001.test-grc1"
        assert result.collection == "greekLit"
        assert result.work_component == "tlg0001.tlg001.test-grc1"
        assert result.text_group == "tlg0001"
        assert result.work == "tlg001"
        assert result.version == "test-grc1"
        assert result.exemplar is None
        assert result.passage_component is None
        assert result.citations == []
        assert result.integer_citations == []

    def test_textpart_urn(self):
        """Should parse textpart URNs."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.2.3")

        assert result.collection == "greekLit"
        assert result.work_component == "tlg0001.tlg001.test-grc1"
        assert result.passage_component == "1.2.3"
        assert result.citations == ["1.2.3"]
        assert result.integer_citations == [[1, 2, 3]]
        assert result.token_strings == []
        assert result.token_indexes == []

    def test_element_urn(self):
        """Should parse element URNs with subreference."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]")

        assert result.collection == "greekLit"
        assert result.passage_component == "1"
        assert result.citations == ["1"]
        assert result.integer_citations == [[1]]
        assert result.token_strings == ["<p>"]
        assert result.token_indexes == [0]

    def test_token_urn(self):
        """Should parse token URNs with subreference."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@word[1]")

        assert result.passage_component == "1"
        assert result.citations == ["1"]
        assert result.token_strings == ["word"]
        assert result.token_indexes == [1]

    def test_range_urn(self):
        """Should parse range URNs."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.1-1.2")

        assert result.passage_component == "1.1-1.2"
        assert result.citations == ["1.1", "1.2"]
        assert result.integer_citations == [[1, 1], [1, 2]]

    def test_range_with_subreferences(self):
        """Should parse range URNs with subreferences on both ends."""
        result = parse_urn(
            "urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.1@Rage[1]-1.2@Achilles[1]"
        )

        assert result.passage_component == "1.1-1.2"
        assert result.citations == ["1.1", "1.2"]
        assert result.integer_citations == [[1, 1], [1, 2]]
        assert result.token_strings == ["Rage", "Achilles"]
        assert result.token_indexes == [1, 1]

    def test_stephanus_urn(self):
        """Should parse URNs with Stephanus notation."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:327a")

        assert result.passage_component == "327a"
        assert result.citations == ["327a"]
        assert result.integer_citations == [[327, 1]]

    def test_stephanus_range_urn(self):
        """Should parse URNs with Stephanus range."""
        result = parse_urn("urn:cts:greekLit:tlg0001.tlg001.test-grc1:327a-327c")

        assert result.passage_component == "327a-327c"
        assert result.citations == ["327a", "327c"]
        assert result.integer_citations == [[327, 1], [327, 3]]

    def test_invalid_urn(self):
        """Should handle invalid URNs gracefully."""
        result = parse_urn("not-a-valid-urn")

        assert result.urn == "not-a-valid-urn"
        assert result.collection is None
        assert result.work_component is None

    def test_empty_urn(self):
        """Should handle empty URN."""
        result = parse_urn("")

        assert result.urn == ""
        assert result.collection is None

    def test_with_exemplar(self):
        """Should parse URNs with exemplar in work component."""
        result = parse_urn(
            "urn:cts:greekLit:tlg0001.tlg001.test-grc1.exemplar1:1.2.3"
        )

        assert result.work_component == "tlg0001.tlg001.test-grc1.exemplar1"
        assert result.text_group == "tlg0001"
        assert result.work == "tlg001"
        assert result.version == "test-grc1"
        assert result.exemplar == "exemplar1"
        assert result.passage_component == "1.2.3"
