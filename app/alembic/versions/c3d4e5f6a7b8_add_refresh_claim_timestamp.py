"""Add refresh claim timestamp

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-13 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track when each durable refresh claim was acquired."""
    op.add_column("items", sa.Column("refresh_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove refresh claim timestamps."""
    op.drop_column("items", "refresh_started_at")
