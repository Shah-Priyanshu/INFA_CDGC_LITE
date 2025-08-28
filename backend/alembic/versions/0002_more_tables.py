"""more tables

Revision ID: 0002_more_tables
Revises: 0001_initial
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_more_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lineage_edge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("src_asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("src_column", sa.String(length=255), nullable=True),
        sa.Column("dst_asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dst_column", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("predicate", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "scan_artifact",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "scan_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_scan_job_source_idem", "scan_job", ["source", "idempotency_key"], unique=False)

    op.create_table(
        "glossary_term",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_scan_job_source_idem", table_name="scan_job")
    op.drop_table("glossary_term")
    op.drop_table("scan_job")
    op.drop_table("scan_artifact")
    op.drop_table("lineage_edge")
