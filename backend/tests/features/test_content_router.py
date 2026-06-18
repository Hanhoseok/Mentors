"""콘텐츠 동 라우터 테스트 — auth 가드 + happy path (monkeypatched service).

mentors 테스트 컨벤션 따름: TestClient + 의존성 override, 실제 DB/외부 호출 없음.
참고: tests/features/test_growth_router.py 패턴.
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
# unauth — 9 엔드포인트 전부 인증 가드
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/content/news"),
        ("GET", "/api/content/news/search?q=test"),
        ("GET", "/api/content/news/1"),
        ("POST", "/api/content/scraps"),
        ("DELETE", "/api/content/scraps/1"),
        ("GET", "/api/content/scraps"),
        ("GET", "/api/content/keywords"),
        ("POST", "/api/content/keywords"),
        ("DELETE", "/api/content/keywords/1"),
    ],
)
def test_route_requires_auth(method: str, path: str) -> None:
    """인증 없이 호출 시 401."""
    app = _build_app()
    with TestClient(app) as client:
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            r = client.post(path, json={})
        else:
            r = client.delete(path)
    assert r.status_code == 401, f"{method} {path} should be protected, got {r.status_code}"


# ---------------------------------------------------------------------------
# happy: keywords CRUD
# ---------------------------------------------------------------------------


class _FakeMasterKeyword:
    def __init__(self, kw_id: int, keyword: str) -> None:
        self.id = kw_id
        self.keyword = keyword
        self.language = "ko"


class _FakeUserKeyword:
    def __init__(self, uk_id: int, master_id: int, keyword: str) -> None:
        self.id = uk_id
        self.master_keyword_id = master_id
        self.master_keyword = _FakeMasterKeyword(master_id, keyword)
        self.source = "manual"
        self.weight = 1
        from datetime import datetime, timezone
        self.created_at = datetime.now(timezone.utc)


def test_list_my_keywords_returns_user_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_user_keywords가 호출된 user_id로 필터링되는지."""
    router_mod = importlib.import_module("features.content.router")

    captured: dict[str, Any] = {}

    async def fake_list(db: Any, *, user_id: int) -> list[_FakeUserKeyword]:
        captured["user_id"] = user_id
        return [_FakeUserKeyword(1, 10, "NVIDIA"), _FakeUserKeyword(2, 11, "반도체")]

    monkeypatch.setattr(router_mod, "list_user_keywords", fake_list)

    for client in _build_authed_client():
        r = client.get("/api/content/keywords")

    assert r.status_code == 200
    assert captured["user_id"] == 42
    body = r.json()
    assert body["total"] == 2
    assert {item["keyword"] for item in body["items"]} == {"NVIDIA", "반도체"}


def test_add_keyword_conflict_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """이미 등록된 키워드면 409."""
    router_mod = importlib.import_module("features.content.router")

    async def fake_add(*_args: Any, **_kwargs: Any) -> None:
        return None  # service returns None for duplicates

    monkeypatch.setattr(router_mod, "add_user_keyword", fake_add)

    for client in _build_authed_client():
        r = client.post("/api/content/keywords", json={"keyword": "NVIDIA"})

    assert r.status_code == 409
    assert r.json()["code"] == "conflict"


def test_remove_keyword_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    router_mod = importlib.import_module("features.content.router")

    async def fake_remove(*_args: Any, **_kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(router_mod, "remove_user_keyword", fake_remove)

    for client in _build_authed_client():
        r = client.delete("/api/content/keywords/999")

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# domain: news detail는 is_visible 무관하게 반환 (검색이 hidden 기사도 노출하므로
# 상세 클릭 시 404가 나지 않도록 의도적으로 visibility 체크를 제거함 — router 참고)
# ---------------------------------------------------------------------------


class _FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeTable:
    """model_validate의 _from_orm_strategies가 data.__table__.columns를 순회하므로
    ORM처럼 보이도록 최소 컬럼 메타를 제공."""

    def __init__(self, names: list[str]) -> None:
        self.columns = [_FakeColumn(n) for n in names]


class _FakeArticle:
    """NewsArticleResponse.model_validate가 동작하도록 ORM-like attrs 제공."""

    _COLUMN_NAMES = [
        "id", "title_original", "title_translated", "summary_ko", "content",
        "content_translated", "original_url", "source_name", "image_url",
        "language", "published_at", "reliability_score", "reliability_level",
        "composite_score", "strategies", "ai_sentiment", "ai_investment_relevance",
        "ai_keywords", "ai_processing_status", "is_visible",
    ]
    __table__ = _FakeTable(_COLUMN_NAMES)

    def __init__(self, *, article_id: int, is_visible: bool) -> None:
        from datetime import datetime, timezone
        self.id = article_id
        self.title_original = "Test"
        self.title_translated = None
        self.summary_ko = None
        self.content = None
        self.content_translated = None
        self.original_url = "https://example.com/x"
        self.source_name = "Test"
        self.image_url = None
        self.language = "en"
        self.published_at = datetime.now(timezone.utc)
        self.reliability_score = 80
        self.reliability_level = "high"
        self.composite_score = 80.0
        self.strategies = ""
        self.ai_sentiment = None
        self.ai_investment_relevance = None
        self.ai_keywords = None
        self.ai_processing_status = "completed"
        self.is_visible = is_visible


def test_get_news_returns_article_regardless_of_visibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """is_visible=False 기사라도 행이 존재하면 200으로 반환한다."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async def fake_scalar(self: AsyncSession, *_args: Any, **_kwargs: Any) -> Any:
        return _FakeArticle(article_id=99, is_visible=False)

    monkeypatch.setattr(AsyncSession, "scalar", fake_scalar)

    for client in _build_authed_client():
        r = client.get("/api/content/news/99")

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 99
    assert body["display_title"] == "Test"


def test_get_news_missing_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """행이 없으면 404."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async def fake_scalar(self: AsyncSession, *_args: Any, **_kwargs: Any) -> Any:
        return None

    monkeypatch.setattr(AsyncSession, "scalar", fake_scalar)

    for client in _build_authed_client():
        r = client.get("/api/content/news/99")

    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
