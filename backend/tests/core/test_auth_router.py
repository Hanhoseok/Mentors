import importlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import bcrypt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

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


class _FakeResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _extract_filters(whereclause) -> dict[str, object]:
    if whereclause is None:
        return {}

    if isinstance(whereclause, BooleanClauseList):
        clauses = list(whereclause.clauses)
    else:
        clauses = [whereclause]

    filters: dict[str, object] = {}
    for clause in clauses:
        if not isinstance(clause, BinaryExpression):
            continue
        filters[clause.left.name] = clause.right.value
    return filters


class _FakeSession:
    def __init__(self) -> None:
        self.users_by_id: dict[int, User] = {}
        self.users_by_email: dict[str, User] = {}
        self.identities_by_provider_user: dict[tuple[str, str], object] = {}
        self.local_credentials_by_user_id: dict[int, object] = {}
        self._pending: list[object] = []
        self._next_user_id = 1000
        self._next_identity_id = 2000
        self._next_local_credential_id = 3000

    def seed_user(self, user: User) -> None:
        assert user.id is not None
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user

    def seed_identity(self, *, user_id: int, provider: str, provider_user_id: str) -> None:
        identity = SimpleNamespace(
            id=self._next_identity_id,
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        self._next_identity_id += 1
        self.identities_by_provider_user[(provider, provider_user_id)] = identity

    def seed_local_credential(self, *, user_id: int, password_hash: str) -> None:
        credential = SimpleNamespace(
            id=self._next_local_credential_id,
            user_id=user_id,
            password_hash=password_hash,
        )
        self._next_local_credential_id += 1
        self.local_credentials_by_user_id[user_id] = credential

    async def execute(self, stmt, *_args, **_kwargs) -> _FakeResult:
        entity = stmt.column_descriptions[0].get("entity")
        entity_name = entity.__name__
        filters = _extract_filters(stmt.whereclause)

        if entity_name == "User":
            return _FakeResult(self.users_by_email.get(filters.get("email")))

        if entity_name == "AuthIdentity":
            if "provider_user_id" in filters:
                key = (filters.get("provider"), filters.get("provider_user_id"))
                return _FakeResult(self.identities_by_provider_user.get(key))

            for identity in self.identities_by_provider_user.values():
                if (
                    getattr(identity, "user_id", None) == filters.get("user_id")
                    and getattr(identity, "provider", None) == filters.get("provider")
                ):
                    return _FakeResult(identity)
            return _FakeResult(None)

        if entity_name == "LocalCredential":
            return _FakeResult(self.local_credentials_by_user_id.get(filters.get("user_id")))

        raise AssertionError(f"Unexpected entity lookup: {entity_name}")

    async def get(self, model, pk: int):
        if model.__name__ == "User":
            return self.users_by_id.get(pk)
        raise AssertionError(f"Unexpected get() model: {model.__name__}")

    def add(self, obj) -> None:
        self._pending.append(obj)

    async def flush(self) -> None:
        self._persist_pending()

    async def commit(self) -> None:
        self._persist_pending()

    async def refresh(self, _obj) -> None:
        return None

    def _persist_pending(self) -> None:
        while self._pending:
            obj = self._pending.pop(0)
            obj_type = obj.__class__.__name__

            if obj_type == "User":
                if getattr(obj, "id", None) is None:
                    obj.id = self._next_user_id
                    self._next_user_id += 1
                self.seed_user(obj)
                continue

            if obj_type == "AuthIdentity":
                if getattr(obj, "id", None) is None:
                    obj.id = self._next_identity_id
                    self._next_identity_id += 1
                self.identities_by_provider_user[(obj.provider, obj.provider_user_id)] = obj
                continue

            if obj_type == "LocalCredential":
                if getattr(obj, "id", None) is None:
                    obj.id = self._next_local_credential_id
                    self._next_local_credential_id += 1
                self.local_credentials_by_user_id[obj.user_id] = obj
                continue

            raise AssertionError(f"Unexpected pending object: {obj_type}")


class _FakeStateCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, *, ttl: int) -> None:  # noqa: ARG002
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


def _override_db(app: FastAPI, session: _FakeSession) -> None:
    async def _fake_get_db():
        yield session

    app.dependency_overrides[get_db] = _fake_get_db


def _noop_sync_pk_sequence(*_args, **_kwargs):
    async def _inner() -> None:
        return None

    return _inner()


def _hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def test_dev_token_route_creates_user_and_returns_valid_jwt(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    published_events: list[object] = []

    async def _fake_publish(event) -> None:
        published_events.append(event)

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    email = f"dev-token-{uuid4().hex[:12]}@local.test"

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/dev-token",
                json={"email": email, "nickname": "router-test"},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["created"] is True
            assert body["user"]["email"] == email
            assert decode_token(body["access_token"])["sub"] == str(body["user"]["id"])
            assert len(published_events) == 1

            me_response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {body['access_token']}"},
            )
            assert me_response.status_code == 200
            assert me_response.json()["email"] == email
    finally:
        app.dependency_overrides.clear()


def test_dev_token_route_reuses_existing_user_for_same_email(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=4242,
        email="dev-token-reuse@local.test",
        nickname="persisted-user",
        status="active",
    )
    session.seed_user(existing_user)

    async def _fake_publish(_event) -> None:
        raise AssertionError("existing users should not publish a signup event")

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            first = client.post(
                "/auth/dev-token",
                json={"email": existing_user.email, "nickname": "first-user"},
            )
            second = client.post(
                "/auth/dev-token",
                json={"email": existing_user.email, "nickname": "second-user"},
            )

            assert first.status_code == 200
            assert second.status_code == 200

            first_body = first.json()
            second_body = second.json()
            assert first_body["created"] is False
            assert second_body["created"] is False
            assert first_body["user"]["id"] == second_body["user"]["id"]
            assert second_body["user"]["email"] == existing_user.email
    finally:
        app.dependency_overrides.clear()


def test_dev_token_route_applies_requested_tier(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    applied_tiers: list[tuple[int, str]] = []
    invalidated_user_ids: list[int] = []

    async def _fake_publish(_event) -> None:
        return None

    async def _fake_apply_dev_tier(_db, *, user_id: int, tier) -> None:
        applied_tiers.append((user_id, tier.value))

    async def _fake_invalidate(user_id) -> None:
        invalidated_user_ids.append(int(user_id))

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)
    monkeypatch.setattr(auth_router, "_apply_dev_tier", _fake_apply_dev_tier)
    monkeypatch.setattr(auth_router.user_context, "invalidate", _fake_invalidate)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/dev-token",
                json={
                    "email": "dev-tier@local.test",
                    "nickname": "tier-tester",
                    "tier": "T2",
                },
            )

            assert response.status_code == 200
            body = response.json()
            assert body["tier"] == "T2"
            assert applied_tiers == [(body["user"]["id"], "T2")]
            assert invalidated_user_ids == [body["user"]["id"]]
    finally:
        app.dependency_overrides.clear()


def test_delete_me_route_marks_user_deleted_and_blocks_future_access(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=909,
        email="delete-me@example.com",
        nickname="delete-me",
        status="active",
    )
    session.seed_user(existing_user)
    session.seed_local_credential(user_id=909, password_hash=_hash_password("Mentors123!"))

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/auth/local/login",
                json={
                    "email": existing_user.email,
                    "password": "Mentors123!",
                },
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]

            delete_response = client.delete(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert delete_response.status_code == 204
            assert existing_user.status == "deleted"

            me_response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_response.status_code == 403
            assert me_response.json()["message"] == "Account deleted"
    finally:
        app.dependency_overrides.clear()


def test_local_signup_route_creates_local_user_and_returns_valid_jwt(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    published_events: list[object] = []

    async def _fake_publish(event) -> None:
        published_events.append(event)

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/local/signup",
                json={
                    "email": "local-user@example.com",
                    "password": "Mentors123!",
                    "password_confirm": "Mentors123!",
                },
            )

            assert response.status_code == 200
            body = response.json()
            user_id = int(decode_token(body["access_token"])["sub"])
            created_user = session.users_by_id[user_id]
            assert created_user.email == "local-user@example.com"
            assert session.local_credentials_by_user_id[user_id].password_hash != "Mentors123!"
            assert len(published_events) == 1
    finally:
        app.dependency_overrides.clear()


def test_local_signup_route_rejects_google_provider_collision(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=11,
        email="collision@example.com",
        nickname="google-user",
        status="active",
    )
    session.seed_user(existing_user)
    session.seed_identity(user_id=11, provider="google", provider_user_id="google-sub-1")

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/local/signup",
                json={
                    "email": existing_user.email,
                    "password": "Mentors123!",
                    "password_confirm": "Mentors123!",
                },
            )

            assert response.status_code == 409
            assert response.json()["code"] == "conflict"
            assert "Google" in response.json()["message"]
    finally:
        app.dependency_overrides.clear()


def test_local_login_route_returns_token_for_existing_local_account(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=77,
        email="existing-local@example.com",
        nickname="existing-local",
        status="active",
    )
    session.seed_user(existing_user)
    session.seed_local_credential(user_id=77, password_hash=_hash_password("Mentors123!"))

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/local/login",
                json={
                    "email": existing_user.email,
                    "password": "Mentors123!",
                },
            )

            assert response.status_code == 200
            assert decode_token(response.json()["access_token"])["sub"] == str(existing_user.id)
    finally:
        app.dependency_overrides.clear()


def test_local_login_route_rejects_google_only_account(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=88,
        email="google-only@example.com",
        nickname="google-only",
        status="active",
    )
    session.seed_user(existing_user)
    session.seed_identity(user_id=88, provider="google", provider_user_id="google-only-sub")

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/local/login",
                json={
                    "email": existing_user.email,
                    "password": "Mentors123!",
                },
            )

            assert response.status_code == 409
            assert response.json()["code"] == "conflict"
            assert "Google" in response.json()["message"]
    finally:
        app.dependency_overrides.clear()


def test_google_callback_redirects_to_app_with_token(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    cache = _FakeStateCache()
    cache.values["state:test-state"] = json.dumps({"return_to": "mentors://auth"})

    async def _fake_exchange_code(_code: str):
        return auth_router.GoogleUserInfo(
            sub="google-sub-redirect",
            email="redirect@example.com",
            name="redirect-user",
        )

    async def _fake_publish(_event) -> None:
        return None

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router, "_state_cache", cache)
    monkeypatch.setattr(auth_router, "exchange_code", _fake_exchange_code)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/google/callback",
                params={"code": "oauth-code", "state": "test-state"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            location = response.headers["location"]
            parsed = urlparse(location)
            assert parsed.scheme == "mentors"
            assert parsed.netloc == "auth"
            query = parse_qs(parsed.query)
            assert "token" in query
            assert query["is_new"] == ["1"]
    finally:
        app.dependency_overrides.clear()


def test_google_callback_redirects_provider_conflict_to_app(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=90,
        email="local-owner@example.com",
        nickname="local-owner",
        status="active",
    )
    session.seed_user(existing_user)
    session.seed_local_credential(user_id=90, password_hash=_hash_password("Mentors123!"))

    cache = _FakeStateCache()
    cache.values["state:test-state"] = json.dumps({"return_to": "mentors://auth"})

    async def _fake_exchange_code(_code: str):
        return auth_router.GoogleUserInfo(
            sub="other-google-sub",
            email=existing_user.email,
            name="google-collision",
        )

    async def _fake_publish(_event) -> None:
        return None

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router, "_state_cache", cache)
    monkeypatch.setattr(auth_router, "exchange_code", _fake_exchange_code)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/google/callback",
                params={"code": "oauth-code", "state": "test-state"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            query = parse_qs(urlparse(response.headers["location"]).query)
            assert "error" in query
            assert "로컬" in query["error"][0]
    finally:
        app.dependency_overrides.clear()


def test_google_callback_attaches_identity_to_existing_email_only_user(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    session = _FakeSession()
    existing_user = User(
        id=91,
        email="email-only@example.com",
        nickname="email-only",
        status="active",
    )
    session.seed_user(existing_user)

    published_events: list[object] = []
    cache = _FakeStateCache()
    cache.values["state:test-state"] = json.dumps({"return_to": "mentors://auth"})

    async def _fake_exchange_code(_code: str):
        return auth_router.GoogleUserInfo(
            sub="attached-google-sub",
            email=existing_user.email,
            name="google-attached-user",
        )

    async def _fake_publish(event) -> None:
        published_events.append(event)

    monkeypatch.setattr(auth_router, "_sync_pk_sequence", _noop_sync_pk_sequence)
    monkeypatch.setattr(auth_router, "_state_cache", cache)
    monkeypatch.setattr(auth_router, "exchange_code", _fake_exchange_code)
    monkeypatch.setattr(auth_router.event_bus, "publish", _fake_publish)

    app = _build_app()
    _override_db(app, session)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/google/callback",
                params={"code": "oauth-code", "state": "test-state"},
                follow_redirects=False,
            )

            assert response.status_code == 302
            query = parse_qs(urlparse(response.headers["location"]).query)
            assert query["is_new"] == ["0"]
            assert decode_token(query["token"][0])["sub"] == str(existing_user.id)
            assert session.users_by_email[existing_user.email].id == existing_user.id
            assert (
                session.identities_by_provider_user[("google", "attached-google-sub")].user_id
                == existing_user.id
            )
            assert published_events == []
    finally:
        app.dependency_overrides.clear()


def test_dev_token_route_is_disabled_outside_dev(monkeypatch) -> None:
    auth_router = importlib.import_module("core.auth.router")
    monkeypatch.setattr(auth_router.settings, "env", "prod")

    with TestClient(_build_app()) as client:
        response = client.post("/auth/dev-token", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
