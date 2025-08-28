"""column fts

Revision ID: 0003_column_fts
Revises: 0002_more_tables
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_column_fts"
down_revision = "0002_more_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE "column"
        ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (
          to_tsvector('simple', unaccent(coalesce(name,'') || ' ' || coalesce(description,'')))
        ) STORED;
        CREATE INDEX IF NOT EXISTS idx_column_search_vector ON "column" USING GIN (search_vector);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_column_search_vector;")
    op.execute("ALTER TABLE \"column\" DROP COLUMN IF EXISTS search_vector;")
