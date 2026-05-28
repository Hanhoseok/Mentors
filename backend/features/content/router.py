"""콘텐츠 동 사용자 노출 엔드포인트.

prefix: /api/content
인증: Mentors auth — Depends(get_current_user)

PR-2: /keywords CRUD
PR-4: /news, /news/{id}, /news/search, /scraps (생성/삭제/목록)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.auth.models import User
from core.contracts import MentorStrategy, ScrapAddedEvent
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import ConflictError, NotFoundError
from core.vector_store import vector_store

from .keyword_service import add_user_keyword, list_user_keywords, remove_user_keyword
from .models import NewsArticle, Scrap
from .schemas import (
    NewsArticleResponse,
    NewsListResponse,
    ScrapCreateRequest,
    ScrapResponse,
    SearchHit,
    SearchResponse,
    UserKeywordCreateRequest,
    UserKeywordListResponse,
    UserKeywordResponse,
)
from .service import RAG_COLLECTION

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
        ScrapAddedEvent(user_id=user.id, article_id=scrap.article_id)  # type: ignore[arg-type]
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


__all__ = ["router"]
