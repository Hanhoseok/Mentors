"""콘텐츠 동 이벤트 핸들러 (AGENTS.md §5.4).

핸들러는 **반드시 멱등**이어야 한다. event_id를 처리 기록에 UNIQUE로 저장해
중복 처리 방지 — 현재는 in-memory dedup으로 단순화 (정식 구현 시
core.cache 또는 별도 processed_events 테이블 사용 권장).
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from core.contracts import OnboardingCompletedEvent, ScrapAddedEvent
from core.db import SessionLocal
from core.user_context import user_context

from .keyword_service import seed_keywords_from_interests

logger = logging.getLogger("content.handlers")

# in-memory 멱등 가드 — process lifetime 동안만 유효. 다중 인스턴스 환경에선
# Redis-based dedup으로 교체 필수.
_MAX_REMEMBER = 10_000
_seen_event_ids: OrderedDict[str, None] = OrderedDict()


def _already_processed(event_id: str) -> bool:
    if event_id in _seen_event_ids:
        return True
    _seen_event_ids[event_id] = None
    if len(_seen_event_ids) > _MAX_REMEMBER:
        _seen_event_ids.popitem(last=False)
    return False


async def on_scrap_added(event: ScrapAddedEvent) -> None:
    """다른 동(혹은 콘텐츠 동 자체 router)에서 발행한 ScrapAddedEvent 처리.

    현재는 통계 로깅만. 추후 추천 모델 fine-tuning 신호 등 확장 지점.
    """
    if _already_processed(event.event_id):
        return
    logger.info(
        "content.scrap_event_consumed",
        extra={
            "event_id": event.event_id,
            "user_id": int(event.user_id),
            "article_id": int(event.article_id),
        },
    )
    # TODO: 사용자 추천 모델 신호 업데이트, 인기 기사 카운터 등


async def on_onboarding_completed(event: OnboardingCompletedEvent) -> None:
    """신규 사용자가 온보딩을 완료하면 관심 키워드 초기 시딩.

    1. user_context.get_interests(user_id)로 onboarding 응답의 interest 태그를 조회
       — 자기 동에서 features.onboarding을 직접 import하지 않기 위해 core 경유 (ADR-002)
    2. 각 태그를 (글로벌) MasterKeyword에 get-or-create
    3. (user_id, master_keyword_id)를 content_user_keywords에 INSERT (UNIQUE로 멱등)

    멱등성: 같은 이벤트가 두 번 들어와도 UNIQUE 제약 + add_user_keyword의
    pre-check로 중복 행을 만들지 않는다. in-memory event_id 가드는 보조 장치.
    """
    if _already_processed(event.event_id):
        return
    user_id = int(event.user_id)
    try:
        interests = await user_context.get_interests(event.user_id)
    except Exception:
        logger.exception(
            "content.onboarding_interests_load_failed",
            extra={"event_id": event.event_id, "user_id": user_id},
        )
        return

    if not interests:
        logger.info(
            "content.onboarding_completed_no_interests",
            extra={"event_id": event.event_id, "user_id": user_id},
        )
        return

    async with SessionLocal() as db:
        added = await seed_keywords_from_interests(
            db, user_id=user_id, interests=interests
        )
    logger.info(
        "content.user_keywords_seeded",
        extra={
            "event_id": event.event_id,
            "user_id": user_id,
            "interest_count": len(interests),
            "added": added,
        },
    )


__all__ = ["on_onboarding_completed", "on_scrap_added"]
