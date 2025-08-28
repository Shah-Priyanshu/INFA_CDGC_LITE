"""initial tables

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    op.create_table(
        "system",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "asset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("system.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("column_names", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "column",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    # FTS generated column and GIN index on asset
    op.execute(
        """
        ALTER TABLE asset
        ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (
          to_tsvector('simple', unaccent(coalesce(name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(column_names,'')))
        ) STORED;
        CREATE INDEX IF NOT EXISTS idx_asset_search_vector ON asset USING GIN (search_vector);
        """
    )


def downgrade() -> None:
    op.drop_index("idx_asset_search_vector", table_name="asset")
    op.drop_table("column")
    op.drop_table("asset")
    op.drop_table("system")
