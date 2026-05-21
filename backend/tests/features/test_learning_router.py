import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import Tier
from core.exceptions import register_exception_handlers


def _fake_user() -> User:
    return User(id=1, email="user@example.com", nickname="tester", status="active")


def _build_app() -> FastAPI:
    from features.learning.router import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


def test_learning_quiz_catalog_route_requires_auth() -> None:
    with TestClient(_build_app()) as client:
        response = client.get("/api/learning/me/quizzes")

    assert response.status_code == 401


def test_learning_quiz_catalog_route_returns_current_tier_quizzes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning_router = importlib.import_module("features.learning.router")

    class _FakeUserContext:
        async def get_tier(self, _user_id: int) -> Tier:
            return Tier.T1

    monkeypatch.setattr(learning_router, "user_context", _FakeUserContext(), raising=False)

    app = _build_app()
    app.dependency_overrides[get_current_user] = _fake_user

    try:
        with TestClient(app) as client:
            response = client.get("/api/learning/me/quizzes")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "T1"
    assert [item["concept_id"] for item in body["quizzes"]] == [101, 102, 103, 104, 105]
