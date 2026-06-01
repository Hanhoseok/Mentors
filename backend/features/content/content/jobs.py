"""콘텐츠 동 스케줄 작업 (AGENTS.md §5.7).

세 가지 주기 job:
  1. content_collect    — 10분마다 새 기사 수집·dedup·DB 저장
  2. content_ai_process — 5분마다 pending 큐의 AI 처리
  3. content_rag_index  — 15분마다 RAG 인덱싱

스케줄 시각 ±60s 미스파이어 grace.
"""

from __future__ import annotations

import logging

from core.db import SessionLocal
from core.jobs import interval

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


__all__ = ["ai_process_tick", "collect_tick", "rag_index_tick"]
