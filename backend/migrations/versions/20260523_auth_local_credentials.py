"""auth: add local credentials

Revision ID: 20260523_auth_local_credentials
Revises: 20260516_debate_sessions
Create Date: 2026-05-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260523_auth_local_credentials"
down_revision: str | Sequence[str] | None = "20260516_debate_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "local_credentials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
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
        sa.UniqueConstraint("user_id", name="uq_local_credentials_user_id"),
    )
    op.create_index("ix_local_credentials_user_id", "local_credentials", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_local_credentials_user_id", table_name="local_credentials")
    op.drop_table("local_credentials")
