"""Add confidence and AI metadata

Revision ID: add_confidence_metadata
Revises: 6ecb6f39fd8c
Create Date: 2025-11-19 13:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Base

target_metadata = Base.metadata


# revision identifiers, used by Alembic.
revision: str = "add_confidence_metadata"
down_revision: str | None = "6ecb6f39fd8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add confidence scores and AI metadata to price_history and items tables."""

    # Add columns to price_history table
    op.add_column("price_history", sa.Column("price_confidence", sa.Float(), nullable=True))
    op.add_column("price_history", sa.Column("in_stock_confidence", sa.Float(), nullable=True))
    op.add_column("price_history", sa.Column("ai_model", sa.String(), nullable=True))
    op.add_column("price_history", sa.Column("ai_provider", sa.String(), nullable=True))
    op.add_column("price_history", sa.Column("prompt_version", sa.String(), nullable=True))
    op.add_column("price_history", sa.Column("repair_used", sa.Boolean(), nullable=True, server_default="false"))

    # Add columns to items table for quick access to latest confidence
    op.add_column("items", sa.Column("current_price_confidence", sa.Float(), nullable=True))
    op.add_column("items", sa.Column("in_stock_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove confidence scores and AI metadata columns."""

    # Remove columns from items table
    op.drop_column("items", "in_stock_confidence")
    op.drop_column("items", "current_price_confidence")

    # Remove columns from price_history table
    op.drop_column("price_history", "repair_used")
    op.drop_column("price_history", "prompt_version")
    op.drop_column("price_history", "ai_provider")
    op.drop_column("price_history", "ai_model")
    op.drop_column("price_history", "in_stock_confidence")
    op.drop_column("price_history", "price_confidence")
