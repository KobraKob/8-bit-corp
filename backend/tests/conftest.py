import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.db.models import Base
import app.db.session as db_session
import app.orchestrator.scheduler as sched_module


@pytest.fixture(autouse=True)
async def isolated_test_db(tmp_path):
    """Ensure each test runs with a completely fresh, isolated SQLite database file."""
    test_db_file = tmp_path / "test_pixel_corp.sqlite"
    test_db_url = f"sqlite+aiosqlite:///{test_db_file.as_posix()}"

    orig_engine = db_session._engine
    test_engine = create_async_engine(test_db_url, echo=False)

    db_session.set_engine_and_factory(test_engine)

    # Initialize tables
    await db_session.init_db(test_engine)

    # Reset active tasks & paused sets in scheduler
    sched_module.scheduler._active_tasks.clear()
    sched_module.scheduler._scheduled_tasks.clear()
    sched_module.scheduler._worker_tasks.clear()
    sched_module.scheduler._paused_projects.clear()

    yield

    await test_engine.dispose()
    db_session.set_engine_and_factory(orig_engine)
