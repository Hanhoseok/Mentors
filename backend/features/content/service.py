"""콘텐츠 동 비즈니스 로직.

흐름:
  1. (jobs.py)    @interval로 ContentService.run_collection()을 부름
  2. ingest_articles: 수집기 fan-out → dedup → reliability → DB 저장 (pending)
  3. process_pending_ai: 큐에서 pending을 꺼내 core.llm으로 번역·요약·전략 매핑
  4. index_for_rag: is_rag_eligible 기사를 청크화 → core.vector_store에 upsert

규칙 (AGENTS.md):
  - core.llm / core.vector_store / core.db 사용. 외부 SDK 직접 사용 금지.
  - 모든 DB 호출 async.
  - 사용자 PII 로깅 금지 (user_id만 가능, 본 service는 user_id를 다루지 않음).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.contracts import MentorStrategy, MessageRole
from core.exceptions import ExternalServiceError
from core.llm import Message, llm
from core.vector_store import Document, vector_store

from . import pipeline_utils as pu
from .collectors import FinnhubCollector, GoogleNewsRSSCollector
from .models import ArticleKeyword, KnowledgeChunk, MasterKeyword, NewsArticle
from .schemas import AIProcessingResult, ArticleRaw

logger = logging.getLogger("content.service")

# Chroma 컬렉션 — RAG 청크가 이 컬렉션에 들어감. core.ai_pipeline.rag가 같은
# 이름으로 검색하면 매끄럽게 콘텐츠 동 데이터에 접근 가능.
RAG_COLLECTION = "content_news_kb"

# RAG 인덱싱 임계값 — 신뢰도가 이 점수 이상이어야 벡터 저장
RAG_ELIGIBILITY_THRESHOLD = 60
# 노출 임계값 — 사용자에게 보이려면 이 점수 이상
VISIBLE_THRESHOLD = 70
# 청크 길이 (토큰 기준 아니라 문자 기준 — 근사치)
CHUNK_CHAR_LEN = 800
CHUNK_OVERLAP_CHAR = 100


class ContentService:
    """수집 → AI → RAG 인덱싱 오케스트레이션. 싱글톤 사용 (jobs.py에서 인스턴스 생성)."""

    def __init__(self) -> None:
        self._collectors = [GoogleNewsRSSCollector(), FinnhubCollector()]

    # ------------------------------------------------------------------
    # 1. Collection — 키워드 풀 순회 + dedup + DB 저장
    # ------------------------------------------------------------------

    async def run_collection(self, session: AsyncSession, *, max_keywords: int = 25) -> dict[str, int]:
        """한 tick: 활성 master_keyword를 우선순위·last_run_at 순으로 N개 가져와
        각각 수집기 fan-out. dedup + 신뢰도 + AI큐 저장까지."""
        keywords = await self._pick_keywords(session, limit=max_keywords)
        if not keywords:
            logger.info("content.collection_skipped", extra={"reason": "no_active_keywords"})
            return {"keywords": 0, "fetched": 0, "saved": 0, "duplicates": 0}

        fetched_total = 0
        saved_total = 0
        dup_total = 0

        for kw in keywords:
            raws = await self._fetch_for_keyword(kw.keyword, max_per_collector=5)
            fetched_total += len(raws)
            saved, dups = await self._persist_articles(session, raws, master_keyword=kw)
            saved_total += saved
            dup_total += dups

            kw.last_run_at = datetime.now(timezone.utc)

        await session.commit()
        logger.info(
            "content.collection_done",
            extra={
                "keywords": len(keywords),
                "fetched": fetched_total,
                "saved": saved_total,
                "duplicates": dup_total,
            },
        )
        return {
            "keywords": len(keywords),
            "fetched": fetched_total,
            "saved": saved_total,
            "duplicates": dup_total,
        }

    async def _pick_keywords(self, session: AsyncSession, *, limit: int) -> list[MasterKeyword]:
        stmt = (
            select(MasterKeyword)
            .where(MasterKeyword.is_active.is_(True))
            .order_by(MasterKeyword.last_run_at.asc().nulls_first(), MasterKeyword.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_for_keyword(self, keyword: str, *, max_per_collector: int) -> list[ArticleRaw]:
        out: list[ArticleRaw] = []
        for collector in self._collectors:
            items = await collector.collect_safe(keyword, max_items=max_per_collector)
            out.extend(items)
        return out

    async def _persist_articles(
        self,
        session: AsyncSession,
        raws: Iterable[ArticleRaw],
        *,
        master_keyword: MasterKeyword,
    ) -> tuple[int, int]:
        """dedup → 신뢰도 → DB row 생성. (saved_count, dup_count)"""
        saved = 0
        dups = 0

        for raw in raws:
            canonical = pu.canonicalize_url(raw.url)
            existing = await session.scalar(
                select(NewsArticle).where(NewsArticle.canonical_url == canonical)
            )
            if existing is not None:
                dups += 1
                # 키워드 태그만 추가 (이미 있는 기사라도 새 키워드로 트리거됐을 수 있음)
                await self._tag_article(session, existing.id, master_keyword.id)
                continue

            score, level, reason = pu.reliability_score(
                source_name=raw.source_name,
                content=raw.content,
                published_at=raw.published_at,
                title=raw.title,
            )
            economy = pu.is_economy(raw.title, raw.content, raw.language)
            strategies = pu.classify_strategies(raw.title, raw.content)

            article = NewsArticle(
                source_name=raw.source_name,
                source_channel=raw.source_channel,
                original_url=raw.url,
                canonical_url=canonical,
                language=raw.language,
                title_original=raw.title,
                content=raw.content,
                published_at=raw.published_at,
                image_url=raw.image_url,
                reliability_score=score,
                reliability_level=level,
                reliability_reason=reason,
                composite_score=float(score),
                is_economy=economy,
                strategies=",".join(s.value for s in strategies) if strategies else None,
                is_visible=score >= VISIBLE_THRESHOLD,
                is_rag_eligible=score >= RAG_ELIGIBILITY_THRESHOLD,
                ai_processing_status="pending" if score >= RAG_ELIGIBILITY_THRESHOLD else "skipped",
            )
            session.add(article)
            await session.flush()  # need PK for tag
            await self._tag_article(session, article.id, master_keyword.id)
            saved += 1

        return saved, dups

    async def _tag_article(self, session: AsyncSession, article_id: int, master_keyword_id: int) -> None:
        existing = await session.scalar(
            select(ArticleKeyword).where(
                and_(
                    ArticleKeyword.article_id == article_id,
                    ArticleKeyword.master_keyword_id == master_keyword_id,
                )
            )
        )
        if existing is None:
            session.add(ArticleKeyword(article_id=article_id, master_keyword_id=master_keyword_id))

    # ------------------------------------------------------------------
    # 2. AI 처리 — 번역 + 요약 + 키워드 + 전략 한 호출
    # ------------------------------------------------------------------

    async def process_pending_ai(
        self, session: AsyncSession, *, limit: int = 40
    ) -> dict[str, int]:
        """ai_processing_status='pending' 기사들을 한 번에 처리."""
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.ai_processing_status == "pending")
            .order_by(NewsArticle.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        completed = 0
        failed = 0
        for article in rows:
            article.ai_processing_status = "processing"
            try:
                res = await self._ai_for_article(article)
                self._apply_ai_result(article, res)
                article.ai_processing_status = res.status
                if res.error:
                    article.ai_error = res.error
                article.processed_at = datetime.now(timezone.utc)
                if res.status == "completed":
                    completed += 1
                else:
                    failed += 1
            except Exception as e:  # noqa: BLE001
                logger.exception("content.ai_failed", extra={"article_id": article.id})
                article.ai_processing_status = "failed"
                article.ai_error = str(e)[:500]
                failed += 1

        await session.commit()
        return {"processed": len(rows), "completed": completed, "failed": failed}

    async def _ai_for_article(self, article: NewsArticle) -> AIProcessingResult:
        """단일 LLM 호출로 번역·요약·키워드·전략 매핑 + sentiment 추출.

        프롬프트는 JSON 출력을 강제하고, 파싱 실패 시 status='failed'.
        """
        if not llm.configured:
            raise ExternalServiceError("LLM not configured")

        system = (
            "너는 경제 뉴스 정리 AI다. 입력 기사를 한국어로 번역하고 핵심 3줄로 요약한다. "
            "결과는 반드시 JSON으로만 출력한다. 다른 텍스트 금지.\n"
            'JSON 형식: {"title_ko": str, "content_ko": str, "summary_ko": str, '
            '"keywords": list[str] (최대 5개), "sentiment": "positive"|"neutral"|"negative", '
            '"investment_relevance": "high"|"medium"|"low", '
            '"strategies": list of "value"|"growth"|"dividend"|"momentum"}'
        )
        body = (article.content or "")[:6000]
        user_content = (
            f"제목: {article.title_original}\n"
            f"출처: {article.source_name or 'unknown'}\n"
            f"본문:\n{body}"
        )

        response = await llm.chat(
            messages=[
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user_content),
            ],
            temperature=0.2,
            max_tokens=900,
            response_format="json",
            use_case="content",
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            # JSON 추출 fallback
            data = self._extract_json(response.text)
            if data is None:
                return AIProcessingResult(status="failed", error="json_parse_failed")

        return AIProcessingResult(
            status="completed",
            translated_title_ko=str(data.get("title_ko") or ""),
            translated_content_ko=str(data.get("content_ko") or ""),
            summary_ko=str(data.get("summary_ko") or ""),
            keywords=[str(k) for k in (data.get("keywords") or [])][:5],
            sentiment=self._safe_enum(data.get("sentiment"), {"positive", "neutral", "negative"}),
            investment_relevance=self._safe_enum(
                data.get("investment_relevance"), {"high", "medium", "low"}
            ),
            strategies=self._parse_strategies(data.get("strategies")),
            detected_language=article.language,
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _safe_enum(value: Any, allowed: set[str]) -> Any:
        return value if isinstance(value, str) and value in allowed else None

    @staticmethod
    def _parse_strategies(value: Any) -> list[MentorStrategy]:
        if not isinstance(value, list):
            return []
        out: list[MentorStrategy] = []
        for raw in value:
            try:
                out.append(MentorStrategy(str(raw).lower()))
            except ValueError:
                continue
        return out

    @staticmethod
    def _apply_ai_result(article: NewsArticle, res: AIProcessingResult) -> None:
        if res.translated_title_ko:
            article.title_translated = res.translated_title_ko
        if res.translated_content_ko:
            article.content_translated = res.translated_content_ko
        if res.summary_ko:
            article.summary_ko = res.summary_ko
        if res.keywords:
            article.ai_keywords = json.dumps(res.keywords, ensure_ascii=False)
        if res.sentiment:
            article.ai_sentiment = res.sentiment
        if res.investment_relevance:
            article.ai_investment_relevance = res.investment_relevance
        if res.strategies:
            # AI가 추정한 전략으로 규칙기반 1차 추정을 덮어씀
            article.strategies = ",".join(s.value for s in res.strategies)

    # ------------------------------------------------------------------
    # 3. RAG 인덱싱 — core.vector_store에 청크 upsert
    # ------------------------------------------------------------------

    async def index_for_rag(self, session: AsyncSession, *, limit: int = 50) -> dict[str, int]:
        """is_rag_eligible=True + ai_processing_status='completed' + 미인덱싱
        기사를 청크화하여 core.vector_store에 upsert."""
        stmt = (
            select(NewsArticle)
            .outerjoin(KnowledgeChunk)
            .where(
                NewsArticle.is_rag_eligible.is_(True),
                NewsArticle.ai_processing_status == "completed",
                KnowledgeChunk.id.is_(None),
            )
            .order_by(NewsArticle.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        candidates = list(result.scalars().unique().all())

        indexed = 0
        for article in candidates:
            chunks = self._chunk_text(article)
            if not chunks:
                continue

            chunk_rows: list[KnowledgeChunk] = []
            docs: list[Document] = []
            for idx, text in enumerate(chunks):
                ref = f"article-{article.id}-chunk-{idx}"
                chunk_rows.append(
                    KnowledgeChunk(
                        article_id=article.id,
                        chunk_index=idx,
                        chunk_text=text,
                        token_count=len(text) // 4,  # rough approx
                        vector_store_ref=ref,
                    )
                )
                docs.append(
                    Document(
                        id=ref,
                        text=text,
                        metadata={
                            "article_id": article.id,
                            "source": article.source_name or "",
                            "url": article.original_url,
                            "published_at": article.published_at.isoformat()
                            if article.published_at
                            else "",
                            "reliability_score": article.reliability_score,
                            "strategies": article.strategies or "",
                        },
                    )
                )

            try:
                await vector_store.upsert(RAG_COLLECTION, docs)
            except Exception:
                logger.exception("content.rag_upsert_failed", extra={"article_id": article.id})
                continue

            for row in chunk_rows:
                session.add(row)
            indexed += 1

        await session.commit()
        return {"scanned": len(candidates), "indexed": indexed}

    @staticmethod
    def _chunk_text(article: NewsArticle) -> list[str]:
        """기사 본문을 CHUNK_CHAR_LEN 단위로 슬라이딩 윈도우 청킹."""
        body = article.content_translated or article.content or article.summary_ko or ""
        body = pu.strip_html(body)
        if len(body) < 200:
            return []

        chunks: list[str] = []
        step = CHUNK_CHAR_LEN - CHUNK_OVERLAP_CHAR
        for start in range(0, len(body), step):
            chunk = body[start : start + CHUNK_CHAR_LEN].strip()
            if chunk:
                chunks.append(chunk)
            if len(chunk) < CHUNK_CHAR_LEN:
                break
        return chunks


# Singleton
content_service = ContentService()


__all__ = ["ContentService", "RAG_COLLECTION", "content_service"]
