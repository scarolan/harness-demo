from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_landing_page_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Harness Demo App" in response.text


def test_landing_page_shows_version():
    response = client.get("/")
    assert "1.0.0" in response.text


def test_health_check_returns_healthy():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert "version" in data


def test_health_check_uptime_increases():
    r1 = client.get("/health").json()
    r2 = client.get("/health").json()
    assert r2["uptime_seconds"] >= r1["uptime_seconds"]


def test_api_info_returns_metadata():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Harness Demo App"
    assert data["version"] == "1.0.0"
    assert "environment" in data
    assert "commit_sha" in data
    assert "build_time" in data
    assert "hostname" in data
    assert "python_version" in data


def test_api_info_python_version_format():
    response = client.get("/api/info")
    data = response.json()
    parts = data["python_version"].split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_openapi_docs_available():
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Harness Demo App"
    assert "/health" in schema["paths"]
    assert "/api/info" in schema["paths"]


def test_nonexistent_route_returns_404():
    response = client.get("/nonexistent")
    assert response.status_code == 404
