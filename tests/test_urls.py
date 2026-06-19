import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_shorten_url():
    response = client.post("/shorten", json={"original_url": "https://example.com"})
    assert response.status_code == 201
    data = response.json()
    assert "short_url" in data
    assert data["total_clicks"] == 0


def test_custom_alias():
    response = client.post(
        "/shorten",
        json={"original_url": "https://example.com", "custom_alias": "my-link"},
    )
    assert response.status_code == 201
    assert "my-link" in response.json()["short_url"]


def test_duplicate_alias_rejected():
    client.post("/shorten", json={"original_url": "https://a.com", "custom_alias": "dupe"})
    response = client.post("/shorten", json={"original_url": "https://b.com", "custom_alias": "dupe"})
    assert response.status_code == 409


def test_redirect():
    res = client.post("/shorten", json={"original_url": "https://example.com"})
    code = res.json()["short_code"]
    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"].rstrip("/") == "https://example.com"


def test_analytics_after_clicks():
    res = client.post("/shorten", json={"original_url": "https://example.com"})
    code = res.json()["short_code"]
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    analytics = client.get(f"/analytics/{code}")
    assert analytics.status_code == 200
    assert analytics.json()["total_clicks"] == 2


def test_deactivate_url():
    res = client.post("/shorten", json={"original_url": "https://example.com"})
    code = res.json()["short_code"]
    client.delete(f"/urls/{code}")
    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 404


def test_list_urls():
    client.post("/shorten", json={"original_url": "https://a.com"})
    client.post("/shorten", json={"original_url": "https://b.com"})
    res = client.get("/urls")
    assert res.status_code == 200
    assert len(res.json()) == 2
