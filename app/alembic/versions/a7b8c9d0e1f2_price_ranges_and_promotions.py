"""Record price ranges, crossed-out prices and promotions

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

COLUMNS = {"price_high": sa.Float, "regular_price": sa.Float, "promotion": sa.String}


def upgrade() -> None:
    for table in ("items", "price_history"):
        for name, type_ in COLUMNS.items():
            op.add_column(table, sa.Column(name, type_(), nullable=True))


def downgrade() -> None:
    for table in ("items", "price_history"):
        for name in COLUMNS:
            op.drop_column(table, name)
