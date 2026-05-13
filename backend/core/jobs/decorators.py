"""@cron / @interval — 동 owner가 features/<동>/jobs.py에서 사용.

사용:
    from core.jobs import cron, interval

    @cron("0 8 * * *", id="daily_report_dispatch")
    async def dispatch():
        ...

    @interval(seconds=300, id="content_news_crawl")
    async def crawl():
        ...

미스파이어 grace: 60초 (스케줄 시각 ±60초 내면 실행, 초과 시 skip).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .scheduler import scheduler

logger = logging.getLogger("jobs")

JobFunc = Callable[[], Awaitable[None]]
DEFAULT_MISFIRE_GRACE_TIME = 60


def _parse_cron(expr: str) -> dict[str, str]:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(
            f"cron expression must be 5 fields (minute hour day month day_of_week), got: {expr!r}"
        )
    return {
        "minute": fields[0],
        "hour": fields[1],
        "day": fields[2],
        "month": fields[3],
        "day_of_week": fields[4],
    }


def cron(
    expr: str,
    *,
    id: str,
    replace_existing: bool = True,
    misfire_grace_time: int = DEFAULT_MISFIRE_GRACE_TIME,
) -> Callable[[JobFunc], JobFunc]:
    parsed = _parse_cron(expr)

    def decorator(func: JobFunc) -> JobFunc:
        try:
            scheduler.add_job(
                func,
                "cron",
                id=id,
                replace_existing=replace_existing,
                misfire_grace_time=misfire_grace_time,
                **parsed,
            )
            logger.info("scheduler.job_registered", extra={"id": id, "type": "cron", "expr": expr})
        except Exception:
            logger.exception("scheduler.add_cron_failed", extra={"id": id})
        return func

    return decorator


def interval(
    seconds: int,
    *,
    id: str,
    replace_existing: bool = True,
    misfire_grace_time: int = DEFAULT_MISFIRE_GRACE_TIME,
) -> Callable[[JobFunc], JobFunc]:
    def decorator(func: JobFunc) -> JobFunc:
        try:
            scheduler.add_job(
                func,
                "interval",
                seconds=seconds,
                id=id,
                replace_existing=replace_existing,
                misfire_grace_time=misfire_grace_time,
            )
            logger.info(
                "scheduler.job_registered",
                extra={"id": id, "type": "interval", "seconds": seconds},
            )
        except Exception:
            logger.exception("scheduler.add_interval_failed", extra={"id": id})
        return func

    return decorator


def _suppress_unused(_: Any = None) -> None:
    """ruff F401 회피용 — 본 모듈은 사이드이펙트(scheduler.add_job)가 핵심."""


__all__ = ["cron", "interval"]
