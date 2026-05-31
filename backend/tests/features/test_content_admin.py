"""콘텐츠 동 admin 엔드포인트 테스트 — AI retry endpoint (PR-Ⅱ).

mentors 테스트 컨벤션 따름: TestClient + 의존성 override, 실제 DB/외부 호출 없음.
참고: tests/features/test_content_router.py 패턴.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.exceptions import register_exception_handlers


def _fake_user() -> User:
    return User(id=42, email="user@example.com", nickname="tester", status="active")


def _build_app() -> FastAPI:
    from features.content.router import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


def _build_authed_client() -> Iterator[TestClient]:
    app = _build_app()
    app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# unauth — admin 엔드포인트도 인증 가드
# ---------------------------------------------------------------------------


def test_retry_failed_requires_auth() -> None:
    """토큰 없이 호출 시 401."""
    app = _build_app()
    with TestClient(app) as client:
        r = client.post("/api/content/admin/retry-failed")
    assert r.status_code == 401, f"expected 401 unauthorized, got {r.status_code}"


# ---------------------------------------------------------------------------
# happy — failed 행이 reset되는 경로
# ---------------------------------------------------------------------------


def test_retry_failed_resets_and_returns_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """service.reset_failed_to_pending이 호출되고 응답이 그대로 통과."""
    router_mod = importlib.import_module("features.content.router")

    captured: dict[str, Any] = {}

    async def fake_reset(db: Any, *, limit: int) -> dict[str, Any]:
        captured["limit"] = limit
        return {
            "reset": 3,
            "sample": [
                {"id": 1, "title": "Sample A", "ai_error": "json_parse_failed"},
                {"id": 2, "title": "Sample B", "ai_error": "timeout"},
                {"id": 3, "title": "Sample C", "ai_error": "rate_limited"},
            ],
        }

    # service 모듈의 싱글톤 인스턴스 메서드를 monkeypatch
    monkeypatch.setattr(
        router_mod.content_service,
        "reset_failed_to_pending",
        fake_reset,
    )

    for client in _build_authed_client():
        r = client.post("/api/content/admin/retry-failed?limit=50")

    assert r.status_code == 200
    body = r.json()
    assert body["reset"] == 3
    assert len(body["sample"]) == 3
    assert body["sample"][0]["ai_error"] == "json_parse_failed"
    assert captured["limit"] == 50


def test_retry_failed_returns_zero_when_no_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """failed 행 0건이면 reset=0, sample=[] 반환."""
    router_mod = importlib.import_module("features.content.router")

    async def fake_reset(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"reset": 0, "sample": []}

    monkeypatch.setattr(
        router_mod.content_service,
        "reset_failed_to_pending",
        fake_reset,
    )

    for client in _build_authed_client():
        r = client.post("/api/content/admin/retry-failed")

    assert r.status_code == 200
    body = r.json()
    assert body["reset"] == 0
    assert body["sample"] == []


# ---------------------------------------------------------------------------
# 유효성 — limit param 경계값
# ---------------------------------------------------------------------------


def test_retry_failed_rejects_zero_limit() -> None:
    """limit=0 은 ge=1 제약 위반 — mentors가 FastAPI 422를 400으로 매핑."""
    for client in _build_authed_client():
        r = client.post("/api/content/admin/retry-failed?limit=0")
    assert r.status_code == 400


def test_retry_failed_rejects_excessive_limit() -> None:
    """limit>500 은 le=500 제약 위반 — mentors가 FastAPI 422를 400으로 매핑."""
    for client in _build_authed_client():
        r = client.post("/api/content/admin/retry-failed?limit=1000")
    assert r.status_code == 400
