"""5동 — 콘텐츠 (DB 토대 + 사용자 키워드 + 수집 파이프라인).

owner: TODO
관련 FR: FR-05, FR-06, FR-08, UC-05, UC-06, UC-08
의존: core.{db, event_bus, read_services, auth, exceptions, user_context, contracts,
         jobs, llm, vector_store}

부팅 사이드이펙트 (PR-2 + PR-3):
  - ContentReader 등록 (read_services 레지스트리)
  - OnboardingCompletedEvent 핸들러 구독 (관심 키워드 자동 시딩)
  - ScrapAddedEvent 핸들러 구독 (PR-4 /scraps 발행 전까지는 dormant)
  - jobs.py import → @interval 3개 (수집·AI 처리·RAG 인덱싱) 스케줄러 등록

뉴스 라우터(`/news`, `/news/search`, `/scraps`)는 PR-4에서 추가.
"""

from core.contracts import OnboardingCompletedEvent, ScrapAddedEvent
from core.event_bus import event_bus
from core.read_services import register_content_reader

from . import jobs as _jobs  # noqa: F401  (스케줄러 등록 트리거 — PR-3)
from .handlers import on_onboarding_completed, on_scrap_added
from .read_service import ContentReadServiceImpl
from .router import router

register_content_reader(ContentReadServiceImpl())
event_bus.subscribe(ScrapAddedEvent, on_scrap_added)
event_bus.subscribe(OnboardingCompletedEvent, on_onboarding_completed)

__all__ = ["router"]
