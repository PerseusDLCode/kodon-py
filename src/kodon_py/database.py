from flask_alembic import Alembic
from flask_sqlalchemy_lite import SQLAlchemy

from typing import Any, List, Optional

from sqlalchemy import ForeignKey, event
from sqlalchemy.types import JSON
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from kodon_py.urn_utils import parse_urn


class Model(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSON,
        list[str]: JSON,
        list[list[int]]: JSON,
        list[int]: JSON,
    }


db = SQLAlchemy()

alembic = Alembic(metadatas=Model.metadata)


class Document(Model):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    editionStmt: Mapped[Optional[str]]
    language: Mapped[str]
    publicationStmt: Mapped[Optional[str]]
    respStmt: Mapped[Optional[str]]
    sourceDesc: Mapped[str]
    textgroup: Mapped[str]
    textparts: Mapped[List["Textpart"]] = relationship(back_populates="document")
    title: Mapped[str]
    urn: Mapped[str] = mapped_column(unique=True)


class Element(Model):
    __tablename__ = "elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    attributes: Mapped[Optional[dict[str, Any]]]
    idx: Mapped[int]
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("elements.id"))
    tagname: Mapped[str]
    textpart: Mapped["Textpart"] = relationship(back_populates="elements")
    textpart_id: Mapped[int] = mapped_column(ForeignKey("textparts.id"))
    tokens: Mapped[List["Token"]] = relationship(back_populates="element")
    urn: Mapped[str]

    # Self-referential relationship for parent/children
    parent: Mapped[Optional["Element"]] = relationship(
        back_populates="children",
        remote_side="Element.id",
    )
    children: Mapped[List["Element"]] = relationship(
        back_populates="parent",
    )

    # URN component fields
    collection: Mapped[Optional[str]]
    work_component: Mapped[Optional[str]]
    passage_component: Mapped[Optional[str]]
    text_group: Mapped[Optional[str]]
    work: Mapped[Optional[str]]
    version: Mapped[Optional[str]]
    exemplar: Mapped[Optional[str]]
    citations: Mapped[Optional[list[str]]]
    integer_citations: Mapped[Optional[list[list[int]]]]

    # Subreference fields
    token_strings: Mapped[Optional[list[str]]]
    token_indexes: Mapped[Optional[list[int]]]


class Textpart(Model):
    __tablename__ = "textparts"

    id: Mapped[int] = mapped_column(primary_key=True)
    document: Mapped["Document"] = relationship(back_populates="textparts")
    document_urn: Mapped[str] = mapped_column(ForeignKey("documents.urn"))
    elements: Mapped[List["Element"]] = relationship(back_populates="textpart")
    idx: Mapped[int]
    location: Mapped[Optional[str]]
    n: Mapped[Optional[str]]
    subtype: Mapped[Optional[str]]
    tokens: Mapped[List["Token"]] = relationship(back_populates="textpart")
    type: Mapped[Optional[str]]
    urn: Mapped[str] = mapped_column(unique=True)

    # URN component fields
    collection: Mapped[Optional[str]]
    work_component: Mapped[Optional[str]]
    passage_component: Mapped[Optional[str]]
    text_group: Mapped[Optional[str]]
    work: Mapped[Optional[str]]
    version: Mapped[Optional[str]]
    exemplar: Mapped[Optional[str]]
    citations: Mapped[Optional[list[str]]]
    integer_citations: Mapped[Optional[list[list[int]]]]


class Token(Model):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    element: Mapped["Element"] = relationship(back_populates="tokens")
    element_id: Mapped[int] = mapped_column(ForeignKey("elements.id"))
    position: Mapped[int]
    text: Mapped[str]
    textpart: Mapped["Textpart"] = relationship(back_populates="tokens")
    textpart_id: Mapped[int] = mapped_column(ForeignKey("textparts.id"))
    urn: Mapped[str]
    whitespace: Mapped[bool]

    # URN component fields
    collection: Mapped[Optional[str]]
    work_component: Mapped[Optional[str]]
    passage_component: Mapped[Optional[str]]
    text_group: Mapped[Optional[str]]
    work: Mapped[Optional[str]]
    version: Mapped[Optional[str]]
    exemplar: Mapped[Optional[str]]
    citations: Mapped[Optional[list[str]]]
    integer_citations: Mapped[Optional[list[list[int]]]]

    # Subreference fields
    token_strings: Mapped[Optional[list[str]]]
    token_indexes: Mapped[Optional[list[int]]]


def populate_urn_components(mapper, connection, target):
    """Event listener to populate URN component fields before insert/update.

    This function parses the `urn` field and populates all decomposed
    URN component fields automatically.
    """
    if not hasattr(target, "urn") or not target.urn:
        return

    parsed = parse_urn(target.urn)

    target.collection = parsed.collection
    target.work_component = parsed.work_component
    target.passage_component = parsed.passage_component
    target.text_group = parsed.text_group
    target.work = parsed.work
    target.version = parsed.version
    target.exemplar = parsed.exemplar
    target.citations = parsed.citations if parsed.citations else None
    target.integer_citations = parsed.integer_citations if parsed.integer_citations else None

    # Only set subreference fields for Element and Token models
    if hasattr(target, "token_strings"):
        target.token_strings = parsed.token_strings if parsed.token_strings else None
        target.token_indexes = parsed.token_indexes if parsed.token_indexes else None


# Register event listeners for URN decomposition
event.listen(Textpart, "before_insert", populate_urn_components)
event.listen(Textpart, "before_update", populate_urn_components)
event.listen(Element, "before_insert", populate_urn_components)
event.listen(Element, "before_update", populate_urn_components)
event.listen(Token, "before_insert", populate_urn_components)
event.listen(Token, "before_update", populate_urn_components)


def run_migrations(app):
    """Run database migrations to head using alembic commands API."""
    with app.app_context():
        alembic.upgrade()
