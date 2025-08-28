"""add classification and glossary link tables

Revision ID: 0007_classification_and_glossary_links
Revises: 0006_visibility_columns
Create Date: 2025-08-15

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_classification_and_glossary_links"
down_revision = "0006_visibility_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "column_classification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("column_id", sa.Integer(), sa.ForeignKey("column.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detector", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_example", sa.Text(), nullable=True),
    )
    op.create_index("ix_cc_column", "column_classification", ["column_id"]) 

    op.create_table(
        "asset_term_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.Integer(), sa.ForeignKey("glossary_term.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_atl_asset", "asset_term_link", ["asset_id"]) 
    op.create_index("ix_atl_term", "asset_term_link", ["term_id"]) 

    op.create_table(
        "column_term_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("column_id", sa.Integer(), sa.ForeignKey("column.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.Integer(), sa.ForeignKey("glossary_term.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_ctl_column", "column_term_link", ["column_id"]) 
    op.create_index("ix_ctl_term", "column_term_link", ["term_id"]) 


def downgrade() -> None:
    op.drop_table("column_term_link")
    op.drop_table("asset_term_link")
    op.drop_table("column_classification")
