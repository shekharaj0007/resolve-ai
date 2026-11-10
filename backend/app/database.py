"""SQLAlchemy engine. PostgreSQL is preferred; SQLite is the local fallback."""

import logging
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.config import settings, sqlite_url

logger = logging.getLogger(__name__)

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


def _sqlite_engine(url: str):
    eng = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return eng


def _postgres_engine(url: str):
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def init_engine():
    global engine, SessionLocal
    if engine is not None:
        return engine

    url = settings.database_url()
    explicit = bool(os.getenv("DATABASE_URL"))
    if url.startswith("sqlite"):
        engine = _sqlite_engine(url)
    elif explicit:
        engine = _postgres_engine(url)
    else:
        candidate = _postgres_engine(url)
        try:
            with candidate.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine = candidate
            logger.info("Connected to PostgreSQL.")
        except Exception as exc:
            candidate.dispose()
            fallback = sqlite_url()
            logger.warning(
                "PostgreSQL is not reachable (%s). Using SQLite at %s.",
                exc.__class__.__name__,
                fallback,
            )
            engine = _sqlite_engine(fallback)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine


def init_db():
    init_engine()
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_label() -> str:
    init_engine()
    name = engine.url.get_backend_name()
    if "postgres" in name:
        return "postgresql"
    if name.startswith("sqlite"):
        return "sqlite"
    return name
