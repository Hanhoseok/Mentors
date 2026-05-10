"""동 간 도메인 read의 Protocol 정의 (§4.16, ADR-014).

이 Protocol을 구현하는 클래스는 features/<동>/read_service.py에 두고,
features/<동>/__init__.py에서 register_*() 호출로 코어에 등록한다.
"""

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from core.contracts import NewsId, Tier, UserId


class NewsRef(BaseModel):
    id: NewsId
    title: str
    url: str
    published_at: datetime


class ContentReader(Protocol):
    """콘텐츠 동이 구현. 다른 동은 `from core.read_services import content_reader` 사용."""

    async def get_today_news_for_user(self, user_id: UserId, top_k: int = 5) -> list[NewsRef]: ...

    async def get_news_by_id(self, news_id: NewsId) -> NewsRef | None: ...


class GrowthReader(Protocol):
    """성장 동이 구현 — 향후 확장 예시 (v2)."""

    async def get_tier_distribution(self) -> dict[Tier, int]: ...


__all__ = ["ContentReader", "GrowthReader", "NewsRef"]
