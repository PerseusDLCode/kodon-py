"""init

Revision ID: 0001
Revises:
Create Date: 2026-01-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = ('default',)
depends_on: Union[str, Sequence[str], None] = None


# URN component columns shared by textparts, elements, and tokens
URN_COMPONENT_COLUMNS = [
    sa.Column("collection", sa.String(), nullable=True),
    sa.Column("work_component", sa.String(), nullable=True),
    sa.Column("passage_component", sa.String(), nullable=True),
    sa.Column("text_group", sa.String(), nullable=True),
    sa.Column("work", sa.String(), nullable=True),
    sa.Column("version", sa.String(), nullable=True),
    sa.Column("exemplar", sa.String(), nullable=True),
    sa.Column("citations", sa.JSON(), nullable=True),
    sa.Column("integer_citations", sa.JSON(), nullable=True),
]

# Subreference columns for elements and tokens only
SUBREFERENCE_COLUMNS = [
    sa.Column("token_strings", sa.JSON(), nullable=True),
    sa.Column("token_indexes", sa.JSON(), nullable=True),
]


def upgrade() -> None:
    """Create all tables."""
    # Documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("editionStmt", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("publicationStmt", sa.String(), nullable=True),
        sa.Column("respStmt", sa.String(), nullable=True),
        sa.Column("sourceDesc", sa.String(), nullable=False),
        sa.Column("textgroup", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("urn", sa.String(), nullable=False, unique=True),
    )

    # Textparts table
    op.create_table(
        'textparts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_urn', sa.String(), sa.ForeignKey('documents.urn'), nullable=False),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('n', sa.String(), nullable=True),
        sa.Column('subtype', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('urn', sa.String(), nullable=False, unique=True),
        # URN component columns
        sa.Column("collection", sa.String(), nullable=True),
        sa.Column("work_component", sa.String(), nullable=True),
        sa.Column("passage_component", sa.String(), nullable=True),
        sa.Column("text_group", sa.String(), nullable=True),
        sa.Column("work", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("exemplar", sa.String(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("integer_citations", sa.JSON(), nullable=True),
    )

    # Elements table
    op.create_table(
        'elements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('attributes', sa.JSON(), nullable=True),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('elements.id'), nullable=True),
        sa.Column('tagname', sa.String(), nullable=False),
        sa.Column('textpart_id', sa.Integer(), sa.ForeignKey('textparts.id'), nullable=False),
        sa.Column('urn', sa.String(), nullable=False),
        # URN component columns
        sa.Column("collection", sa.String(), nullable=True),
        sa.Column("work_component", sa.String(), nullable=True),
        sa.Column("passage_component", sa.String(), nullable=True),
        sa.Column("text_group", sa.String(), nullable=True),
        sa.Column("work", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("exemplar", sa.String(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("integer_citations", sa.JSON(), nullable=True),
        # Subreference columns
        sa.Column("token_strings", sa.JSON(), nullable=True),
        sa.Column("token_indexes", sa.JSON(), nullable=True),
    )

    # Tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('element_id', sa.Integer(), sa.ForeignKey('elements.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('textpart_id', sa.Integer(), sa.ForeignKey('textparts.id'), nullable=False),
        sa.Column('urn', sa.String(), nullable=False),
        sa.Column('whitespace', sa.Boolean(), nullable=False),
        # URN component columns
        sa.Column("collection", sa.String(), nullable=True),
        sa.Column("work_component", sa.String(), nullable=True),
        sa.Column("passage_component", sa.String(), nullable=True),
        sa.Column("text_group", sa.String(), nullable=True),
        sa.Column("work", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("exemplar", sa.String(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("integer_citations", sa.JSON(), nullable=True),
        # Subreference columns
        sa.Column("token_strings", sa.JSON(), nullable=True),
        sa.Column("token_indexes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('tokens')
    op.drop_table('elements')
    op.drop_table('textparts')
    op.drop_table('documents')
