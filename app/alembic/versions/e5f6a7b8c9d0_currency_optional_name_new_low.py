"""Add item currency, allow unnamed items, add the new-low notification option

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("currency", sa.String(3), nullable=True))
    op.alter_column("items", "name", existing_type=sa.String(), nullable=True)
    op.add_column(
        "notification_profiles",
        sa.Column("notify_on_new_low", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("notification_profiles", "notify_on_new_low")
    op.execute("UPDATE items SET name = url WHERE name IS NULL")
    op.alter_column("items", "name", existing_type=sa.String(), nullable=False)
    op.drop_column("items", "currency")
