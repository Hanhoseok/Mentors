"""헬스 엔드포인트 + 미들웨어 스모크."""

from fastapi.testclient import TestClient

from main import app


def test_health() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_live() -> None:
    with TestClient(app) as client:
        r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_request_id_echoed() -> None:
    with TestClient(app) as client:
        r = client.get("/health", headers={"X-Request-ID": "test-rid-xyz"})
    assert r.headers.get("X-Request-ID") == "test-rid-xyz"


def test_request_id_auto_generated() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    rid = r.headers.get("X-Request-ID", "")
    assert rid.startswith("req_")


def test_dev_cors_allows_expo_web_origin() -> None:
    with TestClient(app) as client:
        r = client.options(
            "/auth/dev-token",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8081"
