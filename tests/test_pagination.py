from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models import System, Asset


def test_systems_pagination(client: TestClient, db_session: Session):
    # Seed a few systems
    names = [f"sys_pg_{i}" for i in range(5)]
    for n in names:
        if not db_session.query(System).filter_by(name=n).first():
            db_session.add(System(name=n))
    db_session.commit()

    r = client.get("/systems/?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert len(body) <= 2

    r2 = client.get("/systems/?limit=2&offset=2")
    assert r2.status_code == 200


def test_jobs_pagination(client: TestClient):
    # Enqueue multiple jobs (eager)
    for i in range(5):
        r = client.post("/ingest/snowflake/scan", json={"idempotency_key": f"k{i}"})
        assert r.status_code == 202
    r = client.get("/ingest/jobs?limit=3&offset=0")
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) <= 3

    r = client.get("/ingest/jobs?limit=3&offset=3")
    assert r.status_code == 200
