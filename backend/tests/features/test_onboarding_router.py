import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.exceptions import register_exception_handlers


def _fake_user() -> User:
    return User(id=1, email="user@example.com", nickname="tester", status="active")


def _build_app() -> FastAPI:
    from features.onboarding.router import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


def test_onboarding_profile_route_requires_auth() -> None:
    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/onboarding/profile",
            json={
                "experience_level": "beginner",
                "interests": ["value"],
                "risk_profile": "steady",
                "learning_goal": "build-habit",
                "preferred_style": "gentle",
            },
        )

    assert response.status_code == 401


def test_onboarding_select_mentor_route_requires_auth() -> None:
    with TestClient(_build_app()) as client:
        response = client.post("/api/onboarding/select-mentor", json={"mentor_id": 1})

    assert response.status_code == 401


def test_onboarding_status_returns_service_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    onboarding_router = importlib.import_module("features.onboarding.router")

    async def fake_status(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "onboarded": True,
            "tier": "T1",
            "selected_mentor": {
                "id": 1,
                "slug": "warren-buffett",
                "name": "Warren Buffett",
            },
            "completed_at": "2026-05-13T00:00:00Z",
        }

    app = _build_app()
    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr(onboarding_router, "get_onboarding_status", fake_status)

    try:
        with TestClient(app) as client:
            response = client.get("/api/onboarding/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["onboarded"] is True
    assert response.json()["selected_mentor"]["slug"] == "warren-buffett"


def test_onboarding_profile_route_returns_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    onboarding_router = importlib.import_module("features.onboarding.router")

    async def fake_save_profile(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "profile": {
                "experience_level": "beginner",
                "interests": ["value"],
                "risk_profile": "steady",
                "learning_goal": "build-habit",
                "preferred_style": "gentle",
            },
            "recommended_mentors": [
                {
                    "id": 1,
                    "slug": "warren-buffett",
                    "name": "Warren Buffett",
                    "title": "Value Investing Mentor",
                    "summary": "Long-term value lens",
                    "reason": "Matches a steady beginner profile.",
                }
            ],
        }

    app = _build_app()
    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr(onboarding_router, "save_onboarding_profile", fake_save_profile)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/onboarding/profile",
                json={
                    "experience_level": "beginner",
                    "interests": ["value"],
                    "risk_profile": "steady",
                    "learning_goal": "build-habit",
                    "preferred_style": "gentle",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["recommended_mentors"][0]["name"] == "Warren Buffett"


def test_onboarding_select_mentor_route_returns_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    onboarding_router = importlib.import_module("features.onboarding.router")

    async def fake_select_mentor(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "onboarded": True,
            "tier": "T1",
            "selected_mentor": {
                "id": 1,
                "slug": "warren-buffett",
                "name": "Warren Buffett",
            },
            "completed_at": "2026-05-13T00:00:00Z",
        }

    app = _build_app()
    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr(onboarding_router, "select_onboarding_mentor", fake_select_mentor)

    try:
        with TestClient(app) as client:
            response = client.post("/api/onboarding/select-mentor", json={"mentor_id": 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["tier"] == "T1"
    assert response.json()["selected_mentor"]["name"] == "Warren Buffett"
