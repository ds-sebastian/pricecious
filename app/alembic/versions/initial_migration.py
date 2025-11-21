"""Initial migration

Revision ID: initial_migration
Revises:
Create Date: 2023-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "initial_migration"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # We are assuming the database is already created by the previous code
    # But for a fresh install, we need to create tables.
    # However, since we are retrofitting, we should use --autogenerate usually.
    # But I cannot run that easily.
    # So I will define the tables here to be safe.

    # Check if tables exist before creating to avoid errors on existing DBs
    # Actually, standard alembic practice is to define them.
    # But since we had `Base.metadata.create_all`, tables might exist.
    # Ideally we would use `alembic stamp head` on existing deployments.

    # For now, I will leave this empty and assume the user will run
    # `alembic revision --autogenerate` if they want to capture the state,
    # or I should try to capture it.
    # Given I can't run the DB, I'll leave it as a placeholder or try to define it.
    # Let's define it properly so new installs work.

    # ... actually, writing all create_table calls manually is error prone without running it.
    # I will rely on the fact that I removed `create_all` from main.py, so this MUST do it.

    op.create_table(
        "notification_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("apprise_url", sa.String(), nullable=True),
        sa.Column("notify_on_price_drop", sa.Boolean(), nullable=True),
        sa.Column("notify_on_target_price", sa.Boolean(), nullable=True),
        sa.Column("price_drop_threshold_percent", sa.Float(), nullable=True),
        sa.Column("notify_on_stock_change", sa.Boolean(), nullable=True),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_profiles_id"), "notification_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_notification_profiles_name"), "notification_profiles", ["name"], unique=True)

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("selector", sa.String(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("check_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("tags", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_checked", sa.DateTime(), nullable=True),
        sa.Column("notification_profile_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["notification_profile_id"],
            ["notification_profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_id"), "items", ["id"], unique=False)
    op.create_index(op.f("ix_items_url"), "items", ["url"], unique=False)

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("screenshot_path", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_history_id"), "price_history", ["id"], unique=False)

    op.create_table(
        "settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(op.f("ix_settings_key"), "settings", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_settings_key"), table_name="settings")
    op.drop_table("settings")
    op.drop_index(op.f("ix_price_history_id"), table_name="price_history")
    op.drop_table("price_history")
    op.drop_index(op.f("ix_items_url"), table_name="items")
    op.drop_index(op.f("ix_items_id"), table_name="items")
    op.drop_table("items")
    op.drop_index(op.f("ix_notification_profiles_name"), table_name="notification_profiles")
    op.drop_index(op.f("ix_notification_profiles_id"), table_name="notification_profiles")
    op.drop_table("notification_profiles")
