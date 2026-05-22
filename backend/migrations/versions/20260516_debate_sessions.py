"""debate: init sessions and messages

Revision ID: 20260516_debate_sessions
Revises: 20260520_learning_quiz_attempts
Create Date: 2026-05-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260516_debate_sessions"
down_revision: str | Sequence[str] | None = "20260520_learning_quiz_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "debate_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("persona_a_id", sa.String(50), nullable=False),
        sa.Column("persona_b_id", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("error_message", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_debate_sessions_user_id", "debate_sessions", ["user_id"])

    op.create_table(
        "debate_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "debate_session_id",
            sa.BigInteger(),
            sa.ForeignKey("debate_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker_id", sa.String(50), nullable=False),
        sa.Column("turn_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("critic_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_debate_messages_debate_session_id",
        "debate_messages",
        ["debate_session_id"],
    )
    op.create_unique_constraint(
        "uq_debate_messages_turn",
        "debate_messages",
        ["debate_session_id", "turn_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_debate_messages_turn", "debate_messages", type_="unique")
    op.drop_index("ix_debate_messages_debate_session_id", table_name="debate_messages")
    op.drop_table("debate_messages")
    op.drop_index("ix_debate_sessions_user_id", table_name="debate_sessions")
    op.drop_table("debate_sessions")
