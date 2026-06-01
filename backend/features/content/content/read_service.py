"""ContentReader 구현 (AGENTS.md §5.2, ADR-014).

다른 동(일일리포트, 학습)이 `from core.read_services import content_reader`로 호출.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select

from core.contracts import NewsId, UserId
from core.db import SessionLocal
from core.read_services import NewsRef
from core.user_context import user_context

from .models import ArticleKeyword, NewsArticle, UserKeyword

logger = logging.getLogger("content.read_service")

# 사용자 멘토 전략과 매칭되는 기사를 최근 N일에서 가져옴
_LOOKBACK_HOURS_TODAY = 36


class ContentReadServiceImpl:
    """ContentReader Protocol 구현."""

    async def get_today_news_for_user(
        self, user_id: UserId, top_k: int = 5
    ) -> list[NewsRef]:
        """오늘(±36h) 노출 가능 기사 우선순위:
          1. 사용자가 등록한 관심 키워드와 매칭되는 기사
          2. 멘토 전략 매칭 기사
          3. 일반 인기 (fallback)

        각 단계에서 중복 제거하며 top_k가 채워질 때까지 누적.
        """
        strategy = await self._resolve_user_strategy(user_id)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS_TODAY)

        async with SessionLocal() as session:
            base_stmt = (
                select(NewsArticle)
                .where(
                    NewsArticle.is_visible.is_(True),
                    NewsArticle.published_at >= cutoff,
                )
                .order_by(desc(NewsArticle.composite_score), desc(NewsArticle.published_at))
            )

            articles: list[NewsArticle] = []
            seen_ids: set[int] = set()

            # ---- 1) 사용자 관심 키워드 매칭 ----
            user_kw_stmt = (
                select(NewsArticle)
                .join(ArticleKeyword, ArticleKeyword.article_id == NewsArticle.id)
                .join(UserKeyword, UserKeyword.master_keyword_id == ArticleKeyword.master_keyword_id)
                .where(
                    UserKeyword.user_id == int(user_id),
                    NewsArticle.is_visible.is_(True),
                    NewsArticle.published_at >= cutoff,
                )
                .order_by(desc(NewsArticle.composite_score), desc(NewsArticle.published_at))
                .limit(top_k * 2)
            )
            result = await session.execute(user_kw_stmt)
            for a in result.scalars().all():
                if a.id in seen_ids:
                    continue
                articles.append(a)
                seen_ids.add(a.id)
                if len(articles) >= top_k:
                    return [self._to_ref(a) for a in articles[:top_k]]

            # ---- 2) 멘토 전략 매칭 ----
            if strategy is not None and len(articles) < top_k:
                stmt = base_stmt.where(NewsArticle.strategies.ilike(f"%{strategy}%")).limit(
                    top_k * 2
                )
                result = await session.execute(stmt)
                for a in result.scalars().all():
                    if a.id in seen_ids:
                        continue
                    articles.append(a)
                    seen_ids.add(a.id)
                    if len(articles) >= top_k:
                        break

            # ---- 3) 일반 인기 fallback ----
            if len(articles) < top_k:
                fallback_stmt = base_stmt.limit(top_k * 2)
                result = await session.execute(fallback_stmt)
                for a in result.scalars().all():
                    if a.id in seen_ids:
                        continue
                    articles.append(a)
                    seen_ids.add(a.id)
                    if len(articles) >= top_k:
                        break

            return [self._to_ref(a) for a in articles[:top_k]]

    async def get_news_by_id(self, news_id: NewsId) -> NewsRef | None:
        async with SessionLocal() as session:
            article = await session.scalar(
                select(NewsArticle).where(NewsArticle.id == int(news_id))
            )
            return self._to_ref(article) if article else None

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_user_strategy(user_id: UserId) -> str | None:
        """user_context에서 선택 멘토 → 멘토 전략으로 변환.

        멘토 모델(학습 동)에 대한 직접 의존을 피하려고 user_context를 거친다.
        user_context에 전략까지 노출돼 있지 않으면 None 반환 (호출자가 fallback).
        """
        try:
            ctx = await user_context.get_for_mentor_chat(user_id)
        except Exception:
            logger.warning("content.user_context_failed", extra={"user_id": int(user_id)})
            return None
        # user_context DTO에 strategy 필드가 있는지 확인. 없으면 None.
        strategy = getattr(ctx, "selected_mentor_strategy", None)
        if strategy is None:
            return None
        return str(strategy.value) if hasattr(strategy, "value") else str(strategy)

    @staticmethod
    def _to_ref(article: NewsArticle) -> NewsRef:
        return NewsRef(
            id=NewsId(article.id),
            title=article.title_translated or article.title_original,
            url=article.original_url,
            published_at=article.published_at or article.created_at,
        )


__all__ = ["ContentReadServiceImpl"]
