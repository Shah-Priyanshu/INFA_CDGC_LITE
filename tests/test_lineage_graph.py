from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models import System, Asset, LineageEdge


def test_lineage_graph_returns_edges(client: TestClient, db_session: Session):
    # Arrange: create simple lineage between two assets
    sys = db_session.query(System).filter_by(name="graph_sys").first()
    if not sys:
        sys = System(name="graph_sys")
        db_session.add(sys)
        db_session.commit()
        db_session.refresh(sys)

    a1 = Asset(system_id=sys.id, name="a1")
    a2 = Asset(system_id=sys.id, name="a2")
    db_session.add_all([a1, a2])
    db_session.commit()

    edge = LineageEdge(src_asset_id=a1.id, dst_asset_id=a2.id, confidence=99, predicate="test")
    db_session.add(edge)
    db_session.commit()

    # Act
    r = client.get("/lineage/graph")
    assert r.status_code == 200
    body = r.json()
    assert set(body["nodes"]) >= {a1.id, a2.id}
    assert (a1.id, a2.id) in [tuple(e) for e in body["edges"]]
