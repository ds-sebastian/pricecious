"""add_performance_indexes

Revision ID: 7f8e9d2a1b3c
Revises: a1b2c3d4e5f6
Create Date: 2025-11-19 19:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f8e9d2a1b3c'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes for performance optimization
    # Items table indexes
    op.create_index('ix_items_last_checked', 'items', ['last_checked'])
    op.create_index('ix_items_is_active', 'items', ['is_active'])
    # Note: url already has an index from the model definition

    # Composite index for common query pattern (active items due for refresh)
    op.create_index('ix_items_active_last_checked', 'items', ['is_active', 'last_checked'])

    # Price history indexes for time-series queries
    op.create_index('ix_price_history_timestamp', 'price_history', ['timestamp'])
    op.create_index('ix_price_history_item_timestamp', 'price_history', ['item_id', 'timestamp'])


def downgrade():
    # Remove indexes in reverse order
    op.drop_index('ix_price_history_item_timestamp', table_name='price_history')
    op.drop_index('ix_price_history_timestamp', table_name='price_history')
    op.drop_index('ix_items_active_last_checked', table_name='items')
    op.drop_index('ix_items_is_active', table_name='items')
    op.drop_index('ix_items_last_checked', table_name='items')
