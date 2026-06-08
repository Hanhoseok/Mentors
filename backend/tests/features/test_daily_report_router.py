import importlib
from collections.abc import AsyncIterator
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.dependencies import get_current_user
from core.db import get_db
from core.exceptions import register_exception_handlers


def _build_app() -> FastAPI:
    from features.daily_report.router import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


class _FakeDb:
    def __init__(self, report: object | None) -> None:
        self._report = report

    async def scalar(self, _stmt: object) -> object | None:
        return self._report


def _fake_db_provider(report: object | None):
    async def _provider() -> AsyncIterator[_FakeDb]:
        yield _FakeDb(report)

    return _provider


def test_daily_report_detail_route_requires_auth() -> None:
    with TestClient(_build_app()) as client:
        response = client.get("/api/daily-report/1")

    assert response.status_code == 401


def test_daily_report_detail_route_returns_serialized_report() -> None:
    importlib.import_module("features.daily_report.router")
    report = SimpleNamespace(
        id=7,
        report_date=date(2026, 6, 5),
        mentor_strategy="value",
        tier="T2",
        status="ready",
        body="daily report body",
        highlights_json='[{"news_id": 1, "title": "headline"}]',
        user_id=1,
    )

    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = _fake_db_provider(report)

    try:
        with TestClient(app) as client:
            response = client.get("/api/daily-report/7")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": 7,
        "report_date": "2026-06-05",
        "mentor_strategy": "value",
        "tier": "T2",
        "status": "ready",
        "body": "daily report body",
        "highlights": [{"news_id": 1, "title": "headline"}],
    }
