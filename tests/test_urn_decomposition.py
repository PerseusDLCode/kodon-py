"""Integration tests for URN decomposition on save/update."""

import pytest

from kodon_py.database import Document, Element, Textpart, Token


class TestTextpartUrnDecomposition:
    """Tests for automatic URN decomposition on Textpart save."""

    def test_urn_components_populated_on_insert(self, db_session):
        """Should populate URN components when inserting a Textpart."""
        # First create a document
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        # Create a textpart
        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1.2.3",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.2.3",
        )
        db_session.add(textpart)
        db_session.commit()

        # Verify URN components were populated
        assert textpart.collection == "greekLit"
        assert textpart.work_component == "tlg0001.tlg001.test-grc1"
        assert textpart.passage_component == "1.2.3"
        assert textpart.text_group == "tlg0001"
        assert textpart.work == "tlg001"
        assert textpart.version == "test-grc1"
        assert textpart.exemplar is None
        assert textpart.citations == ["1.2.3"]
        assert textpart.integer_citations == [[1, 2, 3]]

    def test_urn_components_updated_on_update(self, db_session):
        """Should update URN components when updating a Textpart's URN."""
        # First create a document
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        # Create a textpart
        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(textpart)
        db_session.commit()

        # Update the URN
        textpart.urn = "urn:cts:greekLit:tlg0001.tlg001.test-grc1:2.3.4"
        db_session.commit()

        # Refresh from database
        db_session.refresh(textpart)

        # Verify URN components were updated
        assert textpart.passage_component == "2.3.4"
        assert textpart.citations == ["2.3.4"]
        assert textpart.integer_citations == [[2, 3, 4]]

    def test_range_citation_on_textpart(self, db_session):
        """Should handle range citations on Textpart."""
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1.1-1.2",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.1-1.2",
        )
        db_session.add(textpart)
        db_session.commit()

        assert textpart.passage_component == "1.1-1.2"
        assert textpart.citations == ["1.1", "1.2"]
        assert textpart.integer_citations == [[1, 1], [1, 2]]


class TestElementUrnDecomposition:
    """Tests for automatic URN decomposition on Element save."""

    def test_element_urn_with_subreference(self, db_session):
        """Should populate subreference fields for Element URNs."""
        # Create document and textpart first
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(textpart)
        db_session.commit()

        # Create element with subreference URN
        element = Element(
            textpart_id=textpart.id,
            idx=0,
            tagname="p",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]",
        )
        db_session.add(element)
        db_session.commit()

        # Verify URN components
        assert element.collection == "greekLit"
        assert element.passage_component == "1"
        assert element.citations == ["1"]
        assert element.integer_citations == [[1]]
        assert element.token_strings == ["<p>"]
        assert element.token_indexes == [0]

    def test_element_without_subreference(self, db_session):
        """Should handle Element URNs without subreference."""
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(textpart)
        db_session.commit()

        # Create element without subreference (unusual but possible)
        element = Element(
            textpart_id=textpart.id,
            idx=0,
            tagname="p",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(element)
        db_session.commit()

        assert element.passage_component == "1"
        assert element.token_strings is None
        assert element.token_indexes is None


class TestTokenUrnDecomposition:
    """Tests for automatic URN decomposition on Token save."""

    def test_token_urn_with_subreference(self, db_session):
        """Should populate subreference fields for Token URNs."""
        # Create document, textpart, and element
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(textpart)
        db_session.commit()

        element = Element(
            textpart_id=textpart.id,
            idx=0,
            tagname="p",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]",
        )
        db_session.add(element)
        db_session.commit()

        # Create token
        token = Token(
            element_id=element.id,
            textpart_id=textpart.id,
            position=0,
            text="Rage",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@Rage[1]",
            whitespace=True,
        )
        db_session.add(token)
        db_session.commit()

        # Verify URN components
        assert token.collection == "greekLit"
        assert token.work_component == "tlg0001.tlg001.test-grc1"
        assert token.passage_component == "1"
        assert token.citations == ["1"]
        assert token.integer_citations == [[1]]
        assert token.token_strings == ["Rage"]
        assert token.token_indexes == [1]

    def test_token_higher_occurrence_index(self, db_session):
        """Should handle tokens with higher occurrence indexes."""
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1",
        )
        db_session.add(textpart)
        db_session.commit()

        element = Element(
            textpart_id=textpart.id,
            idx=0,
            tagname="p",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]",
        )
        db_session.add(element)
        db_session.commit()

        # Create token with higher occurrence index (5th occurrence of "the")
        token = Token(
            element_id=element.id,
            textpart_id=textpart.id,
            position=10,
            text="the",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@the[5]",
            whitespace=True,
        )
        db_session.add(token)
        db_session.commit()

        assert token.token_strings == ["the"]
        assert token.token_indexes == [5]


class TestStephanusNotation:
    """Tests for Stephanus notation in URN decomposition."""

    def test_stephanus_single_citation(self, db_session):
        """Should handle Stephanus notation in single citations."""
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="327a",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:327a",
        )
        db_session.add(textpart)
        db_session.commit()

        assert textpart.passage_component == "327a"
        assert textpart.citations == ["327a"]
        assert textpart.integer_citations == [[327, 1]]

    def test_stephanus_range_citation(self, db_session):
        """Should handle Stephanus notation in range citations."""
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        db_session.add(doc)
        db_session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="327a-327c",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:327a-327c",
        )
        db_session.add(textpart)
        db_session.commit()

        assert textpart.passage_component == "327a-327c"
        assert textpart.citations == ["327a", "327c"]
        assert textpart.integer_citations == [[327, 1], [327, 3]]


class TestDataPersistence:
    """Tests to verify URN components are persisted to database."""

    def test_urn_components_persist_after_session_close(self, db_path):
        """Should persist URN components when session is closed and reopened."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import scoped_session, sessionmaker

        engine = create_engine(f"sqlite:///{db_path}")
        session_factory = sessionmaker(bind=engine)
        session = scoped_session(session_factory)

        # Create and save data
        doc = Document(
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            title="Test",
            editionStmt="",
            language="grc",
            publicationStmt="",
            respStmt="",
            sourceDesc="",
            textgroup="test",
        )
        session.add(doc)
        session.commit()

        textpart = Textpart(
            document_urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1",
            idx=0,
            n="1.2.3",
            urn="urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.2.3",
        )
        session.add(textpart)
        session.commit()
        textpart_id = textpart.id
        session.remove()

        # Open new session and verify
        new_session = scoped_session(session_factory)
        loaded_textpart = new_session.get(Textpart, textpart_id)

        assert loaded_textpart.collection == "greekLit"
        assert loaded_textpart.work_component == "tlg0001.tlg001.test-grc1"
        assert loaded_textpart.passage_component == "1.2.3"
        assert loaded_textpart.text_group == "tlg0001"
        assert loaded_textpart.work == "tlg001"
        assert loaded_textpart.version == "test-grc1"
        assert loaded_textpart.citations == ["1.2.3"]
        assert loaded_textpart.integer_citations == [[1, 2, 3]]

        new_session.remove()
