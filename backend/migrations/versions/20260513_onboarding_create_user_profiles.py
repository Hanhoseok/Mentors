"""onboarding: create user_profiles and onboarding_survey_answers

Revision ID: 20260513_onboarding
Revises: 20260519_learning_init_chat
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260513_onboarding"
down_revision: str | Sequence[str] | None = "20260519_learning_init_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_profiles" not in tables:
        op.create_table(
            "user_profiles",
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("current_tier", sa.String(length=10), nullable=False, server_default="T1"),
            sa.Column("selected_mentor_id", sa.BigInteger(), nullable=True),
            sa.Column("selected_mentor_slug", sa.String(length=100), nullable=True),
            sa.Column("risk_profile", sa.String(length=50), nullable=True),
            sa.Column("experience_level", sa.String(length=50), nullable=True),
            sa.Column("learning_goal", sa.String(length=100), nullable=True),
            sa.Column("preferred_style", sa.String(length=50), nullable=True),
            sa.Column("interests_json", sa.Text(), nullable=True),
            sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
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
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("user_profiles")}
        if "current_tier" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("current_tier", sa.String(length=10), nullable=True),
            )
            op.execute("UPDATE user_profiles SET current_tier = 'T1' WHERE current_tier IS NULL")
            op.alter_column("user_profiles", "current_tier", nullable=False, server_default="T1")
        if "selected_mentor_id" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("selected_mentor_id", sa.BigInteger(), nullable=True),
            )
        if "selected_mentor_slug" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("selected_mentor_slug", sa.String(length=100), nullable=True),
            )
        if "risk_profile" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("risk_profile", sa.String(length=50), nullable=True),
            )
            if "risk_tolerance" in columns:
                op.execute(
                    "UPDATE user_profiles SET risk_profile = risk_tolerance "
                    "WHERE risk_profile IS NULL"
                )
        if "experience_level" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("experience_level", sa.String(length=50), nullable=True),
            )
        if "learning_goal" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("learning_goal", sa.String(length=100), nullable=True),
            )
        if "preferred_style" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("preferred_style", sa.String(length=50), nullable=True),
            )
        if "interests_json" not in columns:
            op.add_column(
                "user_profiles",
                sa.Column("interests_json", sa.Text(), nullable=True),
            )

    if "onboarding_survey_answers" not in tables:
        op.create_table(
            "onboarding_survey_answers",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("question_code", sa.String(length=100), nullable=False),
            sa.Column("question_text", sa.String(length=255), nullable=True),
            sa.Column("answer_value", sa.Text(), nullable=True),
            sa.Column("answer_payload_json", sa.Text(), nullable=True),
            sa.Column(
                "answered_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_onboarding_survey_answers_user_id",
            "onboarding_survey_answers",
            ["user_id"],
        )
    else:
        answer_columns = {
            column["name"] for column in inspector.get_columns("onboarding_survey_answers")
        }
        if "answer_payload_json" not in answer_columns:
            op.add_column(
                "onboarding_survey_answers",
                sa.Column("answer_payload_json", sa.Text(), nullable=True),
            )
            if "answer_payload" in answer_columns:
                op.execute(
                    "UPDATE onboarding_survey_answers "
                    "SET answer_payload_json = answer_payload "
                    "WHERE answer_payload_json IS NULL"
                )
        indexes = {index["name"] for index in inspector.get_indexes("onboarding_survey_answers")}
        if "ix_onboarding_survey_answers_user_id" not in indexes:
            op.create_index(
                "ix_onboarding_survey_answers_user_id",
                "onboarding_survey_answers",
                ["user_id"],
            )


def downgrade() -> None:
    op.drop_index(
        "ix_onboarding_survey_answers_user_id",
        table_name="onboarding_survey_answers",
    )
    op.drop_table("onboarding_survey_answers")
    op.drop_table("user_profiles")
