"""Track page fingerprints so unchanged pages can skip the AI

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("page_fingerprint", sa.String(64), nullable=True))
    op.add_column("items", sa.Column("ai_checked_at", sa.DateTime(), nullable=True))
    op.add_column("items", sa.Column("ai_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("ai_skips", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    for column in ("ai_skips", "ai_calls", "ai_checked_at", "page_fingerprint"):
        op.drop_column("items", column)
