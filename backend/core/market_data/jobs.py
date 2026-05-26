from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.market_data.collector import refresh_market_data

logger = logging.getLogger("market_data")

MARKET_DATA_REFRESH_JOB_ID = "market_data_refresh"


def register_market_data_jobs(scheduler: AsyncIOScheduler) -> None:
    if not settings.market_data_refresh_enabled:
        logger.info("market_data.refresh_disabled")
        return
    if scheduler.get_job(MARKET_DATA_REFRESH_JOB_ID):
        return
    scheduler.add_job(
        refresh_market_data,
        "interval",
        minutes=settings.market_data_refresh_interval_minutes,
        id=MARKET_DATA_REFRESH_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    logger.info(
        "market_data.refresh_registered",
        extra={"interval_minutes": settings.market_data_refresh_interval_minutes},
    )
