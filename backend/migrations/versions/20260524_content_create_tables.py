"""content: create content_* tables (industries, master keywords, news, scraps, user keywords)

Revision ID: 20260524_content_create_tables
Revises: 20260523_auth_local_credentials
Create Date: 2026-05-24

owner: content (5동)
관련 FR/UC: FR-05, FR-06, FR-08, UC-05
주의: 다른 PR이 먼저 머지되어 head가 바뀌면 down_revision 재조정 (AGENTS.md §5.9).

스키마 출처:
- newspipeline/core/db/models.py 의 도메인 구조를 그대로 이식
- mentors 컨벤션 적용: 테이블 prefix `content_`, user_id BigInteger + FK→users.id CASCADE,
  PEP 604 타입, alembic revision/down_revision 타입 시그니처
- 산업 → 산업 키워드 → 마스터 키워드 → 대표 기업 계층은 PR-3 수집기가 활용.
  PR-2 시점에서는 테이블 구조만 만들고 풀 시드(115개 산업)는 별도 작업.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260524_content_create_tables"
down_revision: str | Sequence[str] | None = "20260523_auth_local_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- content_news_sources --------------------------------------------
    # 뉴스 출처 카탈로그 (RSS, Finnhub API, SEC EDGAR 등).
    op.create_table(
        "content_news_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),  # rss / api / web / sec
        sa.Column("base_url", sa.String(500)),
        sa.Column("category", sa.String(100)),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("country", sa.String(10), nullable=False, server_default="US"),
        sa.Column("reliability_base_score", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_content_news_source_code"),
    )
    op.create_index("ix_content_news_sources_active", "content_news_sources", ["is_active"])

    # ---- content_industries ---------------------------------------------
    # 산업 분류 (UI: 산업 카테고리 그리드).
    op.create_table(
        "content_industries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_ko", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name_ko", name="uq_content_industry_name_ko"),
    )
    op.create_index(
        "ix_content_industries_display_order", "content_industries", ["display_order"]
    )

    # ---- content_industry_keywords --------------------------------------
    # 산업별 하부 키워드 라벨 (UI: 산업 카드 안의 하위 칩).
    op.create_table(
        "content_industry_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "industry_id",
            sa.Integer(),
            sa.ForeignKey("content_industries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label_ko", sa.String(200), nullable=False),
        sa.Column("keyword_en", sa.String(200), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "industry_id", "label_ko", name="uq_content_industry_keyword_label"
        ),
    )
    op.create_index(
        "ix_content_industry_keywords_industry", "content_industry_keywords", ["industry_id"]
    )

    # ---- content_master_keywords ----------------------------------------
    # 글로벌 키워드 풀. 산업 하부 키워드(industry_keywords)에 1:1로 연결되는 경우
    # 가 일반적이지만, 사용자가 직접 추가한 manual 키워드는 industry_keyword_id 가
    # NULL. priority/scheduling 컬럼은 PR-3 수집기 스케줄러가 사용.
    op.create_table(
        "content_master_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column(
            "industry_keyword_id",
            sa.Integer(),
            sa.ForeignKey("content_industry_keywords.id", ondelete="SET NULL"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.String(2), nullable=False, server_default="P2"),
        sa.Column("collection_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_articles_per_run", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("slot_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("keyword", name="uq_content_master_keyword"),
    )
    op.create_index("ix_content_master_keyword_active", "content_master_keywords", ["is_active"])
    op.create_index("ix_content_master_keyword_source", "content_master_keywords", ["source"])
    op.create_index(
        "ix_content_master_keyword_priority", "content_master_keywords", ["priority"]
    )
    op.create_index("ix_content_master_keyword_slot", "content_master_keywords", ["slot_minute"])
    op.create_index(
        "ix_content_master_keyword_next_run", "content_master_keywords", ["next_run_at"]
    )
    op.create_index(
        "ix_content_master_keyword_industry_kw",
        "content_master_keywords",
        ["industry_keyword_id"],
    )

    # ---- content_master_keyword_companies -------------------------------
    # 마스터 키워드의 대표 기업 (RSS/Finnhub가 실제 검색하는 문자열).
    op.create_table(
        "content_master_keyword_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "master_keyword_id",
            sa.Integer(),
            sa.ForeignKey("content_master_keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("company_name_ko", sa.String(200)),
        sa.Column("ticker", sa.String(20)),
        sa.Column("country", sa.String(10)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "master_keyword_id", "company_name", name="uq_content_master_kw_company"
        ),
    )
    op.create_index(
        "ix_content_mkw_company_keyword",
        "content_master_keyword_companies",
        ["master_keyword_id"],
    )
    op.create_index(
        "ix_content_mkw_company_ticker", "content_master_keyword_companies", ["ticker"]
    )
    op.create_index(
        "ix_content_mkw_company_last_fetched",
        "content_master_keyword_companies",
        ["last_fetched_at"],
    )

    # ---- content_news_articles ------------------------------------------
    op.create_table(
        "content_news_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("content_news_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("source_name", sa.String(200)),
        sa.Column("source_channel", sa.String(200)),
        sa.Column("original_url", sa.String(2000), nullable=False),
        sa.Column("canonical_url", sa.String(2000)),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("original_language", sa.String(10)),
        sa.Column("title_original", sa.String(1000), nullable=False),
        sa.Column("title_translated", sa.String(1000)),
        sa.Column("summary", sa.Text()),
        sa.Column("summary_ko", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("content_translated", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("image_url", sa.String(1000)),
        sa.Column("category", sa.String(100)),
        # AI 처리
        sa.Column("ai_keywords", sa.Text()),
        sa.Column("ai_sentiment", sa.String(20)),
        sa.Column("ai_investment_relevance", sa.String(20)),
        sa.Column("strategies", sa.String(100)),
        sa.Column("ai_processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("ai_error", sa.Text()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        # 신뢰도·필터링·중복
        sa.Column("reliability_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reliability_level", sa.String(20), nullable=False, server_default="low"),
        sa.Column("reliability_reason", sa.Text()),
        sa.Column("cross_check_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("composite_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_economy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "duplicate_of_article_id",
            sa.Integer(),
            sa.ForeignKey("content_news_articles.id", ondelete="SET NULL"),
        ),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_rag_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        # 태그 (denormalized 보조)
        sa.Column("related_tickers", sa.String(500)),
        sa.Column("related_industries", sa.String(500)),
        sa.Column("related_keywords", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("canonical_url", name="uq_content_article_canonical_url"),
    )
    op.create_index("ix_content_articles_source", "content_news_articles", ["source_id"])
    op.create_index("ix_content_articles_published", "content_news_articles", ["published_at"])
    op.create_index("ix_content_articles_status", "content_news_articles", ["ai_processing_status"])
    op.create_index(
        "ix_content_articles_reliability", "content_news_articles", ["reliability_score"]
    )
    op.create_index("ix_content_articles_composite", "content_news_articles", ["composite_score"])
    op.create_index("ix_content_articles_visible", "content_news_articles", ["is_visible"])
    op.create_index("ix_content_articles_economy", "content_news_articles", ["is_economy"])
    op.create_index("ix_content_articles_rag", "content_news_articles", ["is_rag_eligible"])
    op.create_index("ix_content_articles_created", "content_news_articles", ["created_at"])
    op.create_index("ix_content_articles_strategies", "content_news_articles", ["strategies"])
    op.create_index(
        "ix_content_articles_visible_published",
        "content_news_articles",
        ["is_visible", "published_at"],
    )
    op.create_index(
        "ix_content_articles_strategies_published",
        "content_news_articles",
        ["strategies", "published_at"],
    )

    # ---- content_article_keywords (M:N, composite PK) -------------------
    op.create_table(
        "content_article_keywords",
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("content_news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "master_keyword_id",
            sa.Integer(),
            sa.ForeignKey("content_master_keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_top_for_keyword", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("article_id", "master_keyword_id"),
    )
    op.create_index(
        "ix_content_article_keyword_master", "content_article_keywords", ["master_keyword_id"]
    )
    op.create_index(
        "ix_content_article_keyword_article", "content_article_keywords", ["article_id"]
    )
    op.create_index(
        "ix_content_article_keyword_top", "content_article_keywords", ["is_top_for_keyword"]
    )

    # ---- content_knowledge_chunks (RAG 청크) ----------------------------
    op.create_table(
        "content_knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("content_news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vector_store_ref", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_content_knowledge_chunks_article", "content_knowledge_chunks", ["article_id"]
    )

    # ---- content_scraps -------------------------------------------------
    # user_id 는 users.id (BigInteger) — auth와 정렬.
    op.create_table(
        "content_scraps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("content_news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "article_id", name="uq_content_scrap_user_article"),
    )
    op.create_index("ix_content_scraps_user", "content_scraps", ["user_id"])
    op.create_index("ix_content_scraps_article", "content_scraps", ["article_id"])

    # ---- content_user_keywords (사용자 구독, M:N) -----------------------
    # 신규 사용자가 온보딩을 완료하면 핸들러가 시딩 (source='onboarding').
    # 사용자가 라우터로 추가하면 source='manual'.
    op.create_table(
        "content_user_keywords",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "master_keyword_id",
            sa.Integer(),
            sa.ForeignKey("content_master_keywords.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "master_keyword_id", name="uq_content_user_keyword"),
    )
    op.create_index("ix_content_user_keyword_user", "content_user_keywords", ["user_id"])
    op.create_index(
        "ix_content_user_keyword_master", "content_user_keywords", ["master_keyword_id"]
    )
    op.create_index("ix_content_user_keyword_source", "content_user_keywords", ["source"])

    # ---- content_pipeline_runs (수집 로그) -----------------------------
    op.create_table(
        "content_pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(20), nullable=False),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("content_news_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("saved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_content_pipeline_runs_source", "content_pipeline_runs", ["source_id"]
    )
    op.create_index(
        "ix_content_pipeline_runs_started", "content_pipeline_runs", ["started_at"]
    )

    # ---- 미니멀 시드 (구조 검증용) -------------------------------------
    # 풀 시드(115개 산업)는 별도 작업. 여기선 한 산업 → 한 키워드 → 두 기업까지만.
    op.bulk_insert(
        sa.table(
            "content_industries",
            sa.column("id", sa.Integer),
            sa.column("name_ko", sa.String),
            sa.column("name_en", sa.String),
            sa.column("display_order", sa.Integer),
        ),
        [{"id": 1, "name_ko": "반도체", "name_en": "Semiconductor", "display_order": 1}],
    )
    op.bulk_insert(
        sa.table(
            "content_industry_keywords",
            sa.column("id", sa.Integer),
            sa.column("industry_id", sa.Integer),
            sa.column("label_ko", sa.String),
            sa.column("keyword_en", sa.String),
            sa.column("display_order", sa.Integer),
        ),
        [
            {"id": 1, "industry_id": 1, "label_ko": "반도체 제조",
             "keyword_en": "semiconductor manufacturing", "display_order": 1},
        ],
    )
    op.bulk_insert(
        sa.table(
            "content_master_keywords",
            sa.column("id", sa.Integer),
            sa.column("keyword", sa.String),
            sa.column("language", sa.String),
            sa.column("source", sa.String),
            sa.column("industry_keyword_id", sa.Integer),
            sa.column("priority", sa.String),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {"id": 1, "keyword": "반도체 제조", "language": "ko", "source": "industry",
             "industry_keyword_id": 1, "priority": "P0", "is_active": True},
        ],
    )
    op.bulk_insert(
        sa.table(
            "content_master_keyword_companies",
            sa.column("master_keyword_id", sa.Integer),
            sa.column("company_name", sa.String),
            sa.column("company_name_ko", sa.String),
            sa.column("country", sa.String),
            sa.column("priority", sa.Integer),
        ),
        [
            {"master_keyword_id": 1, "company_name": "Samsung Electronics",
             "company_name_ko": "삼성전자", "country": "KR", "priority": 1},
            {"master_keyword_id": 1, "company_name": "SK hynix",
             "company_name_ko": "SK하이닉스", "country": "KR", "priority": 2},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_content_pipeline_runs_started", table_name="content_pipeline_runs")
    op.drop_index("ix_content_pipeline_runs_source", table_name="content_pipeline_runs")
    op.drop_table("content_pipeline_runs")

    op.drop_index("ix_content_user_keyword_source", table_name="content_user_keywords")
    op.drop_index("ix_content_user_keyword_master", table_name="content_user_keywords")
    op.drop_index("ix_content_user_keyword_user", table_name="content_user_keywords")
    op.drop_table("content_user_keywords")

    op.drop_index("ix_content_scraps_article", table_name="content_scraps")
    op.drop_index("ix_content_scraps_user", table_name="content_scraps")
    op.drop_table("content_scraps")

    op.drop_index("ix_content_knowledge_chunks_article", table_name="content_knowledge_chunks")
    op.drop_table("content_knowledge_chunks")

    op.drop_index("ix_content_article_keyword_top", table_name="content_article_keywords")
    op.drop_index("ix_content_article_keyword_article", table_name="content_article_keywords")
    op.drop_index("ix_content_article_keyword_master", table_name="content_article_keywords")
    op.drop_table("content_article_keywords")

    for ix in [
        "ix_content_articles_strategies_published",
        "ix_content_articles_visible_published",
        "ix_content_articles_strategies",
        "ix_content_articles_created",
        "ix_content_articles_rag",
        "ix_content_articles_economy",
        "ix_content_articles_visible",
        "ix_content_articles_composite",
        "ix_content_articles_reliability",
        "ix_content_articles_status",
        "ix_content_articles_published",
        "ix_content_articles_source",
    ]:
        op.drop_index(ix, table_name="content_news_articles")
    op.drop_table("content_news_articles")

    op.drop_index(
        "ix_content_mkw_company_last_fetched",
        table_name="content_master_keyword_companies",
    )
    op.drop_index(
        "ix_content_mkw_company_ticker", table_name="content_master_keyword_companies"
    )
    op.drop_index(
        "ix_content_mkw_company_keyword", table_name="content_master_keyword_companies"
    )
    op.drop_table("content_master_keyword_companies")

    op.drop_index(
        "ix_content_master_keyword_industry_kw", table_name="content_master_keywords"
    )
    op.drop_index("ix_content_master_keyword_next_run", table_name="content_master_keywords")
    op.drop_index("ix_content_master_keyword_slot", table_name="content_master_keywords")
    op.drop_index("ix_content_master_keyword_priority", table_name="content_master_keywords")
    op.drop_index("ix_content_master_keyword_source", table_name="content_master_keywords")
    op.drop_index("ix_content_master_keyword_active", table_name="content_master_keywords")
    op.drop_table("content_master_keywords")

    op.drop_index(
        "ix_content_industry_keywords_industry", table_name="content_industry_keywords"
    )
    op.drop_table("content_industry_keywords")

    op.drop_index("ix_content_industries_display_order", table_name="content_industries")
    op.drop_table("content_industries")

    op.drop_index("ix_content_news_sources_active", table_name="content_news_sources")
    op.drop_table("content_news_sources")
