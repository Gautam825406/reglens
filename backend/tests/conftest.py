import os

os.environ["DATABASE_URL"] = "sqlite:///./test_reglens.db"
os.environ["GROQ_API_KEY"] = ""
os.environ["JWT_SECRET"] = "reglens-test-secret"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest  # noqa: E402

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_reglens.db")


@pytest.fixture(scope="session", autouse=True)
def _fresh_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture(autouse=True)
def _reset_tables():
    """Clean slate per test: first registered user is Admin again."""
    from app import models  # noqa: F401
    from app.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def register(client, name, email, password="password123"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
