"""콘텐츠 동 스케줄 작업 (AGENTS.md §5.7).

네 가지 주기 job:
  1. content_collect          — 10분마다 새 기사 수집·dedup·DB 저장
  2. content_ai_process       — 5분마다 pending 큐의 AI 처리
  3. content_rag_index        — 15분마다 RAG 인덱싱
  4. content_live_news_refresh — 10분마다 4탭(환율/금리/코스피/나스닥)
                                 RSS+요약 prefetch → Redis 캐시

스케줄 시각 ±60s 미스파이어 grace.
"""

from __future__ import annotations

import logging

from core.db import SessionLocal
from core.jobs import interval

from .live_news import refresh_all_topics
from .service import content_service

logger = logging.getLogger("content.jobs")


@interval(seconds=600, id="content_collect")
async def collect_tick() -> None:
    """뉴스 수집 tick — 10분."""
    async with SessionLocal() as session:
        stats = await content_service.run_collection(session)
    logger.info("content.jobs.collect_done", extra=stats)


@interval(seconds=300, id="content_ai_process")
async def ai_process_tick() -> None:
    """AI 큐 드레인 tick — 5분."""
    async with SessionLocal() as session:
        stats = await content_service.process_pending_ai(session, limit=40)
    logger.info("content.jobs.ai_done", extra=stats)


@interval(seconds=900, id="content_rag_index")
async def rag_index_tick() -> None:
    """RAG 인덱싱 tick — 15분."""
    async with SessionLocal() as session:
        stats = await content_service.index_for_rag(session, limit=30)
    logger.info("content.jobs.rag_done", extra=stats)


@interval(seconds=600, id="content_live_news_refresh")
async def live_news_refresh_tick() -> None:
    """주요 뉴스 4탭 prefetch tick — 10분.

    각 탭 키워드(환율/금리/코스피/나스닥)에 대해 Google News RSS를 새로 끌어와
    OpenAI batch 요약 후 Redis 캐시(`live_news:{topic}`, TTL 30분)에 저장.
    탭 클릭 응답이 Redis hit으로 즉시 떨어지게 만드는 prefetch 파이프라인.
    """
    stats = await refresh_all_topics()
    logger.info("content.jobs.live_news_done", extra=stats)


__all__ = [
    "ai_process_tick",
    "collect_tick",
    "live_news_refresh_tick",
    "rag_index_tick",
]
