from fastapi.testclient import TestClient
from backend.main import app

def test_healthz():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_missing_env(monkeypatch):
    client = TestClient(app)
    # Ensure required envs are absent to trigger 503
    for k in ["DATABASE_URL", "OIDC_ISSUER", "OIDC_AUDIENCE", "SECRET_KEY"]:
        monkeypatch.delenv(k, raising=False)
    r = client.get("/readyz")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "not-ready"
    assert set(["DATABASE_URL", "OIDC_ISSUER", "OIDC_AUDIENCE", "SECRET_KEY"]) == set(data["missing"])  # noqa: E501
