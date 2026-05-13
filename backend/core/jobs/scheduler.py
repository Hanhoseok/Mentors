"""APScheduler — in-process AsyncIOScheduler (§4.14, ADR-013).

Jobstore 정책:
- SCHEDULER_JOBSTORE_URL이 설정되면 SQLAlchemyJobStore (영속화)
- 미설정이면 MemoryJobStore (재시작 시 유실 — dev 기본)

start()/stop()은 lifespan에서 호출. DB·드라이버 문제로 SQLAlchemyJobStore가 실패하면
자동으로 MemoryJobStore로 폴백한다 (앱 부팅 보장).
"""

import logging
from typing import Any

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings

logger = logging.getLogger("jobs")


def _build_jobstore() -> Any:
    if not settings.scheduler_jobstore_url:
        return MemoryJobStore()
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

        sync_url = settings.effective_jobstore_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg://"
        )
        return SQLAlchemyJobStore(url=sync_url, tablename="apscheduler_jobs")
    except Exception:
        logger.exception("scheduler.sqlalchemy_jobstore_failed_fallback_memory")
        return MemoryJobStore()


scheduler: AsyncIOScheduler = AsyncIOScheduler(
    jobstores={"default": _build_jobstore()},
    timezone=settings.scheduler_timezone,
)


async def start_scheduler() -> None:
    try:
        scheduler.start()
        logger.info(
            "scheduler.started",
            extra={"job_count": len(scheduler.get_jobs()), "tz": settings.scheduler_timezone},
        )
    except Exception:
        logger.exception("scheduler.start_failed")


async def stop_scheduler() -> None:
    try:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
    except Exception:
        logger.exception("scheduler.stop_failed")


__all__ = ["scheduler", "start_scheduler", "stop_scheduler"]
