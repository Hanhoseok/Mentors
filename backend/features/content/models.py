"""콘텐츠 동 SQLAlchemy 모델 (async).

규칙 (AGENTS.md §3, §6.1):
  - core.db.Base 사용
  - 자기 동 외부에서 직접 import 금지 — 다른 동은 read_service를 통해 접근
  - 새 컬럼 추가 시 Alembic 마이그레이션 동반

구조 (newspipeline/core/db/models.py 도메인을 mentors 컨벤션으로 이식):

  Industry ──< IndustryKeyword ──< MasterKeyword ──< MasterKeywordCompany
                                          │
                                          ├──< ArticleKeyword (composite PK)
                                          └──< UserKeyword (M:N, user_id=BigInt FK users.id)

  NewsSource ──< NewsArticle ──< KnowledgeChunk
                       │
                       └── duplicate_of_article_id (self FK)
                       └──< ArticleKeyword
                       └──< Scrap (user_id=BigInt FK users.id)

  PipelineRun (수집 로그, 독립)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base

# ---------------------------------------------------------------------------
# 뉴스 출처 카탈로그
# ---------------------------------------------------------------------------


class NewsSource(Base):
    """뉴스 출처 — RSS feed, Finnhub API, SEC EDGAR 등."""

    __tablename__ = "content_news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))  # rss / api / web / sec
    base_url: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(10), default="en")
    country: Mapped[str] = mapped_column(String(10), default="US")
    reliability_base_score: Mapped[int] = mapped_column(Integer, default=30)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=10)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    articles: Mapped[list[NewsArticle]] = relationship(back_populates="source")


# ---------------------------------------------------------------------------
# 산업 분류 (UI 카테고리) + 산업 하부 키워드 라벨
# ---------------------------------------------------------------------------


class Industry(Base):
    """산업 카테고리 — UI에서 그리드/탭으로 노출."""

    __tablename__ = "content_industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ko: Mapped[str] = mapped_column(String(100), unique=True)
    name_en: Mapped[str] = mapped_column(String(100))
    display_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    keywords: Mapped[list[IndustryKeyword]] = relationship(
        back_populates="industry", cascade="all, delete-orphan"
    )


class IndustryKeyword(Base):
    """산업 하부 키워드 — 사용자가 산업 카드 안에서 선택하는 라벨.

    실제 수집 키워드(MasterKeyword)와 1:N. label_ko는 UI 표시용 한국어,
    keyword_en은 영문 검색용.
    """

    __tablename__ = "content_industry_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry_id: Mapped[int] = mapped_column(
        ForeignKey("content_industries.id", ondelete="CASCADE"), index=True
    )
    label_ko: Mapped[str] = mapped_column(String(200))
    keyword_en: Mapped[str] = mapped_column(String(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    industry: Mapped[Industry] = relationship(back_populates="keywords")
    master_keywords: Mapped[list[MasterKeyword]] = relationship(
        back_populates="industry_keyword"
    )

    __table_args__ = (
        UniqueConstraint("industry_id", "label_ko", name="uq_content_industry_keyword_label"),
    )


# ---------------------------------------------------------------------------
# 마스터 키워드 풀
# ---------------------------------------------------------------------------


class MasterKeyword(Base):
    """글로벌 키워드 풀. PR-3 수집기가 priority/slot/next_run_at 기반으로 순회.

    `source` 분류:
      - 'industry': IndustryKeyword에서 자동 시딩 (industry_keyword_id 보유)
      - 'ticker':  SEC ticker 검색으로 추가된 회사명
      - 'manual':  관리자/사용자 직접 추가
      - 'onboarding': OnboardingCompletedEvent 핸들러가 시딩

    스케줄링 컬럼은 PR-3에서 활용. PR-2 시점에는 server_default로 채워짐.
    """

    __tablename__ = "content_master_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(10), default="auto")
    source: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    industry_keyword_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_industry_keywords.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # 스케줄링 (PR-3 collector)
    priority: Mapped[str] = mapped_column(String(2), default="P2", index=True)
    collection_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_articles_per_run: Mapped[int] = mapped_column(Integer, default=3)
    slot_minute: Mapped[int] = mapped_column(Integer, default=0, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    industry_keyword: Mapped[IndustryKeyword | None] = relationship(
        back_populates="master_keywords"
    )
    companies: Mapped[list[MasterKeywordCompany]] = relationship(
        back_populates="master_keyword", cascade="all, delete-orphan",
        order_by="MasterKeywordCompany.priority",
    )
    article_matches: Mapped[list[ArticleKeyword]] = relationship(
        back_populates="master_keyword", cascade="all, delete-orphan"
    )
    user_subscriptions: Mapped[list[UserKeyword]] = relationship(
        back_populates="master_keyword", cascade="all, delete-orphan"
    )


class MasterKeywordCompany(Base):
    """마스터 키워드 하부 대표 기업 — RSS/Finnhub가 실제 검색하는 문자열."""

    __tablename__ = "content_master_keyword_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    master_keyword_id: Mapped[int] = mapped_column(
        ForeignKey("content_master_keywords.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(200))
    company_name_ko: Mapped[str | None] = mapped_column(String(200))
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    country: Mapped[str | None] = mapped_column(String(10))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    master_keyword: Mapped[MasterKeyword] = relationship(back_populates="companies")

    __table_args__ = (
        UniqueConstraint(
            "master_keyword_id", "company_name", name="uq_content_master_kw_company"
        ),
    )


# ---------------------------------------------------------------------------
# 뉴스 기사
# ---------------------------------------------------------------------------


class NewsArticle(Base):
    """수집·평가·요약된 뉴스 기사. ID는 ArticleId/NewsId로 노출."""

    __tablename__ = "content_news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 출처
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_news_sources.id", ondelete="SET NULL"), index=True
    )
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_channel: Mapped[str | None] = mapped_column(String(200))

    # URL / 본문 메타
    original_url: Mapped[str] = mapped_column(String(2000))
    canonical_url: Mapped[str | None] = mapped_column(String(2000), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    original_language: Mapped[str | None] = mapped_column(String(10))
    title_original: Mapped[str] = mapped_column(String(1000))
    title_translated: Mapped[str | None] = mapped_column(String(1000))
    summary: Mapped[str | None] = mapped_column(Text)
    summary_ko: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    content_translated: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    category: Mapped[str | None] = mapped_column(String(100))

    # AI 처리
    ai_keywords: Mapped[str | None] = mapped_column(Text)  # JSON list[str]
    ai_sentiment: Mapped[str | None] = mapped_column(String(20))
    ai_investment_relevance: Mapped[str | None] = mapped_column(String(20))
    # 멘토 전략 매핑 — 콤마 구분. MentorStrategy enum과 매칭.
    strategies: Mapped[str | None] = mapped_column(String(100), index=True)
    ai_processing_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    ai_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 신뢰도·필터링·중복
    reliability_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    reliability_level: Mapped[str] = mapped_column(String(20), default="low")
    reliability_reason: Mapped[str | None] = mapped_column(Text)
    cross_check_count: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    is_economy: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_news_articles.id", ondelete="SET NULL")
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_rag_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # 태그 (denormalized 보조 — pipeline_utils가 채움)
    related_tickers: Mapped[str | None] = mapped_column(String(500))
    related_industries: Mapped[str | None] = mapped_column(String(500))
    related_keywords: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[NewsSource | None] = relationship(back_populates="articles")
    keyword_matches: Mapped[list[ArticleKeyword]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_content_articles_visible_published", "is_visible", "published_at"),
        Index("ix_content_articles_strategies_published", "strategies", "published_at"),
    )


# ---------------------------------------------------------------------------
# 기사 ↔ 마스터 키워드 매핑 (composite PK)
# ---------------------------------------------------------------------------


class ArticleKeyword(Base):
    """기사와 매칭된 마스터 키워드. is_top_for_keyword는 그 키워드의 top-1 기사."""

    __tablename__ = "content_article_keywords"

    article_id: Mapped[int] = mapped_column(
        ForeignKey("content_news_articles.id", ondelete="CASCADE"), index=True
    )
    master_keyword_id: Mapped[int] = mapped_column(
        ForeignKey("content_master_keywords.id", ondelete="CASCADE"), index=True
    )
    is_top_for_keyword: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped[NewsArticle] = relationship(back_populates="keyword_matches")
    master_keyword: Mapped[MasterKeyword] = relationship(back_populates="article_matches")

    __table_args__ = (PrimaryKeyConstraint("article_id", "master_keyword_id"),)


# ---------------------------------------------------------------------------
# RAG 청크 (Chroma와 동기화)
# ---------------------------------------------------------------------------


class KnowledgeChunk(Base):
    """기사를 RAG-친화적인 청크로 쪼갠 결과. Chroma collection
    'content_news_kb'와 1:1 동기화 (vector_store_ref가 Chroma doc id)."""

    __tablename__ = "content_knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("content_news_articles.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_store_ref: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    article: Mapped[NewsArticle] = relationship(back_populates="chunks")


# ---------------------------------------------------------------------------
# 스크랩 — ScrapAddedEvent와 연결
# ---------------------------------------------------------------------------


class Scrap(Base):
    """사용자가 저장한 기사. ScrapAddedEvent 발행/구독의 single source of truth."""

    __tablename__ = "content_scraps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("content_news_articles.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_content_scrap_user_article"),
    )


# ---------------------------------------------------------------------------
# 사용자별 관심 키워드 구독 (M:N)
# ---------------------------------------------------------------------------


class UserKeyword(Base):
    """사용자가 선택한(또는 온보딩이 자동 등록한) 관심 키워드.

    - source='onboarding': OnboardingCompletedEvent 핸들러가 자동 시딩
    - source='manual': /api/content/keywords POST로 사용자가 직접 추가
    - source='auto': 추후 사용자 행동(스크랩 등)으로 추론 등록

    user_id는 users.id (BigInteger). MasterKeyword는 글로벌 풀에서 공유.
    """

    __tablename__ = "content_user_keywords"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    master_keyword_id: Mapped[int] = mapped_column(
        ForeignKey("content_master_keywords.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    master_keyword: Mapped[MasterKeyword] = relationship(back_populates="user_subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "master_keyword_id", name="uq_content_user_keyword"),
    )


# ---------------------------------------------------------------------------
# 수집 로그
# ---------------------------------------------------------------------------


class PipelineRun(Base):
    """수집 파이프라인 실행 로그. PR-3 collector + ai_worker가 INSERT."""

    __tablename__ = "content_pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(20))  # scheduled / manual / retry
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_news_sources.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))  # running / success / failed / partial_success
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


__all__ = [
    "ArticleKeyword",
    "Industry",
    "IndustryKeyword",
    "KnowledgeChunk",
    "MasterKeyword",
    "MasterKeywordCompany",
    "NewsArticle",
    "NewsSource",
    "PipelineRun",
    "Scrap",
    "UserKeyword",
]
