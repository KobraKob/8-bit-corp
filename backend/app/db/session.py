import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from app.core.config import get_app_settings
from app.db.models import Base

settings = get_app_settings()

_engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

_session_factory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def set_engine_and_factory(new_engine):
    global _engine, _session_factory
    _engine = new_engine
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


class _SessionFactoryProxy:
    def __call__(self, *args, **kwargs) -> AsyncSession:
        return _session_factory(*args, **kwargs)


async_session_factory = _SessionFactoryProxy()


async def init_db(engine_override=None) -> None:
    """Initialize database tables and set SQLite WAL mode if applicable."""
    target_engine = engine_override or _engine
    async with target_engine.begin() as conn:
        if "sqlite" in str(target_engine.url):
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
