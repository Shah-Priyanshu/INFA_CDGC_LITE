from __future__ import annotations

from sqlalchemy.orm import Session
import os

from workers.app import run_scan
from backend.models import System, Asset, ColumnModel


def test_worker_scan_upserts(db_session: Session):
    # Use snowflake connector stub via run_scan task; this runs inline
    # Ensure worker connects to the same SQLite DB used by tests
    if db_session.bind and db_session.bind.url:
        os.environ["DATABASE_URL"] = str(db_session.bind.url)
    result = run_scan.apply(args=("snowflake", None)).get()
    assert result["source"] == "snowflake"

    # Verify system upsert
    sys = db_session.query(System).filter(System.name == "snowflake").first()
    assert sys is not None

    # Verify asset
    asset = db_session.query(Asset).filter(Asset.name == "db.schema.table").first()
    assert asset is not None
    assert asset.system_id == sys.id

    # Verify column and column_names cache
    col = db_session.query(ColumnModel).filter(ColumnModel.asset_id == asset.id, ColumnModel.name == "id").first()
    assert col is not None
    db_session.refresh(asset)
    assert asset.column_names is not None and "id" in asset.column_names.split(",")
