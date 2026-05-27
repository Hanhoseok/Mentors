"""market data: cache entities and news

Revision ID: 20260526_market_data_cache
Revises: 20260526_learning_backfill
Create Date: 2026-05-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260526_market_data_cache"
down_revision: str | Sequence[str] | None = "20260526_learning_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=True),
        sa.Column("exchange", sa.String(40), nullable=True),
        sa.Column("sector", sa.String(80), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("themes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(80), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_market_entities_kind", "market_entities", ["kind"])
    op.create_index("ix_market_entities_name", "market_entities", ["name"])
    op.create_index("ix_market_entities_name_en", "market_entities", ["name_en"])
    op.create_index("ix_market_entities_sector", "market_entities", ["sector"])
    op.create_unique_constraint(
        "uq_market_entities_kind_symbol",
        "market_entities",
        ["kind", "symbol"],
    )

    op.create_table(
        "market_news_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "entity_id",
            sa.BigInteger(),
            sa.ForeignKey("market_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_market_news_items_entity_id", "market_news_items", ["entity_id"])
    op.create_unique_constraint(
        "uq_market_news_items_entity_url",
        "market_news_items",
        ["entity_id", "url"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_market_news_items_entity_url", "market_news_items", type_="unique")
    op.drop_index("ix_market_news_items_entity_id", table_name="market_news_items")
    op.drop_table("market_news_items")
    op.drop_constraint("uq_market_entities_kind_symbol", "market_entities", type_="unique")
    op.drop_index("ix_market_entities_sector", table_name="market_entities")
    op.drop_index("ix_market_entities_name_en", table_name="market_entities")
    op.drop_index("ix_market_entities_name", table_name="market_entities")
    op.drop_index("ix_market_entities_kind", table_name="market_entities")
    op.drop_table("market_entities")
