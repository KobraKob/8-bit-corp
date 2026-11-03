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


async def _migrate_sqlite_schema(conn) -> None:
    """Auto-migrate schema changes for SQLite databases to ensure columns match models."""
    # 1. agents.api_key
    res = await conn.execute(text("PRAGMA table_info(agents);"))
    agent_cols = [r[1] for r in res.fetchall()]
    if agent_cols and "api_key" not in agent_cols:
        await conn.execute(text("ALTER TABLE agents ADD COLUMN api_key VARCHAR(255);"))

    # 2. llm_calls.key_alias
    res = await conn.execute(text("PRAGMA table_info(llm_calls);"))
    llm_cols = [r[1] for r in res.fetchall()]
    if llm_cols and "key_alias" not in llm_cols:
        await conn.execute(text("ALTER TABLE llm_calls ADD COLUMN key_alias VARCHAR(100) DEFAULT 'default' NOT NULL;"))

    # 3. daily_usage.key_alias
    res = await conn.execute(text("PRAGMA table_info(daily_usage);"))
    usage_cols = [r[1] for r in res.fetchall()]
    if usage_cols and "key_alias" not in usage_cols:
        await conn.execute(text("ALTER TABLE daily_usage ADD COLUMN key_alias VARCHAR(100) DEFAULT 'default' NOT NULL;"))

    # Persistent execution checkpoints and task leases.
    res = await conn.execute(text("PRAGMA table_info(tasks);"))
    task_cols = {r[1] for r in res.fetchall()}
    if task_cols:
        if "checkpoint_json" not in task_cols:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN checkpoint_json JSON NOT NULL DEFAULT '{}';"))
        if "lease_token" not in task_cols:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN lease_token VARCHAR(64);"))
        if "lease_expires_at" not in task_cols:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN lease_expires_at DATETIME;"))
        if "next_retry_at" not in task_cols:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN next_retry_at DATETIME;"))
        if "delegation_count" not in task_cols:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN delegation_count INTEGER NOT NULL DEFAULT 0;"))


async def init_db(engine_override=None) -> None:
    """Initialize database tables and set SQLite WAL mode if applicable."""
    target_engine = engine_override or _engine
    async with target_engine.begin() as conn:
        if "sqlite" in str(target_engine.url):
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in str(target_engine.url):
            await _migrate_sqlite_schema(conn)


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
