"""merge content and learning migration heads

Revision ID: 20260531_merge_content_learning_heads
Revises: 20260528_content_seed_pool, 20260529_learning_quiz_progress
Create Date: 2026-05-31

"""

from collections.abc import Sequence

revision: str = "20260531_merge_content_learning_heads"
down_revision: str | Sequence[str] | None = (
    "20260528_content_seed_pool",
    "20260529_learning_quiz_progress",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
