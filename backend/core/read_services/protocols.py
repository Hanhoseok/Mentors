"""동 간 도메인 read의 Protocol 정의 (§4.16, ADR-014).

이 Protocol을 구현하는 클래스는 features/<동>/read_service.py에 두고,
features/<동>/__init__.py에서 register_*() 호출로 코어에 등록한다.
"""

from datetime import date, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from core.contracts import ConceptId, MentorStrategy, NewsId, ReportId, Tier, UserId


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
    """성장 동이 구현. 다른 동은 자기 동의 fallback 레이어를 거쳐 호출.

    학습 동의 경우 `features/learning/growth_dep.reader()`가 등록 여부를
    체크해 등록 안 됐을 때 NullGrowthReader(T1·빈 마스터리)를 돌려준다.
    그러므로 본 Protocol에 메서드를 추가할 때는 NullGrowthReader도 함께 갱신.
    """

    async def get_user_tier(self, user_id: UserId) -> Tier: ...

    async def get_mastered_concepts(
        self, user_id: UserId, strategy: MentorStrategy
    ) -> set[ConceptId]: ...

    async def get_tier_distribution(self) -> dict[Tier, int]: ...


class DailyReportRef(BaseModel):
    """일일 리포트 동이 다른 동에 노출하는 읽기 DTO (ADR-014).

    학습 동이 '그날 첫 진입'에서 멘토 페르소나 오프너 + 브리핑 카드를 렌더할 때
    필요한 만큼만 담는다. body는 마크다운, highlights는 [{news_id, title}].
    """

    id: ReportId
    report_date: date
    mentor_strategy: MentorStrategy
    tier: Tier
    status: str
    body: str | None
    highlights: list[dict[str, Any]]


class DailyReportReader(Protocol):
    """일일 리포트 동이 구현. 학습 동이 '그날 그 멘토 첫 진입'에서 호출해
    선택 멘토(전략)의 오늘 리포트를 get-or-create 한다 (없으면 lazy 생성)."""

    async def get_or_create_today_report(
        self, user_id: UserId, strategy: MentorStrategy
    ) -> DailyReportRef: ...


__all__ = [
    "ContentReader",
    "DailyReportReader",
    "DailyReportRef",
    "GrowthReader",
    "NewsRef",
]
