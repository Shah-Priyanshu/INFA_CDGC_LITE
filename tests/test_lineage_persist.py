from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models import System, Asset, LineageEdge


def test_lineage_sql_persist_creates_edge(client: TestClient, db_session: Session):
    # Arrange: make two assets with matching names to the SQL
    # Create or fetch system to avoid uniqueness conflicts when tests re-use the same DB file
    sys = db_session.query(System).filter_by(name="sys1").first()
    if not sys:
        sys = System(name="sys1")
        db_session.add(sys)
        db_session.commit()
        db_session.refresh(sys)

    a_src = Asset(system_id=sys.id, name="src")
    a_tgt = Asset(system_id=sys.id, name="tgt")
    db_session.add_all([a_src, a_tgt])
    db_session.commit()

    # Act: send SQL with persist=1; auth bypass in tests via env AUTH_DISABLED=1
    payload = {"sql": "create table tgt as select * from src"}
    r = client.post("/lineage/sql", params={"persist": 1}, json=payload)
    assert r.status_code == 200, r.text

    # Assert: lineage edge exists for our created assets (robust to pre-existing edges from other tests)
    edge = (
        db_session.query(LineageEdge)
        .filter(LineageEdge.src_asset_id == a_src.id, LineageEdge.dst_asset_id == a_tgt.id)
        .first()
    )
    assert edge is not None

    # Call again; should not duplicate
    r = client.post("/lineage/sql", params={"persist": 1}, json=payload)
    assert r.status_code == 200
    count = (
        db_session.query(LineageEdge)
        .filter(LineageEdge.src_asset_id == a_src.id, LineageEdge.dst_asset_id == a_tgt.id)
        .count()
    )
    assert count == 1
