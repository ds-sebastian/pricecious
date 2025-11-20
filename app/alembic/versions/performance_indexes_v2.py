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
    # Add indexes only if they don't exist
    # Using raw SQL with IF NOT EXISTS for safety
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_price_history_timestamp
        ON price_history (timestamp)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_price_history_item_timestamp
        ON price_history (item_id, timestamp)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_items_is_active
        ON items (is_active)
        """
    )


def downgrade():
    op.drop_index("ix_items_is_active", table_name="items", if_exists=True)
    op.drop_index("ix_price_history_item_timestamp", table_name="price_history", if_exists=True)
    op.drop_index("ix_price_history_timestamp", table_name="price_history", if_exists=True)
