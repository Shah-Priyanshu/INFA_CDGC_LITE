"""add idempotency_key to scan_job

Revision ID: 0004_scan_job_idempotency
Revises: 0003_column_fts
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_scan_job_idempotency"
down_revision = "0003_column_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan_job", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index("ix_scan_job_source_idem", "scan_job", ["source", "idempotency_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_job_source_idem", table_name="scan_job")
    op.drop_column("scan_job", "idempotency_key")
