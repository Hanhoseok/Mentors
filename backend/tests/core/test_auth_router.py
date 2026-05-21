import importlib
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.jwt import decode_token
from core.auth.models import User
from core.db import get_db
from core.exceptions import register_exception_handlers


def _build_app() -> FastAPI:
    from core.auth.router import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


def test_dev_token_route_creates_user_and_returns_valid_jwt() -> None:
    email = f"dev-token-{uuid4().hex[:12]}@local.test"

    with TestClient(_build_app()) as client:
        response = client.post(
            "/auth/dev-token",
            json={"email": email, "nickname": "router-test"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["created"] is True
        assert body["user"]["email"] == email
        assert decode_token(body["access_token"])["sub"] == str(body["user"]["id"])

        me_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == email


def test_dev_token_route_reuses_existing_user_for_same_email() -> None:
    email = f"dev-token-reuse-{uuid4().hex[:10]}@local.test"
    existing_user = User(id=4242, email=email, nickname="persisted-user", status="active")

    class _FakeResult:
        def scalar_one_or_none(self) -> User:
            return existing_user

    class _FakeSession:
        async def execute(self, *_args, **_kwargs) -> _FakeResult:
            return _FakeResult()

    async def _fake_get_db():
        yield _FakeSession()

    app = _build_app()
    app.dependency_overrides[get_db] = _fake_get_db

    try:
        with TestClient(app) as client:
            first = client.post(
                "/auth/dev-token",
                json={"email": email, "nickname": "first-user"},
            )
            second = client.post(
                "/auth/dev-token",
                json={"email": email, "nickname": "second-user"},
            )

            assert first.status_code == 200
            assert second.status_code == 200

            first_body = first.json()
            second_body = second.json()
            assert first_body["created"] is False
            assert second_body["created"] is False
            assert first_body["user"]["id"] == second_body["user"]["id"]
            assert second_body["user"]["email"] == email
    finally:
        app.dependency_overrides.clear()


def test_dev_token_route_is_disabled_outside_dev(
    monkeypatch,
) -> None:
    auth_router = importlib.import_module("core.auth.router")
    monkeypatch.setattr(auth_router.settings, "env", "prod")

    with TestClient(_build_app()) as client:
        response = client.post("/auth/dev-token", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
