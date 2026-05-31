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
import os
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.contracts import MentorStrategy, MessageRole
from core.exceptions import ExternalServiceError
from core.llm import Message, llm
from core.vector_store import Document, vector_store

from . import pipeline_utils as pu
from .collectors import FinnhubCollector, GoogleNewsRSSCollector
from .extractor import content_extractor
from .models import (
    ArticleKeyword,
    KnowledgeChunk,
    MasterKeyword,
    MasterKeywordCompany,
    NewsArticle,
)
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

# Priority-tier 스케줄러 캡 (newspipeline 기본값 유지, env override 가능).
# 한 tick에서 fan-out할 회사 query의 상한 — P0가 P1+를 starve하지 않도록.
_TIER_CAP = {
    "P0": int(os.getenv("MAX_P0_PER_TICK", "15")),
    "P1": int(os.getenv("MAX_P1_PER_TICK", "12")),
    "P2": int(os.getenv("MAX_P2_PER_TICK", "8")),
    "P3": int(os.getenv("MAX_P3_PER_TICK", "5")),
}
_GLOBAL_CAP = max(1, int(os.getenv("MAX_KEYWORDS_PER_TICK", "40")))
_COMPANIES_PER_KEYWORD = int(os.getenv("COMPANIES_PER_KEYWORD", "5"))

# AI 처리 중 process crash / 외부 timeout 등으로 status가 'processing'에 stuck된 행
# 을 N분 후 자동으로 'pending'으로 복구. process_pending_ai 시작 시 매번 실행.
_AI_PROCESSING_STUCK_MINUTES = int(os.getenv("AI_PROCESSING_STUCK_MINUTES", "15"))


class ContentService:
    """수집 → AI → RAG 인덱싱 오케스트레이션. 싱글톤 사용 (jobs.py에서 인스턴스 생성)."""

    def __init__(self) -> None:
        self._collectors = [GoogleNewsRSSCollector(), FinnhubCollector()]

    # ------------------------------------------------------------------
    # 1. Collection — 키워드 풀 순회 + dedup + DB 저장
    # ------------------------------------------------------------------

    async def run_collection(
        self, session: AsyncSession, *, max_keywords: int | None = None
    ) -> dict[str, int]:
        """한 tick: priority-tier 스케줄러로 due master_keywords를 뽑고,
        각 master 안에서 회사를 회전(`last_fetched_at` asc) 시키며 검색.

        - master_keyword.companies가 있으면 회사명으로 검색 (정확도 ↑)
        - 없으면 키워드 텍스트로 폴백
        - tick 후 master.last_run_at + next_run_at 스탬프, company.last_fetched_at 스탬프
        """
        global_cap = max_keywords if max_keywords is not None else _GLOBAL_CAP
        targets = await self._load_due_targets(session, global_cap=global_cap)
        if not targets:
            logger.info("content.collection_skipped", extra={"reason": "no_due_targets"})
            return {"keywords": 0, "fetched": 0, "saved": 0, "duplicates": 0}

        fetched_total = 0
        saved_total = 0
        dup_total = 0

        masters_used: dict[int, MasterKeyword] = {}
        for target in targets:
            master: MasterKeyword = target["master"]
            masters_used[master.id] = master
            query = target["query"]
            max_articles = int(target["max_articles"])

            raws = await self._fetch_query(query, max_per_collector=max_articles)
            fetched_total += len(raws)
            saved, dups = await self._persist_articles(session, raws, master_keyword=master)
            saved_total += saved
            dup_total += dups

            company: MasterKeywordCompany | None = target.get("company")
            if company is not None:
                company.last_fetched_at = datetime.now(UTC)

        # tick 후 master 스케줄 스탬프 — 한 master가 여러 회사를 fanout 했어도 한 번만
        now = datetime.now(UTC)
        for master in masters_used.values():
            master.last_run_at = now
            master.next_run_at = now + timedelta(minutes=master.collection_interval_minutes or 60)

        await session.commit()
        logger.info(
            "content.collection_done",
            extra={
                "keywords": len(masters_used),
                "queries": len(targets),
                "fetched": fetched_total,
                "saved": saved_total,
                "duplicates": dup_total,
            },
        )
        return {
            "keywords": len(masters_used),
            "queries": len(targets),
            "fetched": fetched_total,
            "saved": saved_total,
            "duplicates": dup_total,
        }

    async def _load_due_targets(
        self, session: AsyncSession, *, global_cap: int
    ) -> list[dict[str, Any]]:
        """priority-tier scheduler. 반환: [{"master": MasterKeyword, "query": str,
        "max_articles": int, "company": MasterKeywordCompany | None}, ...]

        - is_active=True
        - next_run_at IS NULL OR next_run_at <= now (없으면 기본 통과 — 첫 tick)
        - priority asc, next_run_at asc nullsfirst
        - 각 tier 캡 적용 후 master당 top-N companies (last_fetched_at asc)
        """
        now = datetime.now(UTC)
        stmt = (
            select(MasterKeyword)
            .options(selectinload(MasterKeyword.companies))
            .where(
                MasterKeyword.is_active.is_(True),
                (MasterKeyword.next_run_at.is_(None)) | (MasterKeyword.next_run_at <= now),
            )
            .order_by(
                MasterKeyword.priority.asc(),
                MasterKeyword.next_run_at.asc().nulls_first(),
            )
            .limit(global_cap * 3)
        )
        candidates = list((await session.execute(stmt)).scalars().all())

        seen_per_tier: dict[str, int] = defaultdict(int)
        selected_masters: list[MasterKeyword] = []
        for mkw in candidates:
            tier = mkw.priority or "P2"
            if seen_per_tier[tier] >= _TIER_CAP.get(tier, 5):
                continue
            selected_masters.append(mkw)
            seen_per_tier[tier] += 1
            if len(selected_masters) >= global_cap:
                break

        if not selected_masters:
            return []

        targets: list[dict[str, Any]] = []
        for mkw in selected_masters:
            companies = list(mkw.companies)
            # 회사가 있으면 last_fetched_at asc로 회전, NULL(미수집) 우선
            if companies:
                companies.sort(
                    key=lambda c: (
                        c.last_fetched_at or datetime.min.replace(tzinfo=UTC),
                        c.priority or 999,
                    )
                )
                for company in companies[:_COMPANIES_PER_KEYWORD]:
                    targets.append(
                        {
                            "master": mkw,
                            "query": company.company_name,
                            "max_articles": mkw.max_articles_per_run or 3,
                            "company": company,
                        }
                    )
            else:
                # 회사 매핑 없는 매크로 키워드(탄소배출권 등): 키워드 텍스트로 검색
                targets.append(
                    {
                        "master": mkw,
                        "query": mkw.keyword,
                        "max_articles": mkw.max_articles_per_run or 3,
                        "company": None,
                    }
                )

        return targets

    async def _fetch_query(self, query: str, *, max_per_collector: int) -> list[ArticleRaw]:
        """단일 쿼리(회사명 또는 키워드 텍스트)로 모든 collector fan-out."""
        out: list[ArticleRaw] = []
        for collector in self._collectors:
            items = await collector.collect_safe(query, max_items=max_per_collector)
            out.extend(items)
        return out

    async def _persist_articles(
        self,
        session: AsyncSession,
        raws: Iterable[ArticleRaw],
        *,
        master_keyword: MasterKeyword,
    ) -> tuple[int, int]:
        """dedup → 본문 재추출 → 2차 dedup → 신뢰도 → DB row 생성. (saved_count, dup_count).

        RSS 본문은 메타데이터 스니펫이라 신뢰도/요약 품질이 낮음. 따라서:
          1. raw.url canonical로 1차 dedup (fetch 회피 — 같은 raw URL은 즉시 skip)
          2. ContentExtractor로 풀 본문 + og:image + resolved_url 재추출
          3. resolved_url이 raw.url과 다르면 publisher canonical로 2차 dedup —
             같은 publisher 기사를 가리키는 서로 다른 Google News URL의 중복 row 방지
          4. 풀 본문으로 reliability_score 재계산
          5. NewsArticle INSERT (canonical_url = publisher canonical 우선, 없으면 raw canonical)

        2차 dedup 효과:
          - Google News는 같은 publisher 기사를 여러 redirector URL로 노출하기 때문에
            1차 dedup만으로는 중복이 새어 들어옴. 2차 dedup이 fetch 후 resolved_url로
            재확인해서 동일 publisher article은 한 row만 유지.
          - canonical_url을 publisher 값으로 저장 → 다음 tick에서 또 다른 Google News URL이
            들어오면 1차 dedup에서 한 번에 매칭 (fetch 횟수 감소).
        """
        saved = 0
        dups = 0

        for raw in raws:
            canonical = pu.canonicalize_url(raw.url)

            # ---- 1차 dedup: raw.url canonical ----
            existing = await session.scalar(
                select(NewsArticle).where(NewsArticle.canonical_url == canonical)
            )
            if existing is not None:
                dups += 1
                # 키워드 태그만 추가 (이미 있는 기사라도 새 키워드로 트리거됐을 수 있음)
                await self._tag_article(session, existing.id, master_keyword.id)
                continue

            # ---- 풀 본문 + 대표 이미지 + resolved_url 재추출 (실패 시 raw fallback) ----
            extracted_body, extracted_image, resolved_url = await content_extractor.extract(raw.url)
            content = extracted_body or raw.content
            image_url = extracted_image or raw.image_url

            # ---- 2차 dedup: Google News URL → publisher URL canonical ----
            # resolved_url이 raw.url과 다르면 publisher canonical 재계산해서 한 번 더 체크.
            # 같은 publisher 기사를 가리키는 다른 Google News URL이 이미 저장됐다면 skip.
            if resolved_url and resolved_url != raw.url:
                publisher_canonical = pu.canonicalize_url(resolved_url)
                if publisher_canonical != canonical:
                    existing_by_resolved = await session.scalar(
                        select(NewsArticle).where(NewsArticle.canonical_url == publisher_canonical)
                    )
                    if existing_by_resolved is not None:
                        dups += 1
                        await self._tag_article(session, existing_by_resolved.id, master_keyword.id)
                        continue
                    # 신규 row의 canonical_url을 publisher 값으로 저장
                    # → 다음 tick에서 또 다른 Google News URL이 와도 1차 dedup에서 매칭
                    canonical = publisher_canonical

            score, level, reason = pu.reliability_score(
                source_name=raw.source_name,
                content=content,
                published_at=raw.published_at,
                title=raw.title,
            )
            economy = pu.is_economy(raw.title, content, raw.language)
            strategies = pu.classify_strategies(raw.title, content)

            article = NewsArticle(
                source_name=raw.source_name,
                source_channel=raw.source_channel,
                original_url=raw.url,
                canonical_url=canonical,
                language=raw.language,
                title_original=raw.title,
                content=content,
                published_at=raw.published_at,
                image_url=image_url,
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

    async def _tag_article(
        self, session: AsyncSession, article_id: int, master_keyword_id: int
    ) -> None:
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

    async def reset_failed_to_pending(
        self, session: AsyncSession, *, limit: int = 100
    ) -> dict[str, Any]:
        """`ai_processing_status='failed'` 기사를 'pending'으로 되돌림.

        다음 ai_process_tick(5분마다)이 자동으로 재처리 시도. 즉시 처리는
        하지 않음 — 응답 빠르게 반환 + scheduler에 위임.

        Returns:
            {"reset": N, "sample": [{"id": ..., "title": ..., "ai_error": ...}, ...]}
        """
        # 먼저 reset 대상 샘플 (응답에 포함, 디버깅 용)
        sample_stmt = (
            select(NewsArticle)
            .where(NewsArticle.ai_processing_status == "failed")
            .order_by(NewsArticle.processed_at.asc().nulls_first())
            .limit(min(limit, 10))
        )
        sample_rows = list((await session.execute(sample_stmt)).scalars().all())
        sample = [
            {
                "id": a.id,
                "title": (a.title_original or "")[:80],
                "ai_error": (a.ai_error or "")[:120],
            }
            for a in sample_rows
        ]

        # 실제 reset — 가장 오래된 failed부터 limit 개
        reset_ids_stmt = (
            select(NewsArticle.id)
            .where(NewsArticle.ai_processing_status == "failed")
            .order_by(NewsArticle.processed_at.asc().nulls_first())
            .limit(limit)
        )
        ids = [row for row in (await session.execute(reset_ids_stmt)).scalars().all()]
        if not ids:
            return {"reset": 0, "sample": []}

        from sqlalchemy import update

        await session.execute(
            update(NewsArticle)
            .where(NewsArticle.id.in_(ids))
            .values(ai_processing_status="pending", ai_error=None)
        )
        await session.commit()
        logger.info("content.ai_retry_reset", extra={"reset": len(ids)})
        return {"reset": len(ids), "sample": sample}

    async def _recover_stuck(self, session: AsyncSession) -> int:
        """`processing` 상태가 _AI_PROCESSING_STUCK_MINUTES 이상이면 pending으로 복구.

        AI 호출 도중 process crash / 네트워크 timeout 등으로 status 업데이트 못 하고
        종료되면 행이 영원히 'processing'에 stuck. 매 tick 시작 시 이 메서드가 좀비
        행을 자동 회수해서 pending으로 되돌림 → 다음 처리 사이클에서 재시도.

        newspipeline ai_worker.recover_stuck과 동등 (mentors-port async 버전).
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=_AI_PROCESSING_STUCK_MINUTES)
        result = await session.execute(
            update(NewsArticle)
            .where(
                NewsArticle.ai_processing_status == "processing",
                NewsArticle.updated_at < cutoff,
            )
            .values(
                ai_processing_status="pending",
                ai_error=f"recovered_after_{_AI_PROCESSING_STUCK_MINUTES}m_stuck",
            )
        )
        # SQLAlchemy Result[Any]에 rowcount 노출되지만 mypy strict가 못 봄 — getattr로 우회.
        recovered = int(getattr(result, "rowcount", 0) or 0)
        if recovered:
            logger.warning(
                "content.ai_stuck_recovered",
                extra={"count": recovered, "threshold_min": _AI_PROCESSING_STUCK_MINUTES},
            )
        return recovered

    async def process_pending_ai(self, session: AsyncSession, *, limit: int = 40) -> dict[str, int]:
        """ai_processing_status='pending' 기사들을 한 번에 처리.

        매 tick 시작 시 _recover_stuck로 좀비 행(processing > 15분)을 pending으로
        자동 복구 → 다음 사이클에서 재처리 보장.
        """
        # 1) Stuck recovery (자동, 매 tick) — newspipeline 동등 패턴
        recovered = await self._recover_stuck(session)

        # 2) Pending 처리
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
                article.processed_at = datetime.now(UTC)
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
        return {
            "recovered": recovered,
            "processed": len(rows),
            "completed": completed,
            "failed": failed,
        }

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
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        # json.loads는 Any 반환 — dict 확정 narrowing
        if not isinstance(parsed, dict):
            return None
        return parsed

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
