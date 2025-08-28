from fastapi.testclient import TestClient
from backend.main import app

def test_system_crud(monkeypatch):
    client = TestClient(app)

    # Ensure readiness unspecified; we won't call /readyz here

    # Create
    r = client.post("/systems/", json={"name": "core", "description": "Core system"})
    assert r.status_code in (201, 409)  # If test re-runs, may conflict
    if r.status_code == 201:
        sid = r.json()["id"]
    else:
        # List and find id
        r2 = client.get("/systems/")
        sid = next(x["id"] for x in r2.json() if x["name"] == "core")

    # Get
    r = client.get(f"/systems/{sid}")
    assert r.status_code == 200

    # Update
    r = client.patch(f"/systems/{sid}", json={"description": "Updated"})
    assert r.status_code == 200

    # Delete
    r = client.delete(f"/systems/{sid}")
    assert r.status_code == 204
