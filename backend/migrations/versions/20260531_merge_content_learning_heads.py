"""merge content/onboarding/growth/daily-report migration heads

Revision ID: 20260531_merge_heads
Revises: 20260530_onb_growth_backfill, 20260602_learning_openers
Create Date: 2026-05-31

"""

from collections.abc import Sequence

revision: str = "20260531_merge_heads"
down_revision: str | Sequence[str] | None = (
    "20260530_onb_growth_backfill",
    "20260602_learning_openers",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
