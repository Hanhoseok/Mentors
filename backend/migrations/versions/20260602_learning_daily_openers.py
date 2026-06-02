"""learning: create daily opener dedup marker table

Revision ID: 20260602_learning_openers
Revises: 20260602_dailyreport_tables
Create Date: 2026-06-02

학습 동(features/learning) 일일 리포트 전달 3단계(딜리버리) 마커.
- learning_daily_openers: (user_id, mentor_id, opened_date) 자연키.
  '그날 그 멘토 첫 진입'을 ON CONFLICT DO NOTHING upsert로 하루 1행만 남겨
  일일 리포트 카드를 멘토별 하루 한 번만 노출한다.

NOTE: revision id는 default `alembic_version.version_num VARCHAR(32)`에
맞춰 32자 이하로 유지한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260602_learning_openers"
down_revision: str | Sequence[str] | None = "20260602_dailyreport_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_daily_openers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mentor_id", sa.BigInteger(), nullable=False),
        sa.Column("opened_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "mentor_id",
            "opened_date",
            name="uq_learning_daily_openers_user_mentor_date",
        ),
    )
    op.create_index(
        "ix_learning_daily_openers_user_id", "learning_daily_openers", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_daily_openers_user_id", table_name="learning_daily_openers"
    )
    op.drop_table("learning_daily_openers")
