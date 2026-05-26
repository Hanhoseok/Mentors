"""5동 — 콘텐츠 (DB 토대 + 사용자 키워드).

owner: TODO
관련 FR: FR-05, FR-06, FR-08, UC-05, UC-06, UC-08
의존: core.{db, event_bus, read_services, auth, exceptions, user_context, contracts}

PR-2 시점 부팅 사이드이펙트:
  - ContentReader 등록 (read_services 레지스트리)
  - OnboardingCompletedEvent 핸들러 구독 (관심 키워드 자동 시딩)
  - ScrapAddedEvent 핸들러 구독 (PR-4 /scraps 발행 전까지는 dormant)

수집기/뉴스 라우터/스케줄러는 PR-3 이후 머지.
"""

from core.contracts import OnboardingCompletedEvent, ScrapAddedEvent
from core.event_bus import event_bus
from core.read_services import register_content_reader

from .handlers import on_onboarding_completed, on_scrap_added
from .read_service import ContentReadServiceImpl
from .router import router

register_content_reader(ContentReadServiceImpl())
event_bus.subscribe(ScrapAddedEvent, on_scrap_added)
event_bus.subscribe(OnboardingCompletedEvent, on_onboarding_completed)

__all__ = ["router"]
