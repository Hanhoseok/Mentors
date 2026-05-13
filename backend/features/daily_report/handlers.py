"""이벤트 핸들러 — 멱등 필수 (§7.4, AGENTS.md §5.4).

DailyReportRequestedEvent를 받으면 사용자별 리포트를 생성한다.
스케줄 트리거(jobs.py) → fan-out 발행 → 각 사용자별 멱등 처리 패턴 (ADR-013).
"""

import logging

from core.contracts import DailyReportRequestedEvent

from .service import generate_for_user

logger = logging.getLogger("daily_report.handlers")


async def on_daily_report_requested(event: DailyReportRequestedEvent) -> None:
    # TODO: event.event_id를 처리 기록 테이블(예: report_processed_events)에 UNIQUE 저장하여
    # 같은 이벤트가 두 번 와도 한 번만 생성되게 보장 (멱등성 — §7.4).
    try:
        await generate_for_user(event.user_id)
    except Exception:
        logger.exception(
            "daily_report.handler_failed",
            extra={"event_id": event.event_id, "user_id": event.user_id},
        )
