"""add visibility columns to system and asset

Revision ID: 0006_visibility_columns
Revises: 0005_scan_artifact_jsonb
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_visibility_columns"
down_revision = "0005_scan_artifact_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("system", sa.Column("visibility", sa.Text(), nullable=True))
    op.add_column("asset", sa.Column("visibility", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("asset", "visibility")
    op.drop_column("system", "visibility")
