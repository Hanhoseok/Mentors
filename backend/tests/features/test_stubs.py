"""6개 동 stub 라우터가 모두 등록됐는지 + 인증 가드 동작 확인."""

import pytest
from fastapi.testclient import TestClient

from main import app

PROTECTED_ROUTES = [
    "/api/onboarding/status",
    "/api/learning/sessions",
    "/api/growth/me/tier",
    "/api/debate/eligibility",
    "/api/content/news/today",
    "/api/daily-report/today",
]


@pytest.mark.parametrize("path", PROTECTED_ROUTES)
def test_route_requires_auth(path: str) -> None:
    with TestClient(app) as client:
        r = client.get(path)
    # 인증 토큰 없으면 401
    assert r.status_code == 401, f"{path} should be protected, got {r.status_code}"
    body = r.json()
    assert body["code"] == "unauthorized"
    assert "request_id" in body
