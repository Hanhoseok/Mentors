"""이벤트 핸들러 — 멱등 필수 (§7.4, AGENTS.md §5.4).

DailyReportRequestedEvent를 받으면 사용자별 리포트를 생성한다.
스케줄 트리거(jobs.py) → fan-out 발행 → 각 사용자별 멱등 처리 패턴 (ADR-013).
"""

import logging

from core.contracts import DailyReportRequestedEvent

from .service import generate_for_user

logger = logging.getLogger("daily_report.handlers")


async def on_daily_report_requested(event: DailyReportRequestedEvent) -> None:
    # 멱등성(§7.4): generate_for_user가 (user, strategy, date) 자연키로 get-or-create
    # 하므로 같은 이벤트가 두 번 와도 리포트·푸시는 한 번만 발생한다. 별도 event_id
    # 처리 기록 테이블은 불필요.
    try:
        await generate_for_user(event.user_id)
    except Exception:
        logger.exception(
            "daily_report.handler_failed",
            extra={"event_id": event.event_id, "user_id": event.user_id},
        )
