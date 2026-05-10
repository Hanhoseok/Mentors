"""일일 리포트 생성 서비스."""

import logging

from core.contracts import DailyReportGeneratedEvent, ReportId, UserId
from core.event_bus import event_bus
from core.push import push
from core.read_services import content_reader
from core.user_context import user_context

logger = logging.getLogger("daily_report.service")


async def generate_for_user(user_id: UserId) -> None:
    """단일 사용자 리포트 생성. 멱등 — 같은 날짜에 중복 호출되어도 안전해야 함."""
    ctx = await user_context.get_for_daily_report(user_id)
    news = await content_reader.get_today_news_for_user(user_id, top_k=3)

    # TODO: LLM 호출로 리포트 본문 생성
    # from core.llm import llm
    # response = await llm.chat([...])

    # TODO: daily_reports 테이블에 저장 (DailyReport 모델 — 본 동에서 추가)
    report_id = ReportId(0)  # placeholder

    await event_bus.publish(DailyReportGeneratedEvent(user_id=user_id, report_id=report_id))

    # 푸시 알림 (FCM 미설정 시 자동 no-op)
    await push.send_to_user(
        user_id=user_id,
        title="오늘의 리포트가 도착했어요",
        body=f"{ctx.nickname}님, 오늘의 시장 흐름을 확인해보세요.",
        data={"deeplink": f"mentors://report/{report_id}"},
    )

    logger.info(
        "daily_report.generated",
        extra={"user_id": user_id, "report_id": report_id, "news_count": len(news)},
    )
