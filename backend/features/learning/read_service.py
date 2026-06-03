"""LearningReader 구현 (AGENTS.md §5.2, ADR-014).

다른 동(일일 리포트)이 `from core.read_services import learning_reader`로 호출해
사용자의 현재 티어에서 '진도순으로 아직 안 푼 다음 커리큘럼 개념'을 받는다.

이 어댑터는 동 경계(읽기 DTO)만 담당하고, 진도 판정·개념 카탈로그는 학습 동
내부 모듈(quizzes·growth.catalog·concept_detector)이 소유한다. 개념을 ConceptRef로
변환해 ORM/퀴즈 모델을 경계 밖으로 누설하지 않는다.
"""

from __future__ import annotations

import logging

from core.contracts import ConceptId, Tier, UserId
from core.db import SessionLocal
from core.read_services import ConceptRef
from features.growth.catalog import list_concepts_for_tier

from .concept_detector import keywords_for_concept
from .quizzes import _load_progress_by_question_id

logger = logging.getLogger("learning.read_service")


class LearningReadServiceImpl:
    """LearningReader Protocol 구현."""

    async def get_today_concept(self, user_id: UserId, tier: Tier) -> ConceptRef | None:
        """현재 티어에서 진도순으로 아직 안 푼 다음 개념을 ConceptRef로 반환.

        '안 푼' 기준은 그 개념의 팔로우업 퀴즈를 아직 solved 하지 못한 것이다.
        전부 풀었으면 마지막 개념으로 복습을 유도한다(같은 티어 안에서 순환).
        """
        concepts = list_concepts_for_tier(tier)
        if not concepts:
            return None

        async with SessionLocal() as db:
            progress = await _load_progress_by_question_id(db, user_id, tier)
        solved_concept_ids = {p.concept_id for p in progress.values() if p.solved}

        target = next(
            (c for c in concepts if c.id not in solved_concept_ids),
            concepts[-1],
        )
        return ConceptRef(
            id=ConceptId(target.id),
            title=target.title,
            keywords=list(keywords_for_concept(target.id)),
        )


__all__ = ["LearningReadServiceImpl"]
