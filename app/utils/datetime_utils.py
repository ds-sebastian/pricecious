"""Datetime utilities for consistent timezone handling."""

from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return current UTC time as naive datetime for database storage.

    SQLAlchemy with asyncpg requires naive datetimes for TIMESTAMP WITHOUT TIME ZONE columns.
    This helper ensures consistency across the codebase.
    """
    return datetime.now(UTC).replace(tzinfo=None)
