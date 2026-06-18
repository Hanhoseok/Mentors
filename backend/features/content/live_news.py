"""실시간 토픽 뉴스 — 전용 파이프라인 (백그라운드 prefetch + Redis 캐시).

SearchScreen 상단 4탭(환율/금리/코스피/나스닥) 전용 경로. 일반 뉴스 파이프라인
(`service.py`)과 데이터·키워드·테이블 모두 분리.

흐름:
  1. (jobs.py)   @interval로 `refresh_all_topics()` 호출 (10분)
  2. refresh:    각 TOPIC에 대해 GoogleNewsRSSCollector → OpenAI batch 요약
                 → Redis JSON 캐시 set(ttl=30분)
  3. 사용자가 탭 클릭 → 라우터는 `get_cached_topic_news()`로 Redis 즉시 응답
     캐시 미스 시 한 번만 라이브 fetch (lock으로 thundering herd 차단) + 캐시 채움

핵심 분리:
  - 일반 파이프라인: master_keywords 풀 + reliability 필터 + DB 저장
  - 토픽 파이프라인: 고정 4개 키워드 + 필터 없음 + Redis 캐시만
"""

from __future__ import annotations

import asyncio
import html as _html
import json
import logging
import re
from datetime import datetime
from typing import Any

from core.cache import make_cache
from core.contracts import MessageRole
from core.llm import Message, llm

from .collectors import GoogleNewsRSSCollector
from .schemas import ArticleRaw

logger = logging.getLogger("content.live_news")

# ── 토픽 ─────────────────────────────────────────────────────────────────────
# 고정 4탭. 새 탭 추가 시 여기에만 넣으면 prefetch 대상에 자동 포함.
TOPICS: tuple[str, ...] = ("환율", "금리", "코스피", "나스닥")
DEFAULT_LIMIT = 6
MAX_LIMIT = 10

# ── 캐시 정책 ───────────────────────────────────────────────────────────────
# TTL은 refresh interval(10분, jobs.py)보다 넉넉히 잡아서, 백그라운드 갱신이
# 한두 번 실패해도 직전 결과가 그대로 노출되도록 함.
_CACHE = make_cache("live_news")
_CACHE_TTL_SECONDS = 60 * 30          # 30분
_CACHE_LOCK_SECONDS = 30              # 라이브 fetch 1회 동안만 잠금

# Batch 요약에 넘기는 본문 스니펫 최대 길이
_SNIPPET_CHARS = 600


# ─────────────────────────────────────────────────────────────────────────────
# Public — 라우터에서 호출
# ─────────────────────────────────────────────────────────────────────────────


async def get_cached_topic_news(
    topic: str, *, limit: int = DEFAULT_LIMIT
) -> tuple[list[dict[str, Any]], bool]:
    """Redis에서 즉시 반환. 캐시 미스면 한 번만 fetch + 캐시 채움.

    Returns:
        (items, from_cache) — 모니터링용 from_cache 플래그 동봉.
    """
    topic = (topic or "").strip()
    if not topic:
        return [], True
    limit = max(1, min(limit, MAX_LIMIT))

    cached = await _read_cache(topic)
    if cached is not None:
        return cached[:limit], True

    # 캐시 미스 — lock으로 thundering herd 차단. lock 안에서 한 번 더 확인.
    try:
        async with _CACHE.lock(f"refresh:{topic}", ttl=_CACHE_LOCK_SECONDS):
            cached = await _read_cache(topic)
            if cached is not None:
                return cached[:limit], True
            items = await _fetch_and_summarize(topic, limit=max(limit, DEFAULT_LIMIT))
            await _write_cache(topic, items)
            return items[:limit], False
    except Exception:
        logger.exception("content.live_news.cache_miss_fetch_failed", extra={"topic": topic})
        return [], False


# ─────────────────────────────────────────────────────────────────────────────
# Public — 스케줄러(jobs.py)에서 호출
# ─────────────────────────────────────────────────────────────────────────────


async def refresh_all_topics(*, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """모든 TOPIC을 병렬로 fetch + 요약 → Redis 갱신. tick 1회분 통계 반환."""
    stats: dict[str, Any] = {"topics": list(TOPICS), "ok": [], "failed": [], "items_total": 0}

    async def _one(t: str) -> None:
        try:
            items = await _fetch_and_summarize(t, limit=limit)
            await _write_cache(t, items)
            stats["ok"].append(t)
            stats["items_total"] += len(items)
        except Exception:
            logger.exception("content.live_news.topic_refresh_failed", extra={"topic": t})
            stats["failed"].append(t)

    await asyncio.gather(*[_one(t) for t in TOPICS])
    logger.info("content.live_news.refresh_done", extra=stats)
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Internal — fetch + 요약
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_and_summarize(topic: str, *, limit: int) -> list[dict[str, Any]]:
    """단일 토픽: Google News RSS → OpenAI batch 요약 → dict 리스트."""
    rss = GoogleNewsRSSCollector()
    raws = await rss.collect(topic, max_items=limit)
    if not raws:
        logger.info("content.live_news.rss_empty", extra={"topic": topic})
        return []

    summaries = await _batch_summarize(topic, raws)

    items: list[dict[str, Any]] = []
    for raw, summary in zip(raws, summaries, strict=False):
        items.append(
            {
                "title": raw.title,
                "url": raw.url,
                "source_name": raw.source_name,
                "published_at": _iso(raw.published_at),
                "language": raw.language,
                "summary_ko": summary,
                "image_url": raw.image_url,
                "keywords": [topic],
            }
        )
    return items


async def _batch_summarize(topic: str, raws: list[ArticleRaw]) -> list[str]:
    """기사 N개를 한 번의 LLM 호출로 한국어 2~3문장씩 요약."""
    # 폴백/스니펫은 RSS content의 HTML(<a> 링크 등)을 제거한 순수 텍스트만 사용.
    # LLM 실패 시에도 카드에 링크가 노출되지 않도록 한다.
    fallbacks = [_truncate(_strip_html(raw.content) or raw.title, 240) for raw in raws]

    if not llm.configured:
        logger.info("content.live_news.llm_not_configured")
        return fallbacks

    payload = [
        {
            "i": idx,
            "title": raw.title,
            "snippet": _truncate(_strip_html(raw.content), _SNIPPET_CHARS),
        }
        for idx, raw in enumerate(raws)
    ]
    system = (
        "너는 경제 뉴스 정리 AI다. 입력으로 들어온 기사 배열의 각 항목을 "
        f"한국어 2~3문장으로 요약하라. 토픽 컨텍스트는 '{topic}'이며, "
        "각 요약은 토픽과의 연관성을 명확히 드러내야 한다. "
        "결과는 반드시 다음 형식의 JSON 배열로만 출력한다 (다른 텍스트 금지): "
        '[{"i": int, "summary": "한국어 요약"}, ...]'
    )
    user = json.dumps(payload, ensure_ascii=False)

    try:
        response = await llm.chat(
            messages=[
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user),
            ],
            temperature=0.3,
            max_tokens=900,
            response_format="json",
            use_case="content",
        )
        text = response.text
    except Exception:
        logger.exception("content.live_news.llm_call_failed", extra={"topic": topic})
        return fallbacks

    parsed = _parse_summary_json(text)
    if parsed is None:
        logger.warning("content.live_news.summary_parse_failed", extra={"topic": topic})
        return fallbacks

    out = list(fallbacks)
    for entry in parsed:
        try:
            idx = int(entry.get("i", -1))
            summary = str(entry.get("summary") or "").strip()
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(out) and summary:
            out[idx] = summary
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Internal — 캐시 R/W (JSON serialize)
# ─────────────────────────────────────────────────────────────────────────────


async def _read_cache(topic: str) -> list[dict[str, Any]] | None:
    raw = await _CACHE.get(topic)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


async def _write_cache(topic: str, items: list[dict[str, Any]]) -> None:
    if not items:
        # 빈 결과는 짧게만 캐시 (다음 tick에서 재시도 유도)
        await _CACHE.set(topic, json.dumps([], ensure_ascii=False), ttl=60)
        return
    await _CACHE.set(
        topic,
        json.dumps(items, ensure_ascii=False),
        ttl=_CACHE_TTL_SECONDS,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_summary_json(text: str) -> list[dict[str, Any]] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict) and "items" in data:
        data = data.get("items")
    return data if isinstance(data, list) else None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(s: str | None) -> str:
    """RSS content의 HTML 태그·엔티티를 제거해 순수 텍스트만 남긴다.

    Google News RSS의 content는 `<a href=...>제목</a> <font>출처</font>` 형태라,
    그대로 두면 카드 요약 자리에 링크/태그가 노출된다.
    """
    if not s:
        return ""
    text = _TAG_RE.sub(" ", s)
    text = _html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _truncate(s: str | None, n: int) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


__all__ = [
    "TOPICS",
    "get_cached_topic_news",
    "refresh_all_topics",
]
