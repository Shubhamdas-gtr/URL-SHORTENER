"""SQLAlchemy engine, session factory, and table initialization."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import SQLALCHEMY_DATABASE_URL

# check_same_thread=False is required for SQLite with FastAPI's threaded dev server.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create all tables. Safe to call at app startup."""
    # Import models so they are registered on Base.metadata.
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
