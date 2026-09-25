"""Restore the price history index, add a forecast index, drop unused columns and indexes

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

# Primary keys are already indexed.
REDUNDANT_INDEXES = {
    "ix_items_id": ("items", "id"),
    "ix_notification_profiles_id": ("notification_profiles", "id"),
    "ix_price_history_id": ("price_history", "id"),
    "ix_price_forecasts_id": ("price_forecasts", "id"),
    "ix_settings_key": ("settings", "key"),
}


def upgrade() -> None:
    op.create_index("ix_price_history_item_id_timestamp", "price_history", ["item_id", "timestamp"], if_not_exists=True)
    op.create_index("ix_price_forecasts_item_id", "price_forecasts", ["item_id"], if_not_exists=True)
    for name, (table, _) in REDUNDANT_INDEXES.items():
        op.drop_index(name, table_name=table, if_exists=True)
    for column in ("screenshot_path", "prompt_version", "repair_used"):
        op.drop_column("price_history", column)


def downgrade() -> None:
    op.add_column("price_history", sa.Column("repair_used", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("price_history", sa.Column("prompt_version", sa.String(), nullable=True))
    op.add_column("price_history", sa.Column("screenshot_path", sa.String(), nullable=True))
    for name, (table, column) in REDUNDANT_INDEXES.items():
        op.create_index(name, table, [column])
    op.drop_index("ix_price_forecasts_item_id", table_name="price_forecasts")
    op.drop_index("ix_price_history_item_id_timestamp", table_name="price_history")
