"""콘텐츠 동 사용자 노출 엔드포인트.

prefix: /api/content
인증: Mentors auth — Depends(get_current_user)

PR-2:  /keywords CRUD
PR-4:  /news, /news/{id}, /news/search, /scraps (생성/삭제/목록)
PR-Ⅱ: /admin/retry-failed (AI 처리 실패 재시도)
"""

from __future__ import annotations

import json as _json
import logging
import re as _re
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.auth.models import User
from core.contracts import MentorStrategy, MessageRole, ScrapAddedEvent
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import ConflictError, NotFoundError
from core.llm import Message, llm
from core.vector_store import vector_store

from .collectors.rss import GoogleNewsRSSCollector
from .extractor import content_extractor
from .keyword_service import add_user_keyword, list_user_keywords, remove_user_keyword
from .models import NewsArticle, Scrap
from .schemas import (
    NewsArticleResponse,
    NewsListResponse,
    RssNewsItem,
    ScrapCreateRequest,
    ScrapResponse,
    SearchHit,
    SearchResponse,
    UrlSummarizeRequest,
    UrlSummarizeResponse,
    UserKeywordCreateRequest,
    UserKeywordListResponse,
    UserKeywordResponse,
)
from .service import RAG_COLLECTION, content_service

_rss_collector = GoogleNewsRSSCollector()

logger = logging.getLogger("content.router")
router = APIRouter(prefix="/api/content", tags=["content"])


# ---------------------------------------------------------------------------
# 뉴스 피드 (PR-4)
# ---------------------------------------------------------------------------


@router.get("/news", response_model=NewsListResponse)
async def list_news(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    strategy: MentorStrategy | None = Query(None, description="멘토 전략 필터"),
    min_reliability: int = Query(0, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("latest", regex="^(latest|reliability|composite)$"),
) -> NewsListResponse:
    """노출 가능 기사 페이징 조회.

    is_visible=True 기사만, reliability_score >= min_reliability.
    strategy 지정 시 NewsArticle.strategies LIKE 매칭.
    """
    base_stmt = select(NewsArticle).where(
        NewsArticle.is_visible.is_(True),
        NewsArticle.reliability_score >= min_reliability,
    )
    if strategy is not None:
        base_stmt = base_stmt.where(NewsArticle.strategies.ilike(f"%{strategy.value}%"))

    if sort == "reliability":
        stmt = base_stmt.order_by(desc(NewsArticle.reliability_score))
    elif sort == "composite":
        stmt = base_stmt.order_by(desc(NewsArticle.composite_score))
    else:
        stmt = base_stmt.order_by(desc(NewsArticle.published_at), desc(NewsArticle.id))

    # total — base_stmt에서 id COUNT
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one() or 0)

    offset = (page - 1) * page_size
    rows = (await db.execute(stmt.offset(offset).limit(page_size))).scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return NewsListResponse(
        items=[NewsArticleResponse.model_validate(a) for a in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# RSS 직접 피드 — DB 파이프라인 불필요 (실시간 Google News RSS)
# ---------------------------------------------------------------------------

# 기본 주요 뉴스 키워드
_TOP_NEWS_KEYWORD = "주식 투자 경제 금융 코스피"


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

_KO_STOPWORDS = frozenset([
    "이", "그", "저", "것", "수", "등", "및", "의", "을", "를", "가", "은", "는",
    "에", "와", "과", "도", "만", "까지", "부터", "에서", "으로", "로", "에게",
    "한", "하는", "있는", "없는", "되는", "된", "한다", "했다", "하다", "됩니다",
    "습니다", "입니다", "합니다", "있습니다", "없습니다", "대한", "통해", "위해",
    "따른", "관련", "대해", "위한", "같은", "이후", "이전", "현재", "오늘", "내일",
    "지난", "올해", "내년", "지난해", "뉴스", "기자", "기사", "보도",
])


def _extract_keywords_simple(text: str, max_kw: int = 5) -> list[str]:
    """제목/요약에서 LLM 없이 규칙 기반 키워드 추출."""
    if not text:
        return []
    parts = _re.split(r'[\s,\.!?\[\]()\·…"\'\/\-\%\|&<>]+', text)
    seen: set[str] = set()
    keywords: list[str] = []
    for w in parts:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in _KO_STOPWORDS:
            continue
        lw = w.lower()
        if lw in seen:
            continue
        seen.add(lw)
        keywords.append(w)
        if len(keywords) >= max_kw:
            break
    return keywords


_VALID_SENTIMENTS = frozenset(["positive", "neutral", "negative"])
_VALID_RELEVANCES = frozenset(["high", "medium", "low"])
_VALID_STRATEGIES = frozenset(["value", "growth", "dividend", "momentum"])


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """LLM 응답에서 JSON 파싱. 코드블록 래퍼·여분 텍스트 처리."""
    cleaned = _re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", raw.strip()).strip()
    m = _re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)
    parsed = _json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON 응답이 dict 아님")
    return parsed


def _article_raw_to_rss_item(a: object) -> RssNewsItem:
    """ArticleRaw → RssNewsItem 변환 헬퍼.

    a는 collectors의 ArticleRaw Pydantic 모델이지만 duck-typing으로 처리
    (mypy에게는 object). getattr default 패턴 유지.
    """
    title = getattr(a, "title", "")
    summary = getattr(a, "content", None)
    pub = getattr(a, "published_at", None)
    combined_text = f"{title} {summary or ''}".strip()
    return RssNewsItem(
        title=title,
        url=getattr(a, "url", ""),
        source_name=getattr(a, "source_name", None),
        published_at=pub.isoformat() if pub is not None else None,
        summary=summary,
        keywords=_extract_keywords_simple(combined_text, max_kw=5),
    )


@router.get("/news/top", response_model=list[RssNewsItem])
async def get_top_news(
    _user: User = Depends(get_current_user),
    limit: int = Query(8, ge=1, le=20),
) -> list[RssNewsItem]:
    """Google News RSS에서 주요 금융 뉴스를 실시간으로 가져온다.

    DB 파이프라인과 무관하게 항상 최신 기사를 반환합니다.
    """
    articles = await _rss_collector.collect(_TOP_NEWS_KEYWORD, max_items=limit)
    return [_article_raw_to_rss_item(a) for a in articles]


@router.get("/news/rss-search", response_model=list[RssNewsItem])
async def rss_search_news(
    q: str = Query(..., min_length=1, description="검색 키워드"),
    _user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=20),
) -> list[RssNewsItem]:
    """Google News RSS 키워드 검색.

    DB 파이프라인과 무관하게 키워드로 최신 기사를 검색합니다.
    """
    articles = await _rss_collector.collect(q, max_items=limit)
    return [_article_raw_to_rss_item(a) for a in articles]


_SUMMARIZE_PROMPT = """\
다음 뉴스 기사를 분석하여 JSON 형식으로만 응답해주세요.
코드블록이나 부연 설명 없이 JSON 객체만 출력하세요.

{{
  "summary": "투자자 관점 3~5문장 한국어 요약 (마크다운·불릿 없이 자연스러운 문단)",
  "sentiment": "positive 또는 neutral 또는 negative 중 하나",
  "investment_relevance": "high 또는 medium 또는 low 중 하나",
  "strategies": ["value","growth","dividend","momentum"] 중 해당하는 최대 2개 배열 (없으면 []),
  "keywords": ["핵심 한국어 키워드 최대 5개"],
  "reliability_score": 기사 신뢰도 0~100 정수
}}

제목: {title}
본문:
{body}
"""

_SUMMARIZE_TITLE_ONLY_PROMPT = """\
다음 뉴스 기사 제목을 바탕으로 JSON 형식으로만 응답해주세요. JSON 객체만 출력하세요.

{{
  "summary": "투자자 관점 2~3문장 한국어 설명 (마크다운 없이 자연스러운 문장)",
  "sentiment": "positive 또는 neutral 또는 negative 중 하나",
  "investment_relevance": "high 또는 medium 또는 low 중 하나",
  "strategies": ["value","growth","dividend","momentum"] 중 해당하는 최대 2개 배열 (없으면 []),
  "keywords": ["핵심 한국어 키워드 최대 5개"],
  "reliability_score": 기사 신뢰도 0~100 정수
}}

제목: {title}
"""

_NO_LLM_SUMMARY = "AI 요약을 생성할 수 없습니다. (LLM 미설정)"


@router.post("/news/summarize-url", response_model=UrlSummarizeResponse)
async def summarize_url(
    payload: UrlSummarizeRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UrlSummarizeResponse:
    """RSS 기사 URL을 받아 본문을 추출하고 LLM으로 한국어 요약 + 분석을 생성합니다.

    - content_extractor로 본문 + og:image + resolved_url 추출 (Google News interstitial 자동 처리)
    - Google 도메인 이미지 필터링 → DB 기사 이미지로 fallback
    - LLM에서 JSON 구조 응답 (요약, 감성, 투자관련도, 전략, 키워드, 신뢰도)
    - LLM 미설정 시 안내 문구 반환
    """
    title = (payload.title or "").strip() or "제목 없음"

    # 1. 본문 + 이미지 + 해소된 URL 추출
    body, image_url, resolved_url = await content_extractor.extract(payload.url)

    # 2. 이미지 없으면 DB에서 resolved_url로 조회
    if not image_url and resolved_url:
        try:
            db_article = await db.scalar(
                select(NewsArticle).where(
                    NewsArticle.original_url == resolved_url,
                    NewsArticle.image_url.isnot(None),
                )
            )
            if db_article and db_article.image_url:
                image_url = db_article.image_url
                logger.debug(
                    "content.summarize_url.db_image_used",
                    extra={"resolved_url": resolved_url[:200]},
                )
        except Exception as exc:
            logger.debug("content.summarize_url.db_image_lookup_failed", extra={"err": str(exc)})

    # 3. LLM 요약 + 분석 (JSON 응답)
    ai_summary = _NO_LLM_SUMMARY
    sentiment: str | None = None
    investment_relevance: str | None = None
    strategies: list[str] = []
    keywords: list[str] = []
    reliability_score: int | None = None

    if llm.configured:
        try:
            if body:
                prompt = _SUMMARIZE_PROMPT.format(title=title, body=body[:4000])
            else:
                prompt = _SUMMARIZE_TITLE_ONLY_PROMPT.format(title=title)

            resp = await llm.chat(
                [Message(role=MessageRole.USER, content=prompt)],
                use_case="content",
                max_tokens=800,
                temperature=0.4,
            )
            raw_text = resp.text.strip()

            # JSON 파싱 시도
            try:
                parsed = _parse_llm_json(raw_text)
                ai_summary = str(parsed.get("summary", "")).strip() or raw_text
                raw_sentiment = str(parsed.get("sentiment", "")).lower()
                sentiment = raw_sentiment if raw_sentiment in _VALID_SENTIMENTS else None
                raw_relevance = str(parsed.get("investment_relevance", "")).lower()
                investment_relevance = raw_relevance if raw_relevance in _VALID_RELEVANCES else None
                strategies = [
                    s for s in (parsed.get("strategies") or []) if s in _VALID_STRATEGIES
                ][:2]
                keywords = [str(k).strip() for k in (parsed.get("keywords") or []) if k][:5]
                raw_score = parsed.get("reliability_score")
                if raw_score is not None:
                    try:
                        reliability_score = max(0, min(100, int(raw_score)))
                    except (TypeError, ValueError):
                        reliability_score = None
            except (_json.JSONDecodeError, KeyError, TypeError):
                # JSON 파싱 실패 시 원문을 요약으로 사용
                ai_summary = raw_text

        except Exception as exc:
            logger.warning("content.summarize_url_llm_failed", extra={"err": str(exc)})
            ai_summary = "요약 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

    return UrlSummarizeResponse(
        title=title,
        ai_summary=ai_summary,
        image_url=image_url,
        original_url=payload.url,
        sentiment=sentiment,
        investment_relevance=investment_relevance,
        strategies=strategies,
        keywords=keywords,
        reliability_score=reliability_score,
    )


# /news/search 를 /news/{news_id} 보다 먼저 선언 (path resolution 우선)
@router.get("/news/search", response_model=SearchResponse)
async def search_news(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., min_length=2, description="검색어"),
    top_k: int = Query(10, ge=1, le=50),
) -> SearchResponse:
    """기사 의미 기반 검색. Chroma에서 청크 검색 후 DB 메타데이터로 augment."""
    docs = await vector_store.search(RAG_COLLECTION, query=q, top_k=top_k)
    if not docs:
        return SearchResponse(query=q, total=0, results=[])

    # 청크 문서 → article_id 집계 → DB row 한 번에 가져오기
    article_ids: list[int] = []
    chunk_by_article: dict[int, str] = {}
    score_by_article: dict[int, float] = {}
    for d in docs:
        aid = int(d.metadata.get("article_id", 0) or 0)
        if not aid:
            continue
        if aid not in chunk_by_article:
            article_ids.append(aid)
            chunk_by_article[aid] = d.text
            score_by_article[aid] = 1.0 / (1 + len(article_ids))  # rough rank
    if not article_ids:
        return SearchResponse(query=q, total=0, results=[])

    rows = (
        await db.execute(select(NewsArticle).where(NewsArticle.id.in_(article_ids)))
    ).scalars().all()
    by_id = {a.id: a for a in rows}

    hits: list[SearchHit] = []
    for aid in article_ids:
        a = by_id.get(aid)
        if a is None or not a.is_visible:
            continue
        hits.append(
            SearchHit(
                article_id=a.id,
                score=score_by_article[aid],
                title=a.title_translated or a.title_original,
                summary=a.summary_ko,
                source_name=a.source_name,
                url=a.original_url,
                image_url=a.image_url,
                matched_chunk=chunk_by_article[aid][:300],
                published_at=a.published_at,
            )
        )
    return SearchResponse(query=q, total=len(hits), results=hits)


@router.get("/news/{news_id}", response_model=NewsArticleResponse)
async def get_news(
    news_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NewsArticleResponse:
    """기사 상세 조회. is_visible=False면 404."""
    article = await db.scalar(select(NewsArticle).where(NewsArticle.id == news_id))
    if article is None or not article.is_visible:
        raise NotFoundError("뉴스를 찾을 수 없습니다")
    return NewsArticleResponse.model_validate(article)


# ---------------------------------------------------------------------------
# 스크랩 (PR-4) — ScrapAddedEvent 발행으로 다른 동(growth 등)에 알림
# ---------------------------------------------------------------------------


@router.post("/scraps", response_model=ScrapResponse, status_code=201)
async def add_scrap(
    payload: ScrapCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScrapResponse:
    """기사 스크랩 생성. ScrapAddedEvent 발행."""
    article = await db.scalar(select(NewsArticle).where(NewsArticle.id == payload.article_id))
    if article is None:
        raise NotFoundError("기사를 찾을 수 없습니다")

    existing = await db.scalar(
        select(Scrap).where(Scrap.user_id == user.id, Scrap.article_id == payload.article_id)
    )
    if existing is not None:
        raise ConflictError("이미 스크랩된 기사입니다")

    scrap = Scrap(user_id=user.id, article_id=payload.article_id)
    db.add(scrap)
    await db.commit()
    await db.refresh(scrap)

    # core.contracts.ArticleId는 NewType[int] — 그냥 int 전달
    await event_bus.publish(
        ScrapAddedEvent(user_id=user.id, article_id=scrap.article_id)
    )
    logger.info("content.scrap_added", extra={"user_id": user.id, "article_id": scrap.article_id})

    return ScrapResponse.model_validate(scrap)


@router.delete("/scraps/{scrap_id}", status_code=204)
async def remove_scrap(
    scrap_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """본인 소유 스크랩 삭제."""
    scrap = await db.scalar(
        select(Scrap).where(Scrap.id == scrap_id, Scrap.user_id == user.id)
    )
    if scrap is None:
        raise NotFoundError("스크랩을 찾을 수 없습니다")
    await db.delete(scrap)
    await db.commit()


@router.get("/scraps", response_model=list[ScrapResponse])
async def list_my_scraps(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[ScrapResponse]:
    """내 스크랩 목록 (최신 순)."""
    rows = (
        await db.execute(
            select(Scrap)
            .where(Scrap.user_id == user.id)
            .order_by(desc(Scrap.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [ScrapResponse.model_validate(s) for s in rows]


# ---------------------------------------------------------------------------
# 사용자 관심 키워드 CRUD (PR-2 머지본)
# user_id는 항상 get_current_user.id에서 가져온다 — 요청 본문에서 받지 않음.
# ---------------------------------------------------------------------------


@router.get("/keywords", response_model=UserKeywordListResponse)
async def list_my_keywords(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeywordListResponse:
    """현재 로그인 사용자의 관심 키워드 목록."""
    rows = await list_user_keywords(db, user_id=user.id)
    items = [UserKeywordResponse.model_validate(r) for r in rows]
    return UserKeywordListResponse(items=items, total=len(items))


@router.post("/keywords", response_model=UserKeywordResponse, status_code=201)
async def add_my_keyword(
    payload: UserKeywordCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeywordResponse:
    """사용자 관심 키워드 추가. 중복은 ConflictError."""
    user_keyword = await add_user_keyword(
        db,
        user_id=user.id,
        keyword=payload.keyword,
        language=payload.language,
        source="manual",
    )
    if user_keyword is None:
        raise ConflictError("이미 등록된 키워드입니다")
    logger.info(
        "content.user_keyword_added",
        extra={"user_id": user.id, "keyword_id": user_keyword.id},
    )
    return UserKeywordResponse.model_validate(user_keyword)


@router.delete("/keywords/{user_keyword_id}", status_code=204)
async def remove_my_keyword(
    user_keyword_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """사용자 관심 키워드 삭제. 본인 소유만 가능."""
    deleted = await remove_user_keyword(db, user_id=user.id, user_keyword_id=user_keyword_id)
    if not deleted:
        raise NotFoundError("키워드를 찾을 수 없습니다")


# ---------------------------------------------------------------------------
# Admin — AI 처리 실패 재시도 (PR-Ⅱ)
# ---------------------------------------------------------------------------
# TODO: 향후 admin role 시스템 도입 시 require_admin dependency로 교체.
#       현재는 인증된 사용자면 호출 가능 (mentors는 아직 role 분리 없음).


@router.post("/admin/retry-failed")
async def retry_failed_ai(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="한 번에 reset할 최대 행 수"),
) -> dict[str, Any]:
    """ai_processing_status='failed' 기사를 'pending'으로 되돌림.

    다음 ai_process_tick(5분 간격)이 자동 재처리. 즉시 처리는 안 함 —
    응답은 빠르게 반환. 결과 모니터링은 별도 쿼리.

    Response:
        {"reset": N, "sample": [{"id": ..., "title": ..., "ai_error": ...}, ...]}
    """
    result = await content_service.reset_failed_to_pending(db, limit=limit)
    logger.info(
        "content.admin.retry_failed_called",
        extra={"user_id": user.id, "reset": result["reset"], "limit": limit},
    )
    return result


__all__ = ["router"]
