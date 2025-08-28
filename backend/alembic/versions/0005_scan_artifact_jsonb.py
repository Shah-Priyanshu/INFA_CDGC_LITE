"""scan artifact payload to json/jsonb

Revision ID: 0005_scan_artifact_jsonb
Revises: 0004_scan_job_idempotency
Create Date: 2025-08-13

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_scan_artifact_jsonb"
down_revision = "0004_scan_job_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.alter_column(
            "scan_artifact",
            "payload",
            type_=sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            postgresql_using="payload::jsonb",
        )
    else:
        # SQLite and others will keep using JSON affinity via SQLAlchemy type without DB schema change
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.alter_column(
            "scan_artifact",
            "payload",
            type_=sa.Text(),
            postgresql_using="payload::text",
        )
    else:
        pass
