"""daily_report: create core + per-mentor report tables

Revision ID: 20260602_dailyreport_tables
Revises: 20260530_onb_growth_backfill
Create Date: 2026-06-02

일일 리포트 동(features/daily_report) 1단계(생산자) 스키마.
- daily_report_cores: 사용자×날짜 1회 공통 시장 코어 (멘토 무관)
- daily_reports: 멘토 전략별 리포트 (user × mentor_strategy × date), 멱등 upsert

NOTE: revision id는 default `alembic_version.version_num VARCHAR(32)`에
맞춰 32자 이하로 유지한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260602_dailyreport_tables"
down_revision: str | Sequence[str] | None = "20260530_onb_growth_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_report_cores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("news_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("market_summary", sa.Text(), nullable=True),
        sa.Column("today_concept_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "report_date", name="uq_daily_report_cores_user_date"),
    )
    op.create_index("ix_daily_report_cores_user_id", "daily_report_cores", ["user_id"])

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "core_id",
            sa.BigInteger(),
            sa.ForeignKey("daily_report_cores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("mentor_strategy", sa.String(length=20), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("highlights_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "mentor_strategy",
            "report_date",
            name="uq_daily_reports_user_strategy_date",
        ),
    )
    op.create_index("ix_daily_reports_user_id", "daily_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_reports_user_id", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index("ix_daily_report_cores_user_id", table_name="daily_report_cores")
    op.drop_table("daily_report_cores")
