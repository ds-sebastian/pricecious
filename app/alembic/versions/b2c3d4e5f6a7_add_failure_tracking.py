"""Add failure tracking columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14 03:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Base

target_metadata = Base.metadata


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add consecutive_failures and error_type columns to items table."""
    op.add_column("items", sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("error_type", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove failure tracking columns."""
    op.drop_column("items", "error_type")
    op.drop_column("items", "consecutive_failures")
