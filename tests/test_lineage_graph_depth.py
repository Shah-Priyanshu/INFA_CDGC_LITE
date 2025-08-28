from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models import System, Asset, LineageEdge


def test_lineage_graph_depth(client: TestClient, db_session: Session):
    # Build a small graph: a -> b -> c, and b -> d
    sys = db_session.query(System).filter_by(name="lg_sys").first() or System(name="lg_sys")
    if not getattr(sys, "id", None):
        db_session.add(sys)
        db_session.commit()
        db_session.refresh(sys)

    a = Asset(system_id=sys.id, name="a")
    b = Asset(system_id=sys.id, name="b")
    c = Asset(system_id=sys.id, name="c")
    d = Asset(system_id=sys.id, name="d")
    db_session.add_all([a, b, c, d])
    db_session.commit()

    e1 = LineageEdge(src_asset_id=a.id, dst_asset_id=b.id, confidence=100)
    e2 = LineageEdge(src_asset_id=b.id, dst_asset_id=c.id, confidence=100)
    e3 = LineageEdge(src_asset_id=b.id, dst_asset_id=d.id, confidence=100)
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    # Depth 0 (should include just the node itself)
    r = client.get(f"/lineage/graph?asset_id={a.id}&depth=0")
    assert r.status_code == 200
    g = r.json()
    assert g["nodes"] == [a.id]
    assert g["edges"] == []

    # Depth 1 (neighbors)
    r = client.get(f"/lineage/graph?asset_id={a.id}&depth=1")
    assert r.status_code == 200
    g = r.json()
    assert set(g["nodes"]) == {a.id, b.id}
    assert (a.id, b.id) in [tuple(e) for e in g["edges"]]

    # Depth 2 from a should include c through b
    r = client.get(f"/lineage/graph?asset_id={a.id}&depth=2")
    assert r.status_code == 200
    g = r.json()
    assert set(g["nodes"]) >= {a.id, b.id, c.id}
    assert (b.id, c.id) in [tuple(e) for e in g["edges"]]

    # From b depth 1 should include b, a (incoming), c and d (outgoing)
    r = client.get(f"/lineage/graph?asset_id={b.id}&depth=1")
    assert r.status_code == 200
    g = r.json()
    assert set(g["nodes"]) == {a.id, b.id, c.id, d.id}
    edges = [tuple(e) for e in g["edges"]]
    assert (a.id, b.id) in edges and (b.id, c.id) in edges and (b.id, d.id) in edges
