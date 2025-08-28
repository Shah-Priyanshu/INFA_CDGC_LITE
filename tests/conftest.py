import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.db import Base, get_session
from backend.main import app


def pytest_configure():
    # Ensure auth is disabled and Celery runs eagerly in tests
    os.environ.setdefault("AUTH_DISABLED", "1")
    os.environ.setdefault("CELERY_EAGER", "1")

@pytest.fixture(scope="session")
def db_engine():
    # Use SQLite file to persist across tests in session
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+pysqlite:///{path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    # Ensure all connections are closed before removing the file (Windows lock avoidance)
    try:
        engine.dispose()
    except Exception:
        pass
    try:
        os.remove(path)
    except PermissionError:
        # As a fallback on Windows, ignore if file is still locked by an external handle
        pass


@pytest.fixture()
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_dependency(db_session):
    def _get_session_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = _get_session_override
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)
