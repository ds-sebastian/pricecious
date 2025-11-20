"""Add performance indexes

Revision ID: performance_indexes_v2
Revises: 7f8e9d2a1b3c
Create Date: 2025-11-19

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "performance_indexes_v2"
down_revision = "7f8e9d2a1b3c"
branch_labels = None
depends_on = None


def upgrade():
    # Add index on price_history.timestamp for time-based queries
    op.create_index(
        "ix_price_history_timestamp",
        "price_history",
        ["timestamp"],
        unique=False,
    )

    # Add composite index on (item_id, timestamp) for efficient history queries
    op.create_index(
        "ix_price_history_item_timestamp",
        "price_history",
        ["item_id", "timestamp"],
        unique=False,
    )

    # Add index on items.is_active for faster active item queries
    op.create_index(
        "ix_items_is_active",
        "items",
        ["is_active"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_items_is_active", table_name="items")
    op.drop_index("ix_price_history_item_timestamp", table_name="price_history")
    op.drop_index("ix_price_history_timestamp", table_name="price_history")
