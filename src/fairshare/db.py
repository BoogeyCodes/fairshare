"""Database engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def _is_memory_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url in ("sqlite://", "sqlite:///:memory:"))


class Database:
    """Owns the engine and hands out sessions. One instance per application."""

    def __init__(self, url: str) -> None:
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        if _is_memory_sqlite(url):
            # An in-memory database lives in a single connection, so share one across the pool.
            kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        self._factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def create_all(self) -> None:
        # Import models so they're registered on Base.metadata before create_all.
        from fairshare import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._factory()

    def session_scope(self) -> Iterator[Session]:
        """Context-managed session that commits on success and rolls back on error."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
