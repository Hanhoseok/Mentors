"""일일 리포트 생성 서비스 (Phase 1: 생산자).

- DailyReportCore: 사용자×날짜 1회 공통 시장 코어 (멘토 무관)
- DailyReport: 멘토 전략별 리포트 (user × strategy × date)

모든 진입점은 멱등(get-or-create)이다. cron fan-out(선택 멘토 pre-warm)과
'그날 그 멘토 첫 진입' lazy 생성이 같은 (user, strategy, date)에 동시에 와도
UNIQUE 제약 + ON CONFLICT DO NOTHING으로 안전하다.

owner: daily_report / 관련 FR: FR-03, UC-02
boundary: cross-feature read는 user_context·core.read_services 만 사용 (ADR-014).
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.contracts import (
    DailyReportGeneratedEvent,
    MentorStrategy,
    NewsId,
    ReportId,
    Tier,
    UserId,
)
from core.db import SessionLocal
from core.event_bus import event_bus
from core.llm import llm
from core.push import push
from core.read_services import NewsRef, content_reader
from core.user_context import user_context

from .models import DailyReport, DailyReportCore
from .prompts import build_market_summary_prompt, build_report_prompt

logger = logging.getLogger("daily_report.service")

# KST는 DST가 없어 고정 UTC+9. zoneinfo/tzdata 의존 없이 '오늘(서울)'을 안전하게 계산.
_KST = timezone(timedelta(hours=9))
_NEWS_TOP_K = 3
_DEFAULT_STRATEGY = MentorStrategy.VALUE

# 백그라운드 본문 채움 태스크 레퍼런스 유지(미보유 시 GC로 취소될 수 있음).
_bg_tasks: set[asyncio.Task[None]] = set()


def _today() -> date:
    return datetime.now(_KST).date()


# ----------------------------------------------------------------------
# LLM 본문 생성 (+ 무키 환경 fallback)
# ----------------------------------------------------------------------


def _fallback_market_summary(news: list[NewsRef]) -> str:
    if not news:
        return "오늘은 선별된 시장 뉴스가 없어요."
    titles = " · ".join(n.title for n in news[:_NEWS_TOP_K])
    return f"오늘 눈에 띈 소식: {titles}"


def _fallback_body(
    nickname: str,
    news: list[NewsRef],
    market_summary: str | None,
) -> str:
    lines = [
        f"{nickname}님, 오늘의 시장 브리핑이에요.",
        "",
        "## 오늘의 시장",
        market_summary or "오늘은 비교적 조용한 흐름이에요.",
    ]
    if news:
        lines += ["", "## 주목할 소식", *[f"- {n.title}" for n in news[:_NEWS_TOP_K]]]
    lines += ["", "## 오늘의 한 걸음", "이 소식, 멘토와 함께 더 깊이 들여다볼까요?"]
    return "\n".join(lines)


async def _summarize_market(news: list[NewsRef]) -> str:
    """멘토 무관 중립 시장 요약. 실패/무키 시 뉴스 제목 fallback."""
    if not news or not llm.configured:
        return _fallback_market_summary(news)
    try:
        resp = await llm.chat(
            build_market_summary_prompt(news),
            use_case="content",
            max_tokens=400,
            temperature=0.5,
        )
    except Exception:  # noqa: BLE001 — 어떤 LLM 오류여도 리포트는 생성돼야 함
        logger.warning("daily_report.market_summary_failed")
        return _fallback_market_summary(news)
    return resp.text.strip() or _fallback_market_summary(news)


async def _compose_body(
    strategy: MentorStrategy,
    tier: Tier,
    nickname: str,
    news: list[NewsRef],
    market_summary: str | None,
) -> str:
    """멘토 전략 렌즈 + 티어 깊이로 리포트 본문 생성. 실패/무키 시 템플릿 fallback."""
    if not llm.configured:
        return _fallback_body(nickname, news, market_summary)
    try:
        resp = await llm.chat(
            build_report_prompt(strategy, tier, nickname, news, market_summary),
            max_tokens=1200,
            temperature=0.7,
        )
    except Exception:  # noqa: BLE001 — 본문 생성 실패해도 fallback으로 리포트 보장
        logger.warning("daily_report.body_failed", extra={"strategy": strategy.value})
        return _fallback_body(nickname, news, market_summary)
    return resp.text.strip() or _fallback_body(nickname, news, market_summary)


# ----------------------------------------------------------------------
# get-or-create (멱등)
# ----------------------------------------------------------------------


async def _get_or_create_core(
    user_id: UserId,
    report_date: date,
    session: AsyncSession,
) -> DailyReportCore:
    """사용자×날짜 공통 코어. 없으면 뉴스 선별 + 중립 요약 후 생성."""
    existing = await session.scalar(
        select(DailyReportCore).where(
            DailyReportCore.user_id == int(user_id),
            DailyReportCore.report_date == report_date,
        )
    )
    if existing is not None:
        return existing

    news = await content_reader.get_today_news_for_user(user_id, top_k=_NEWS_TOP_K)
    market_summary = await _summarize_market(news)

    await session.execute(
        pg_insert(DailyReportCore)
        .values(
            user_id=int(user_id),
            report_date=report_date,
            news_ids_json=json.dumps([int(n.id) for n in news]),
            market_summary=market_summary,
            # TODO: LearningReader 도입 시 학습 개념 연결 (현재 boundary상 보류)
            today_concept_id=None,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "report_date"])
    )

    core = await session.scalar(
        select(DailyReportCore).where(
            DailyReportCore.user_id == int(user_id),
            DailyReportCore.report_date == report_date,
        )
    )
    if core is None:  # pragma: no cover — insert/conflict 직후엔 반드시 존재
        raise RuntimeError("daily_report_core upsert로도 행이 없습니다")
    return core


async def _load_core_news(core: DailyReportCore) -> list[NewsRef]:
    """코어가 스냅샷한 뉴스 id로 NewsRef 복원 (top_k=3이라 N+1 무시 가능)."""
    try:
        ids = json.loads(core.news_ids_json or "[]")
    except json.JSONDecodeError:
        return []
    refs: list[NewsRef] = []
    for raw in ids:
        ref = await content_reader.get_news_by_id(NewsId(int(raw)))
        if ref is not None:
            refs.append(ref)
    return refs


async def _select_report(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
    session: AsyncSession,
) -> DailyReport | None:
    report: DailyReport | None = await session.scalar(
        select(DailyReport).where(
            DailyReport.user_id == int(user_id),
            DailyReport.mentor_strategy == strategy.value,
            DailyReport.report_date == report_date,
        )
    )
    return report


async def _get_or_create_pending(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
    session: AsyncSession,
) -> tuple[DailyReport, bool]:
    """LLM 없이 즉시 pending 행을 멱등 생성. 반환: (리포트, 이번 호출이 생성했는지).

    무거운 시장요약·본문 생성은 _fill_report가 채운다. ON CONFLICT DO NOTHING +
    RETURNING으로 정확히 한 호출만 created=True를 받으므로, '생성한 쪽'이 채움을
    소유한다(중복 생성 방지). tier는 LLM이 아닌 컨텍스트 조회라 빠른 경로에 포함.
    """
    existing = await _select_report(user_id, strategy, report_date, session)
    if existing is not None:
        return existing, False

    ctx = await user_context.get_for_daily_report(user_id)
    inserted_id = await session.scalar(
        pg_insert(DailyReport)
        .values(
            user_id=int(user_id),
            core_id=None,
            report_date=report_date,
            mentor_strategy=strategy.value,
            tier=ctx.tier.value,
            status="pending",
            body=None,
            highlights_json="[]",
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "mentor_strategy", "report_date"]
        )
        .returning(DailyReport.id)
    )
    created = inserted_id is not None

    report = await _select_report(user_id, strategy, report_date, session)
    if report is None:  # pragma: no cover — insert/conflict 직후엔 반드시 존재
        raise RuntimeError("daily_report pending upsert로도 행이 없습니다")
    return report, created


async def _fill_report(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
    session: AsyncSession,
) -> None:
    """pending 행에 시장 코어 + 본문 + 하이라이트를 채우고 ready로 전환.

    멱등: 행이 없거나 이미 ready면 no-op. 생성 소유자만 호출하는 전제라 경합
    클레임은 두지 않는다. 커밋은 호출자가 담당.
    """
    report = await _select_report(user_id, strategy, report_date, session)
    if report is None or report.status == "ready":
        return

    ctx = await user_context.get_for_daily_report(user_id)
    core = await _get_or_create_core(user_id, report_date, session)
    news = await _load_core_news(core)
    body = await _compose_body(strategy, ctx.tier, ctx.nickname, news, core.market_summary)
    highlights = [{"news_id": int(n.id), "title": n.title} for n in news]

    report.core_id = core.id
    report.body = body
    report.highlights_json = json.dumps(highlights, ensure_ascii=False)
    report.status = "ready"


async def _finalize_fallback(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
) -> None:
    """채움이 예외로 끝났을 때 pending에 갇히지 않게 폴백 본문으로 ready 마감."""
    try:
        async with SessionLocal() as session:
            report = await _select_report(user_id, strategy, report_date, session)
            if report is None or report.status == "ready":
                return
            try:
                nickname = (await user_context.get_for_daily_report(user_id)).nickname
            except Exception:  # noqa: BLE001 — 컨텍스트 실패해도 마감은 해야 함
                nickname = "투자자"
            report.body = _fallback_body(nickname, [], None)
            report.status = "ready"
            await session.commit()
    except Exception:  # noqa: BLE001 — 폴백 마감마저 실패하면 로그만 남기고 포기
        logger.exception(
            "daily_report.finalize_fallback_failed",
            extra={"user_id": user_id, "strategy": strategy.value},
        )


async def _fill_report_bg(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
) -> None:
    """응답 이후 별도 태스크로 본문을 채운다(lazy 진입 지연 제거)."""
    try:
        async with SessionLocal() as session:
            await _fill_report(user_id, strategy, report_date, session)
            await session.commit()
        logger.info(
            "daily_report.bg_filled",
            extra={"user_id": user_id, "strategy": strategy.value},
        )
    except Exception:  # noqa: BLE001 — 어떤 오류여도 행이 pending에 갇히지 않게 마감
        logger.exception(
            "daily_report.bg_fill_failed",
            extra={"user_id": user_id, "strategy": strategy.value},
        )
        await _finalize_fallback(user_id, strategy, report_date)


def _schedule_fill(
    user_id: UserId,
    strategy: MentorStrategy,
    report_date: date,
) -> None:
    """백그라운드 채움 태스크 등록. 레퍼런스를 잡아 GC 취소를 막는다."""
    task = asyncio.create_task(
        _fill_report_bg(user_id, strategy, report_date),
        name=f"daily_report_fill_{int(user_id)}_{strategy.value}_{report_date.isoformat()}",
    )
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# ----------------------------------------------------------------------
# 공개 진입점
# ----------------------------------------------------------------------


async def resolve_strategy(user_id: UserId) -> MentorStrategy:
    """선택 멘토 전략 해석 (content 동과 동일 boundary 패턴).

    user_context가 아직 전략을 노출하지 않으면 기본 VALUE. 학습 동에 대한 직접
    의존(get_mentor_strategy import)을 피하려고 user_context를 거친다.
    """
    try:
        ctx = await user_context.get_for_mentor_chat(user_id)
    except Exception:  # noqa: BLE001 — 컨텍스트 조회 실패 시 기본 전략으로 진행
        return _DEFAULT_STRATEGY
    raw = getattr(ctx, "selected_mentor_strategy", None)
    if raw is None:
        return _DEFAULT_STRATEGY
    try:
        return MentorStrategy(str(raw.value) if hasattr(raw, "value") else str(raw))
    except ValueError:
        return _DEFAULT_STRATEGY


async def get_or_create_today_report(
    user_id: UserId,
    strategy: MentorStrategy,
) -> DailyReport:
    """그날 그 멘토(전략) 리포트 get-or-create. 리더/라우터(lazy) 진입점.

    진입 지연을 없애려고 LLM 없이 pending 행만 즉시 만들어 반환하고, 본문 생성은
    백그라운드 태스크에 위임한다(status가 ready로 바뀔 때까지 클라이언트는 스켈레톤
    표시 후 폴링). 이미 있으면 그대로 반환(pending이면 진행 중인 채움을 기다린다).
    """
    report_date = _today()
    async with SessionLocal() as session:
        report, created = await _get_or_create_pending(user_id, strategy, report_date, session)
        await session.commit()
    if created:
        _schedule_fill(user_id, strategy, report_date)
    return report


async def get_today_report(
    user_id: UserId,
    strategy: MentorStrategy,
) -> DailyReport | None:
    """오늘 리포트 조회 전용 (생성하지 않음)."""
    async with SessionLocal() as session:
        report: DailyReport | None = await session.scalar(
            select(DailyReport).where(
                DailyReport.user_id == int(user_id),
                DailyReport.mentor_strategy == strategy.value,
                DailyReport.report_date == _today(),
            )
        )
    return report


async def generate_for_user(user_id: UserId) -> None:
    """단일 사용자 pre-warm. 멱등 — 같은 날 중복 호출 안전.

    cron fan-out → 핸들러가 호출. 선택 멘토 전략 1개만 미리 생성하고, 나머지
    전략은 그날 그 멘토 첫 진입 때 lazy 생성된다. 새로 생성된 경우에만
    이벤트 발행 + 푸시(중복 알림 방지).
    """
    report_date = _today()
    strategy = await resolve_strategy(user_id)

    async with SessionLocal() as session:
        report, created = await _get_or_create_pending(user_id, strategy, report_date, session)
        # cron pre-warm은 리스너 태스크에서 실행되므로 인라인으로 끝까지 채워
        # ready 상태로 만든 뒤 푸시한다(사용자엔 ready 리포트만 알림).
        if created:
            await _fill_report(user_id, strategy, report_date, session)
        await session.commit()

    if not created:
        logger.info(
            "daily_report.already_exists",
            extra={"user_id": user_id, "report_id": report.id, "strategy": strategy.value},
        )
        return

    await event_bus.publish(
        DailyReportGeneratedEvent(user_id=user_id, report_id=ReportId(report.id))
    )

    ctx = await user_context.get_for_daily_report(user_id)
    await push.send_to_user(
        user_id=user_id,
        title="오늘의 리포트가 도착했어요",
        body=f"{ctx.nickname}님, 오늘의 시장 흐름을 확인해보세요.",
        data={"deeplink": f"mentors://report/{report.id}"},
    )

    logger.info(
        "daily_report.generated",
        extra={"user_id": user_id, "report_id": report.id, "strategy": strategy.value},
    )


__all__ = [
    "generate_for_user",
    "get_or_create_today_report",
    "get_today_report",
    "resolve_strategy",
]
