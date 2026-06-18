"""콘텐츠 동 사용자 노출 엔드포인트.

prefix: /api/content
인증: Mentors auth — Depends(get_current_user)

PR-2:  /keywords CRUD
PR-4:  /news, /news/{id}, /news/search, /scraps (생성/삭제/목록)
PR-Ⅱ: /admin/retry-failed (AI 처리 실패 재시도)
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from dataclasses import dataclass, field

from sqlalchemy import and_, desc, func, or_, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.auth.models import User
from core.contracts import MentorStrategy, ScrapAddedEvent
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import ConflictError, NotFoundError
from core.vector_store import vector_store

from sqlalchemy.orm import selectinload

from .keyword_service import add_user_keyword, list_user_keywords, remove_user_keyword
from .live_news import get_cached_topic_news
from .models import (
    Industry,
    IndustryKeyword,
    MasterKeyword,
    MasterKeywordCompany,
    NewsArticle,
    Scrap,
    ScrapFolder,
)
from .schemas import (
    IndustryItem,
    IndustryKeywordItem,
    LiveTopicNewsItem,
    LiveTopicNewsResponse,
    NewsArticleResponse,
    NewsListResponse,
    ScrapCreateRequest,
    ScrapExistsResponse,
    ScrapFolderCreateRequest,
    ScrapFolderResponse,
    ScrapResponse,
    SearchHit,
    SearchResponse,
    UserKeywordCreateRequest,
    UserKeywordListResponse,
    UserKeywordResponse,
)
from .service import RAG_COLLECTION, SEARCH_MIN_SCORE, content_service

logger = logging.getLogger("content.router")
router = APIRouter(prefix="/api/content", tags=["content"])


# ---------------------------------------------------------------------------
# 산업 카탈로그 — 관심사 설정 화면용
# ---------------------------------------------------------------------------


@router.get("/industries", response_model=list[IndustryItem])
async def list_industries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IndustryItem]:
    """산업 + 하위 키워드 트리. 관심사 설정 화면이 카드로 그릴 때 사용.

    display_order asc, 각 industry 내부의 하위 키워드도 display_order asc.
    인증은 사용자별로 다른 데이터를 주지는 않지만 일관성 위해 require.
    """
    stmt = (
        select(Industry)
        .options(selectinload(Industry.keywords))
        .order_by(Industry.display_order.asc(), Industry.id.asc())
    )
    industries = list((await db.execute(stmt)).scalars().all())

    return [
        IndustryItem(
            id=ind.id,
            name_ko=ind.name_ko,
            name_en=ind.name_en,
            display_order=ind.display_order,
            keywords=[
                IndustryKeywordItem.model_validate(kw)
                for kw in sorted(
                    ind.keywords,
                    key=lambda k: (k.display_order, k.id),
                )
            ],
        )
        for ind in industries
    ]


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
    sort: str = Query("latest", pattern="^(latest|reliability|composite)$"),
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


# ── 검색 확장 정책 ──────────────────────────────────────────────────────────
# generalist = 사업이 워낙 광범위해서 회사명만 매칭하면 토픽과 무관한 뉴스가
# 대량 유입되는 거대 기술 기업. 검색 확장에서는 이 회사명만 단독 매칭하지 않고,
# 반드시 토픽 키워드(원본 검색어 + 동의어)가 같은 기사에 함께 나와야 통과시킴.
# 예: "양자컴퓨터" 검색 시 NVIDIA가 들어간 기사는 "quantum"도 같이 있어야 hit.
_GENERALIST_COMPANIES: set[str] = {
    "NVIDIA", "IBM", "Microsoft", "Microsoft AI", "Microsoft Copilot",
    "Google", "Google AI", "Google DeepMind", "Google Quantum AI",
    "Apple", "Amazon", "Amazon Braket", "Azure AI",
    "Meta", "Meta Platforms", "Alphabet",
    "Oracle", "Oracle AI", "Samsung",
    "Intel", "AMD", "Broadcom", "TSMC", "Taiwan Semiconductor",
}

# 산업 키워드(label_ko) → 토픽 anchor 영문/한국어 동의어.
# 시드 데이터의 keyword_en이 한국어 그대로인 경우가 많아 보충용. 미등록 키워드는
# 원본 검색어만 anchor로 사용. 새 산업 추가 시 여기에 한 줄씩 늘리면 됨.
_TOPIC_SYNONYMS: dict[str, list[str]] = {
    "양자컴퓨터": ["양자컴퓨터", "양자 컴퓨터", "양자 컴퓨팅", "양자컴퓨팅",
                "quantum computing", "quantum computer", "quantum"],
    "인공지능":   ["인공지능", "AI", "artificial intelligence",
                "machine learning", "ML", "deep learning"],
    "반도체":     ["반도체", "semiconductor", "chip", "wafer", "foundry"],
    "전기차":     ["전기차", "EV", "electric vehicle"],
    "배터리":     ["배터리", "battery"],
    "암호화폐":   ["암호화폐", "crypto", "cryptocurrency", "bitcoin", "ethereum"],
    "클라우드":   ["클라우드", "cloud", "AWS", "Azure", "GCP"],
    "보안":       ["보안", "security", "cybersecurity", "endpoint"],
}


@dataclass
class ExpandedQuery:
    """`_expand_query_terms` 결과.

    - topic_terms      : 검색어 + (있다면) IndustryKeyword 동의어. 토픽 anchor.
                         단독으로도 매칭 가능. generalist 회사명과 결합되는 anchor 역할.
    - specialist_terms : generalist에 안 들어가는 회사명. 단독 매칭 OK.
    - generalist_terms : 거대 기술 기업 회사명. 토픽 anchor와 동시 등장해야 매칭.
    """

    topic_terms: list[str] = field(default_factory=list)
    specialist_terms: list[str] = field(default_factory=list)
    generalist_terms: list[str] = field(default_factory=list)


async def _expand_query_terms(db: AsyncSession, query: str) -> ExpandedQuery:
    """검색어를 토픽 anchor + 회사명(specialist/generalist)로 확장.

    동작:
      1. query 자체는 topic_terms에 포함
      2. IndustryKeyword.label_ko 또는 .keyword_en 정확 매칭 시:
         - label_ko/keyword_en → topic_terms 추가
         - _TOPIC_SYNONYMS의 매핑된 영문/한국어 변형 → topic_terms 추가
      3. 매칭된 산업 산하 MasterKeyword들의 MasterKeywordCompany 회사명을
         generalist 집합과 대조해서 specialist/generalist로 분리
    """
    q = query.strip()
    out = ExpandedQuery()
    if not q:
        return out

    topic: set[str] = {q}

    # ── 1) IndustryKeyword 매칭 ─────────────────────────────────────────────
    ind_stmt = select(IndustryKeyword).where(
        or_(IndustryKeyword.label_ko == q, IndustryKeyword.keyword_en == q)
    )
    industry_kws = list((await db.execute(ind_stmt)).scalars().all())

    industry_kw_ids: list[int] = [ik.id for ik in industry_kws]
    for ik in industry_kws:
        if ik.label_ko:
            topic.add(ik.label_ko)
        if ik.keyword_en:
            topic.add(ik.keyword_en)
        for syn in _TOPIC_SYNONYMS.get(ik.label_ko, []):
            topic.add(syn)
    # query 자체가 시너지 동의어 맵에 있을 때
    for syn in _TOPIC_SYNONYMS.get(q, []):
        topic.add(syn)

    out.topic_terms = sorted(topic)

    # ── 2) MasterKeyword 매칭 ────────────────────────────────────────────────
    mk_where = [MasterKeyword.keyword == q]
    if industry_kw_ids:
        mk_where.append(MasterKeyword.industry_keyword_id.in_(industry_kw_ids))
    mk_stmt = select(MasterKeyword).where(or_(*mk_where))
    master_kws = list((await db.execute(mk_stmt)).scalars().all())

    master_kw_ids = [mk.id for mk in master_kws]
    if not master_kw_ids:
        return out

    # ── 3) MasterKeywordCompany → specialist / generalist 분리 ──────────────
    co_stmt = select(MasterKeywordCompany).where(
        MasterKeywordCompany.master_keyword_id.in_(master_kw_ids)
    )
    companies = list((await db.execute(co_stmt)).scalars().all())

    specialist: set[str] = set()
    generalist: set[str] = set()
    for c in companies:
        name = (c.company_name or "").strip()
        if not name:
            continue
        bucket = generalist if name in _GENERALIST_COMPANIES else specialist
        bucket.add(name)
        # 한국어 회사명도 같은 버킷에 추가
        ko = (c.company_name_ko or "").strip()
        if ko:
            bucket.add(ko)

    out.specialist_terms = sorted(specialist)
    out.generalist_terms = sorted(generalist)
    return out


# /news/search 를 /news/{news_id} 보다 먼저 선언 (path resolution 우선)
@router.get("/news/search", response_model=SearchResponse)
async def search_news(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., min_length=1, description="검색어"),
    top_k: int = Query(15, ge=1, le=50),
    visible_only: bool = Query(
        False,
        description=(
            "True면 is_visible=True(노출 임계값 이상) 기사만. "
            "기본 False — 파이프라인이 수집한 전체 풀에서 검색해서 "
            "사용자가 임의 키워드로도 결과를 받을 수 있게 함."
        ),
    ),
    min_score: int = Query(
        SEARCH_MIN_SCORE,
        ge=0,
        le=100,
        description=(
            "reliability_score 최저값. 기본 = CONTENT_SEARCH_MIN_SCORE env "
            "(현재 40). 경제/투자와 무관한 저품질 기사를 검색에서 배제하기 위한 필터. "
            "AI 처리 큐(RAG 임계값)와 분리돼 있어 검색 풀만 조정 가능."
        ),
    ),
) -> SearchResponse:
    """기사 하이브리드 검색.

    1. Chroma 시맨틱 검색으로 article_id 후보 추출
    2. DB에서 title/summary/content/ai_keywords ILIKE 키워드 매칭
    3. 두 결과를 article_id로 dedupe·머지 (시맨틱 점수가 더 높음)
    4. reliability_score >= min_score 인 행만 최종 반환 — 비경제/저품질 차단

    기본은 visibility 필터 OFF, min_score=45 (RAG 임계값).
    """
    # ── 1) 시맨틱 (Chroma cosine distance 임계값 필터) ──────────────────────
    # distance > SEMANTIC_DISTANCE_THRESHOLD 인 결과는 "그나마 가까운 무관 매칭"
    # 으로 보고 버림. cosine distance: 0.0=동일, 1.0=직교(무관). 0.55는 보수적.
    SEMANTIC_DISTANCE_THRESHOLD = 0.55
    semantic_ids: list[int] = []
    chunk_by_article: dict[int, str] = {}
    score_by_article: dict[int, float] = {}
    try:
        docs = await vector_store.search(RAG_COLLECTION, query=q, top_k=top_k)
    except Exception as exc:
        logger.warning("content.search.semantic_failed", extra={"err": str(exc)})
        docs = []
    dropped_distant = 0
    for d in docs:
        # 거리 너무 멀면 drop — 검색어와 진짜 무관한 기사가 끌려오는 거 방지
        if d.distance is not None and d.distance > SEMANTIC_DISTANCE_THRESHOLD:
            dropped_distant += 1
            continue
        aid = int(d.metadata.get("article_id", 0) or 0)
        if not aid or aid in chunk_by_article:
            continue
        semantic_ids.append(aid)
        chunk_by_article[aid] = d.text
        # distance가 작을수록 점수 높게: 1 - distance 사용 (1.0 ~ 0.45 범위)
        sim = (1.0 - d.distance) if d.distance is not None else 0.6
        score_by_article[aid] = float(sim)
    if dropped_distant:
        logger.info(
            "content.search.distant_semantic_dropped",
            extra={"q": q, "dropped": dropped_distant, "kept": len(semantic_ids)},
        )

    # ── 2) 키워드 (DB ILIKE) — 토픽 anchor + specialist/generalist 분리 ─────
    # 한국어 키워드는 영문 기사를 못 잡으므로 IndustryKeyword 시드 데이터를 따라
    # 회사명까지 확장. 단, 거대 기술 기업(NVIDIA, IBM, MSFT 등)은 회사명만으로는
    # 토픽 무관 뉴스가 대량 유입되므로 토픽 anchor와 동시 등장(AND)해야 통과시킴.
    expanded = await _expand_query_terms(db, q)

    _FIELDS = (
        NewsArticle.title_translated,
        NewsArticle.title_original,
        NewsArticle.summary_ko,
        NewsArticle.content_translated,
        NewsArticle.content,
        NewsArticle.ai_keywords,
        NewsArticle.related_keywords,
    )

    import re as _re

    def _is_short_acronym(term: str) -> bool:
        """4자 이하 영문 약어 — 단어 경계 매칭이 필요한 케이스.

        예) "AI", "ML", "GPU", "LLM" → AIRBUS/WILLIAM/SHGPU 같은 substring 매칭
        방지. 한글 키워드("양자")는 단어 경계 개념이 약해서 단순 ILIKE 사용.
        """
        return (
            1 <= len(term) <= 4
            and term.isascii()
            and any(c.isalpha() for c in term)
        )

    def _any_field_ilike(terms: list[str]):
        """terms 중 하나라도 모든 필드 중 하나에 매칭되면 True (단일 SQL OR 그룹).

        짧은 영문 약어는 PostgreSQL `~*` 정규식 + `\\y` 단어 경계로 매칭해서
        AI→AIRBUS, ML→WILLIAM 같은 false positive 방지.
        """
        conds = []
        for term in terms:
            if not term:
                continue
            if _is_short_acronym(term):
                pattern = rf"\y{_re.escape(term)}\y"
                conds.extend(f.op("~*")(pattern) for f in _FIELDS)
            else:
                pat = f"%{term}%"
                conds.extend(f.ilike(pat) for f in _FIELDS)
        return or_(*conds) if conds else None

    topic_match = _any_field_ilike(expanded.topic_terms)
    specialist_match = _any_field_ilike(expanded.specialist_terms)
    generalist_match = _any_field_ilike(expanded.generalist_terms)

    # 최종 텍스트 매칭 OR 그룹:
    #   topic         (단독 OK — 토픽이 본문에 직접 나옴)
    #   OR specialist (단독 OK — 전문 기업명이 본문에 나옴)
    #   OR (generalist AND topic)  — 거대 기업명은 토픽과 동시 등장해야 함
    text_clauses = []
    if topic_match is not None:
        text_clauses.append(topic_match)
    if specialist_match is not None:
        text_clauses.append(specialist_match)
    if generalist_match is not None and topic_match is not None:
        text_clauses.append(and_(generalist_match, topic_match))

    if not text_clauses:
        # 빈 검색어 방어 — 정상 흐름에선 도달 안 함 (q.min_length=1)
        text_clauses = [NewsArticle.id.is_(None)]

    keyword_where = [
        NewsArticle.reliability_score >= min_score,
        or_(*text_clauses),
    ]
    if visible_only:
        keyword_where.insert(0, NewsArticle.is_visible.is_(True))

    if (
        len(expanded.topic_terms) > 1
        or expanded.specialist_terms
        or expanded.generalist_terms
    ):
        logger.info(
            "content.search.query_expanded",
            extra={
                "q": q,
                "topic": expanded.topic_terms,
                "specialist_n": len(expanded.specialist_terms),
                "generalist_n": len(expanded.generalist_terms),
            },
        )

    keyword_stmt = (
        select(NewsArticle)
        .where(*keyword_where)
        .order_by(desc(NewsArticle.published_at))
        .limit(top_k * 3)  # 확장 검색이라 후보를 더 넓게, 최종 sort 후 top_k로 trim
    )
    keyword_rows = (await db.execute(keyword_stmt)).scalars().all()

    # ── 3) Merge ─────────────────────────────────────────────────────────────
    # ILIKE 매칭은 검색어가 실제 텍스트에 등장하는 것이므로 정확도 보장 → 0.7 점수
    # 시맨틱은 distance에 따라 0.45~1.0 — distance 작으면 시맨틱이 ILIKE보다 위
    all_ids: list[int] = list(semantic_ids)
    seen: set[int] = set(semantic_ids)
    for art in keyword_rows:
        if art.id in seen:
            # 양쪽 다 매칭된 기사는 시맨틱 점수에 보너스 + 0.15
            score_by_article[art.id] = min(1.0, score_by_article.get(art.id, 0.6) + 0.15)
            continue
        all_ids.append(art.id)
        seen.add(art.id)
        score_by_article[art.id] = 0.7
        snippet = art.summary_ko or art.content_translated or art.content or art.title_original or ""
        chunk_by_article[art.id] = snippet[:300]

    if not all_ids:
        return SearchResponse(query=q, total=0, results=[])

    # 시맨틱 후보 중 DB lookup이 필요한 ID만 추가 조회
    need_lookup = [aid for aid in semantic_ids if aid not in {a.id for a in keyword_rows}]
    extra_rows: list[NewsArticle] = []
    if need_lookup:
        extra_rows = list(
            (await db.execute(select(NewsArticle).where(NewsArticle.id.in_(need_lookup))))
            .scalars()
            .all()
        )
    by_id: dict[int, NewsArticle] = {a.id: a for a in keyword_rows}
    for a in extra_rows:
        by_id.setdefault(a.id, a)

    hits: list[SearchHit] = []
    low_quality_dropped = 0
    for aid in all_ids:
        a = by_id.get(aid)
        if a is None:
            continue
        if visible_only and not a.is_visible:
            continue
        # reliability 필터 — 시맨틱으로 끌려온 경제 무관 저품질 기사 차단
        if a.reliability_score < min_score:
            low_quality_dropped += 1
            continue
        hits.append(
            SearchHit(
                article_id=a.id,
                score=score_by_article.get(aid, 0.0),
                title=a.title_translated or a.title_original,
                summary=a.summary_ko,
                source_name=a.source_name,
                url=a.original_url,
                image_url=a.image_url,
                matched_chunk=chunk_by_article.get(aid, "")[:300],
                published_at=a.published_at,
            )
        )
    if low_quality_dropped:
        logger.info(
            "content.search.low_quality_dropped",
            extra={"q": q, "min_score": min_score, "dropped": low_quality_dropped},
        )

    # 점수 내림차순 정렬
    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[:top_k]
    return SearchResponse(query=q, total=len(hits), results=hits)


# ---------------------------------------------------------------------------
# 실시간 토픽 뉴스 — SearchScreen 상단 탭(환율/금리/코스피/나스닥)용
# 파이프라인 우회: 신뢰도 필터/DB 저장 없이 RSS + OpenAI 요약만 즉석 수행
# ---------------------------------------------------------------------------


# /news/live-topics 를 /news/{news_id} 보다 먼저 선언
@router.get("/news/live-topics", response_model=LiveTopicNewsResponse)
async def live_topic_news(
    user: User = Depends(get_current_user),
    topic: str = Query(..., min_length=1, max_length=80, description="탭 키워드"),
    limit: int = Query(6, ge=1, le=10),
) -> LiveTopicNewsResponse:
    """주어진 토픽의 캐시된 뉴스를 즉시 반환.

    백그라운드 잡(`refresh_live_news_tick`)이 10분마다 Redis를 갱신하므로
    탭 클릭 시 거의 즉시 응답한다. 캐시 미스(첫 부팅 직후 등)에만 한 번
    라이브 fetch로 폴백 — 그 사이 다른 요청은 lock으로 wait.
    """
    items, _ = await get_cached_topic_news(topic, limit=limit)
    return LiveTopicNewsResponse(
        topic=topic,
        items=[LiveTopicNewsItem(**it) for it in items],
    )


@router.get("/news/{news_id}", response_model=NewsArticleResponse)
async def get_news(
    news_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NewsArticleResponse:
    """기사 상세 조회. is_visible 무관 — 검색이 hidden 기사도 노출하므로
    상세 클릭 시 404 안 나도록 visibility 체크 제거. 행이 존재하면 무조건 반환.
    """
    article = await db.scalar(select(NewsArticle).where(NewsArticle.id == news_id))
    if article is None:
        raise NotFoundError("뉴스를 찾을 수 없습니다")
    return NewsArticleResponse.model_validate(article)


# ---------------------------------------------------------------------------
# 스크랩 폴더 — 사용자가 직접 만드는 분류함
# ---------------------------------------------------------------------------


async def _folder_to_response(db: AsyncSession, folder: ScrapFolder) -> ScrapFolderResponse:
    count = int(
        (
            await db.execute(
                select(func.count()).select_from(Scrap).where(Scrap.folder_id == folder.id)
            )
        ).scalar_one()
        or 0
    )
    return ScrapFolderResponse(
        id=folder.id,
        user_id=folder.user_id,
        name=folder.name,
        color=folder.color,
        scrap_count=count,
        created_at=folder.created_at,
    )


@router.get("/scrap-folders", response_model=list[ScrapFolderResponse])
async def list_scrap_folders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScrapFolderResponse]:
    """내 스크랩 폴더 목록 (각 폴더의 스크랩 개수 포함, 생성 순)."""
    folders = (
        await db.execute(
            select(ScrapFolder)
            .where(ScrapFolder.user_id == user.id)
            .order_by(ScrapFolder.created_at.asc(), ScrapFolder.id.asc())
        )
    ).scalars().all()

    # 폴더별 개수를 한 번의 group-by 쿼리로
    counts = dict(
        (
            await db.execute(
                select(Scrap.folder_id, func.count())
                .where(Scrap.user_id == user.id, Scrap.folder_id.is_not(None))
                .group_by(Scrap.folder_id)
            )
        ).all()
    )
    return [
        ScrapFolderResponse(
            id=f.id,
            user_id=f.user_id,
            name=f.name,
            color=f.color,
            scrap_count=int(counts.get(f.id, 0)),
            created_at=f.created_at,
        )
        for f in folders
    ]


@router.post("/scrap-folders", response_model=ScrapFolderResponse, status_code=201)
async def create_scrap_folder(
    payload: ScrapFolderCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScrapFolderResponse:
    """새 스크랩 폴더 생성. 같은 이름이 이미 있으면 409."""
    name = payload.name.strip()
    if not name:
        raise ConflictError("폴더 이름을 입력해 주세요")

    existing = await db.scalar(
        select(ScrapFolder).where(
            ScrapFolder.user_id == user.id, ScrapFolder.name == name
        )
    )
    if existing is not None:
        raise ConflictError("같은 이름의 폴더가 이미 있습니다")

    folder = ScrapFolder(user_id=user.id, name=name, color=payload.color)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    logger.info(
        "content.scrap_folder_created", extra={"user_id": user.id, "folder_id": folder.id}
    )
    return await _folder_to_response(db, folder)


@router.delete("/scrap-folders/{folder_id}", status_code=204)
async def delete_scrap_folder(
    folder_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """본인 소유 폴더 삭제 — 폴더 안의 스크랩도 함께 삭제(CASCADE)."""
    folder = await db.scalar(
        select(ScrapFolder).where(
            ScrapFolder.id == folder_id, ScrapFolder.user_id == user.id
        )
    )
    if folder is None:
        raise NotFoundError("폴더를 찾을 수 없습니다")
    await db.delete(folder)
    await db.commit()


# ---------------------------------------------------------------------------
# 스크랩 (PR-4) — ScrapAddedEvent 발행으로 다른 동(growth 등)에 알림
# ---------------------------------------------------------------------------


@router.post("/scraps", response_model=ScrapResponse, status_code=201)
async def add_scrap(
    payload: ScrapCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScrapResponse:
    """기사 스크랩 생성.

    - folder_id 지정 시 본인 폴더 검증.
    - article_id가 있으면 DB 기사 검증 + ScrapAddedEvent 발행. 없으면(live RSS)
      스냅샷만으로 저장 (이벤트는 article_id 필수라 생략).
    - 같은 폴더에 같은 기사(article_id 또는 url) 중복 저장은 409.
    """
    # 폴더 소유 검증
    if payload.folder_id is not None:
        folder = await db.scalar(
            select(ScrapFolder).where(
                ScrapFolder.id == payload.folder_id, ScrapFolder.user_id == user.id
            )
        )
        if folder is None:
            raise NotFoundError("폴더를 찾을 수 없습니다")

    # article_id가 있으면 실제 기사 존재 검증
    if payload.article_id is not None:
        article = await db.scalar(
            select(NewsArticle).where(NewsArticle.id == payload.article_id)
        )
        if article is None:
            raise NotFoundError("기사를 찾을 수 없습니다")

    # 같은 폴더 내 중복 방지 (article_id 우선, 없으면 url 기준)
    dup_clause = (
        Scrap.article_id == payload.article_id
        if payload.article_id is not None
        else Scrap.url == payload.url
    )
    existing = await db.scalar(
        select(Scrap).where(
            Scrap.user_id == user.id,
            Scrap.folder_id == payload.folder_id,
            dup_clause,
        )
    )
    if existing is not None:
        raise ConflictError("이미 이 폴더에 스크랩된 기사입니다")

    scrap = Scrap(
        user_id=user.id,
        folder_id=payload.folder_id,
        article_id=payload.article_id,
        title=payload.title,
        url=payload.url,
        image_url=payload.image_url,
        summary=payload.summary,
        source_name=payload.source_name,
        category=payload.category,
        published_at=payload.published_at,
    )
    db.add(scrap)
    await db.commit()
    await db.refresh(scrap)

    if scrap.article_id is not None:
        # core.contracts.ArticleId는 NewType[int] — 그냥 int 전달
        await event_bus.publish(
            ScrapAddedEvent(user_id=user.id, article_id=scrap.article_id)  # type: ignore[arg-type]
        )
    logger.info(
        "content.scrap_added",
        extra={"user_id": user.id, "scrap_id": scrap.id, "folder_id": scrap.folder_id},
    )

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
    folder_id: int | None = Query(None, description="폴더 필터 — 지정 시 해당 폴더만"),
    limit: int = Query(50, ge=1, le=200),
) -> list[ScrapResponse]:
    """내 스크랩 목록 (최신 순). folder_id 지정 시 그 폴더 안의 스크랩만."""
    stmt = select(Scrap).where(Scrap.user_id == user.id)
    if folder_id is not None:
        stmt = stmt.where(Scrap.folder_id == folder_id)
    rows = (
        await db.execute(stmt.order_by(desc(Scrap.created_at)).limit(limit))
    ).scalars().all()
    return [ScrapResponse.model_validate(s) for s in rows]


@router.get("/scraps/exists", response_model=ScrapExistsResponse)
async def check_scrap_exists(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    article_id: int | None = Query(None, description="DB 기사 id"),
    url: str | None = Query(None, description="기사 원문 url (live RSS 등 article_id 없는 경우)"),
) -> ScrapExistsResponse:
    """이 사용자가 해당 기사를 스크랩했는지 단건 판정.

    article_id 우선, 없으면 url로 매칭. 둘 다 없으면 exists=False.
    전체 목록 조회 + 클라이언트 매칭(limit 상한에 걸려 누락 가능)을 대체한다.
    """
    clauses = []
    if article_id is not None:
        clauses.append(Scrap.article_id == article_id)
    if url:
        clauses.append(Scrap.url == url)
    if not clauses:
        return ScrapExistsResponse(exists=False)

    found = await db.scalar(
        select(Scrap.id).where(Scrap.user_id == user.id, or_(*clauses)).limit(1)
    )
    return ScrapExistsResponse(exists=found is not None)


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


@router.post("/admin/refresh-images")
async def refresh_images(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="이번 호출에서 재추출할 기사 수"),
) -> dict:
    """image_url IS NULL 인 기사에 대해 ContentExtractor를 다시 돌려 이미지 backfill.

    동작:
      1. image_url이 비어있는 기사 `limit`개 선택 (오래된 것부터)
      2. 각 기사 original_url에 대해 content_extractor.extract() 호출
         (publisher 페이지 fetch + JSON-LD/og:image/article img 추출)
      3. 추출 성공한 경우만 image_url UPDATE
      4. 추출 실패한 행은 그냥 두고 다음 호출에서 재시도 가능

    각 호출은 extractor 내부 세마포어(max_concurrency=6)로 동시 HTTP 6개로 제한.
    호출 한 번에 limit=50이면 ~30초 정도 걸림 (사이트별 응답 시간 따라).
    """
    from .extractor import content_extractor

    stmt = (
        select(NewsArticle)
        .where(
            (NewsArticle.image_url.is_(None)) | (NewsArticle.image_url == ""),
        )
        .order_by(NewsArticle.id.asc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return {"scanned": 0, "updated": 0}

    # 병렬 fetch — extractor 내부 세마포어가 max 6개 제한
    async def _one(art: NewsArticle):
        try:
            _body, image_url, _resolved = await content_extractor.extract(art.original_url)
            return art, image_url
        except Exception:
            return art, None

    outcomes = await asyncio.gather(*[_one(a) for a in rows])

    updated = 0
    for art, new_image in outcomes:
        if new_image:
            art.image_url = new_image
            updated += 1
    await db.commit()
    logger.info(
        "content.admin.images_refreshed",
        extra={"user_id": user.id, "scanned": len(rows), "updated": updated},
    )
    return {"scanned": len(rows), "updated": updated}


@router.post("/admin/process-ai-now")
async def process_ai_now(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=200, description="이번 호출에서 처리할 pending 최대"),
    parallelism: int = Query(10, ge=1, le=20, description="동시 LLM 호출 수"),
) -> dict:
    """다음 5분 tick을 기다리지 않고 pending 큐에서 batch 처리 즉시 실행.

    backfill 직후 또는 수집기 첫 가동 직후 큐가 폭발했을 때 사용. 호출 한 번에
    `limit`만큼 처리 시도 — 결과 반환되면 다시 호출하면 됨. 병렬 호출은 OK
    (각 호출이 자기 batch를 'processing'으로 즉시 마킹해서 lock 효과).
    """
    stats = await content_service.process_pending_ai(
        db, limit=limit, parallelism=parallelism
    )
    logger.info("content.admin.ai_processed_now", extra={"user_id": user.id, **stats})
    return stats


@router.post("/admin/make-all-visible")
async def make_all_visible(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """수집된 모든 기사를 is_visible=True로 일괄 전환 (점수 무관).

    임계값 기반 큐레이션을 우회하고 싶을 때 사용. 검색·피드에서 모든 기사를
    그대로 노출하게 됨. 신규 수집분은 여전히 임계값 적용되므로, 새 기사를
    계속 보이게 하려면 CONTENT_VISIBLE_THRESHOLD를 0으로 낮추는 게 더 영속적.
    """
    result = await db.execute(
        sa_update(NewsArticle)
        .where(NewsArticle.is_visible.is_(False))
        .values(is_visible=True)
    )
    promoted = result.rowcount or 0
    await db.commit()
    total = int(
        (
            await db.execute(select(func.count()).select_from(NewsArticle))
        ).scalar_one()
        or 0
    )
    logger.info(
        "content.admin.make_all_visible",
        extra={"user_id": user.id, "promoted": promoted, "total": total},
    )
    return {"promoted": promoted, "total_visible": total}


@router.post("/admin/reapply-thresholds")
async def reapply_thresholds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """현재 환경변수 임계값을 기존 모든 기사에 다시 적용 (점수 재계산 X).

    is_visible / is_rag_eligible / ai_processing_status('skipped'→'pending')만
    갱신. 임계값을 .env에서 바꾼 직후 한 번 호출하면 그동안 'skipped'에 묶여
    있던 행들이 즉시 AI 큐로 승격되고, 노출 가능 풀도 즉시 늘어남.

    Response:
        {
            "thresholds": {"visible": N, "rag": M},
            "promoted_skipped_to_pending": int,
            "visible_now": int,
            "rag_eligible_now": int,
            "ai_pending_now": int
        }
    """
    stats = await content_service.reapply_thresholds(db)
    logger.info(
        "content.admin.thresholds_reapplied",
        extra={"user_id": user.id, **stats},
    )
    return stats


@router.post("/admin/retry-failed")
async def retry_failed_ai(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="한 번에 reset할 최대 행 수"),
) -> dict:
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
