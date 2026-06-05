"""content: scrap folders + scrap snapshot columns

Revision ID: 20260604_scrap_folders
Revises: 20260604_market_search
Create Date: 2026-06-04

owner: content (5동)

변경 요약:
- content_scrap_folders 신규 — 사용자별 스크랩 폴더(이름/색상).
- content_scraps 확장 — folder_id(FK→folders, CASCADE) + 기사 스냅샷 컬럼
  (title/url/image_url/summary/source_name/category/published_at).
- article_id를 nullable로 완화 (실시간 RSS 기사는 DB 미적재 → id 없음).
- 기존 uq_content_scrap_user_article 제거 — 같은 기사를 여러 폴더에 담거나
  DB id 없는 live 기사를 중복 저장 가능하게. 중복 방지는 서비스 계층에서 처리.

기존 데이터: 기존 content_scraps 행에는 title/url이 NULL이므로, 백필을
content_news_articles에서 끌어온다(article_id가 항상 존재했던 시절의 행).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_scrap_folders"
down_revision: str | Sequence[str] | None = "20260604_market_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- content_scrap_folders ------------------------------------------
    op.create_table(
        "content_scrap_folders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_content_scrap_folder_user_name"),
    )
    op.create_index("ix_content_scrap_folders_user", "content_scrap_folders", ["user_id"])

    # ---- content_scraps 확장 --------------------------------------------
    # 1) 기존 unique 제약 제거 (멀티 폴더 / live 기사 중복 허용)
    op.drop_constraint("uq_content_scrap_user_article", "content_scraps", type_="unique")

    # 2) folder_id
    op.add_column(
        "content_scraps",
        sa.Column(
            "folder_id",
            sa.BigInteger(),
            sa.ForeignKey("content_scrap_folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_content_scraps_folder", "content_scraps", ["folder_id"])

    # 3) 기사 스냅샷 컬럼 (우선 nullable로 추가 → 백필 → title/url NOT NULL 승격)
    op.add_column("content_scraps", sa.Column("title", sa.String(1000)))
    op.add_column("content_scraps", sa.Column("url", sa.String(2000)))
    op.add_column("content_scraps", sa.Column("image_url", sa.String(1000)))
    op.add_column("content_scraps", sa.Column("summary", sa.Text()))
    op.add_column("content_scraps", sa.Column("source_name", sa.String(200)))
    op.add_column("content_scraps", sa.Column("category", sa.String(100)))
    op.add_column("content_scraps", sa.Column("published_at", sa.DateTime(timezone=True)))

    # 4) 기존 행 백필 — article_id로 기사 메타 끌어오기
    op.execute(
        """
        UPDATE content_scraps s
        SET title = COALESCE(a.title_translated, a.title_original, '(제목 없음)'),
            url = a.original_url,
            image_url = a.image_url,
            summary = a.summary_ko,
            source_name = a.source_name,
            published_at = a.published_at
        FROM content_news_articles a
        WHERE s.article_id = a.id
          AND s.title IS NULL
        """
    )
    # article_id가 없는데 title도 없는 행은 방어적으로 채움 (정상 흐름엔 없음)
    op.execute("UPDATE content_scraps SET title = '(제목 없음)' WHERE title IS NULL")
    op.execute("UPDATE content_scraps SET url = '' WHERE url IS NULL")

    # 5) title/url NOT NULL 승격, article_id NULL 허용
    op.alter_column("content_scraps", "title", existing_type=sa.String(1000), nullable=False)
    op.alter_column("content_scraps", "url", existing_type=sa.String(2000), nullable=False)
    op.alter_column(
        "content_scraps", "article_id", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    # ⚠️ 주의(데이터 손실): 이 마이그레이션 이후 생성된 스크랩 중 article_id가
    # NULL인 행(실시간 RSS/live-topics 기사처럼 DB 미적재 기사를 스냅샷으로만
    # 저장한 경우)은 article_id를 다시 NOT NULL로 되돌릴 수 없다. 그대로 두면
    # ALTER COLUMN ... SET NOT NULL 이 실패하므로, downgrade는 이 행들을 먼저
    # 삭제한 뒤 NOT NULL 제약을 복원한다. (업그레이드 이전 상태 = article_id가
    # 항상 존재하던 스크랩만 남는 상태로 복귀.)
    op.execute("DELETE FROM content_scraps WHERE article_id IS NULL")
    op.alter_column(
        "content_scraps", "article_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_column("content_scraps", "published_at")
    op.drop_column("content_scraps", "category")
    op.drop_column("content_scraps", "source_name")
    op.drop_column("content_scraps", "summary")
    op.drop_column("content_scraps", "image_url")
    op.drop_column("content_scraps", "url")
    op.drop_column("content_scraps", "title")
    op.drop_index("ix_content_scraps_folder", table_name="content_scraps")
    op.drop_column("content_scraps", "folder_id")
    op.create_unique_constraint(
        "uq_content_scrap_user_article", "content_scraps", ["user_id", "article_id"]
    )

    op.drop_index("ix_content_scrap_folders_user", table_name="content_scrap_folders")
    op.drop_table("content_scrap_folders")
