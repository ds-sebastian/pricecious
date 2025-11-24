import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Remove hardcoded credentials - require environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. Example: postgresql://user:password@localhost:5432/pricewatch"
    )

# Connection pool configuration
#  pool_size: number of connections to maintain
#  max_overflow: max number of connections above pool_size
#  pool_pre_ping: verify connections before using (prevents stale connections)
#  pool_recycle: recycle connections after N seconds (prevents timeout issues)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,  # 1 hour
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Log database connection events for debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("Database connection established")


@event.listens_for(engine, "close")
def receive_close(dbapi_conn, connection_record):
    logger.debug("Database connection closed")


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
