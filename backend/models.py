from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
except Exception:  # pragma: no cover
    PGJSONB = None  # type: ignore
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class System(Base, TimestampMixin):
    __tablename__ = "system"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Optional visibility controls: space/comma separated roles/groups allowed to view; NULL means public
    visibility: Mapped[str | None] = mapped_column(Text)

    assets: Mapped[list[Asset]] = relationship("Asset", back_populates="system")


class Asset(Base, TimestampMixin):
    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    column_names: Mapped[str | None] = mapped_column(Text)
    # Optional visibility controls
    visibility: Mapped[str | None] = mapped_column(Text)

    system: Mapped[System] = relationship("System", back_populates="assets")
    columns: Mapped[list[ColumnModel]] = relationship("ColumnModel", back_populates="asset")


class ColumnModel(Base, TimestampMixin):
    __tablename__ = "column"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship("Asset", back_populates="columns")


class LineageEdge(Base, TimestampMixin):
    __tablename__ = "lineage_edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    src_column: Mapped[str | None] = mapped_column(String(255))
    dst_asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    dst_column: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    predicate: Mapped[str | None] = mapped_column(Text)


class ScanArtifact(Base, TimestampMixin):
    __tablename__ = "scan_artifact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    # Use JSON for portability; Postgres will use JSONB via Alembic migration
    payload: Mapped[dict] = mapped_column(JSON().with_variant(PGJSONB, "postgresql") if PGJSONB else JSON, nullable=False)


class ScanJob(Base, TimestampMixin):
    __tablename__ = "scan_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GlossaryTerm(Base, TimestampMixin):
    __tablename__ = "glossary_term"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class ColumnClassification(Base, TimestampMixin):
    __tablename__ = "column_classification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("column.id", ondelete="CASCADE"), nullable=False)
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    matched_example: Mapped[str | None] = mapped_column(Text)


class AssetTermLink(Base, TimestampMixin):
    __tablename__ = "asset_term_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[int] = mapped_column(ForeignKey("glossary_term.id", ondelete="CASCADE"), nullable=False)


class ColumnTermLink(Base, TimestampMixin):
    __tablename__ = "column_term_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("column.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[int] = mapped_column(ForeignKey("glossary_term.id", ondelete="CASCADE"), nullable=False)
