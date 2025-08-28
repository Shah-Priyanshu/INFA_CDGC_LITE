from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import System, Asset, LineageEdge


def test_visibility_filters_systems_and_assets(client: TestClient, db_session: Session):
    # Create systems with different visibilities
    s_public = System(name="s_public")
    s_private = System(name="s_private", visibility="admins editors")
    db_session.add_all([s_public, s_private])
    db_session.commit()

    # Assets
    a1 = Asset(system_id=s_public.id, name="a1")
    a2 = Asset(system_id=s_private.id, name="a2", visibility="admins")
    db_session.add_all([a1, a2])
    db_session.commit()

    # With auth disabled (tests), all should be visible
    r = client.get("/systems/")
    assert r.status_code == 200
    names = {x["name"] for x in r.json()}
    assert {"s_public", "s_private"}.issubset(names)

    r = client.get("/assets/")
    assert r.status_code == 200
    anames = {x["name"] for x in r.json()}
    assert {"a1", "a2"}.issubset(anames)


def test_lineage_graph_ui_format(client: TestClient, db_session: Session):
    s = System(name="sys")
    db_session.add(s)
    db_session.commit()
    a = Asset(system_id=s.id, name="A")
    b = Asset(system_id=s.id, name="B")
    db_session.add_all([a, b])
    db_session.commit()
    db_session.add(LineageEdge(src_asset_id=a.id, dst_asset_id=b.id))
    db_session.commit()

    r = client.get(f"/lineage/graph?asset_id={a.id}&depth=1&format=ui")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("nodes"), list) and isinstance(body.get("edges"), list)
    node = next((n for n in body["nodes"] if n["id"] == a.id), None)
    assert node is not None
    assert node["name"] == "A"
    edge = next((e for e in body["edges"] if e["source"] == a.id and e["target"] == b.id), None)
    assert edge is not None
