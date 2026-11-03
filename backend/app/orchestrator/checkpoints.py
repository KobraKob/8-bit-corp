"""Durable task checkpoints and structured task-level execution logs."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.config import get_app_settings
from app.core.ids import generate_id
from app.db.models import Task, TaskLog
from app.db.session import async_session_factory


async def log_task(
    task_id: str,
    event: str,
    message: str,
    level: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    async with async_session_factory() as session:
        if not await session.get(Task, task_id):
            return
        session.add(TaskLog(
            id=generate_id("log"), task_id=task_id, level=level,
            event=event, message=message, metadata_json=metadata or {},
        ))
        await session.commit()


async def save_task_checkpoint(
    task_id: str,
    checkpoint: Dict[str, Any],
    *,
    lease_token: Optional[str] = None,
    event: str = "checkpoint.saved",
    message: str = "Task checkpoint saved.",
    level: str = "debug",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Merge a checkpoint and renew its worker lease in one transaction."""
    now = datetime.now(timezone.utc)
    lease_seconds = get_app_settings().settings.task_lease_seconds
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            return False
        if lease_token and task.lease_token != lease_token:
            raise RuntimeError("Task worker lease was lost; execution must stop to avoid duplicate work.")
        merged = dict(task.checkpoint_json or {})
        merged.update(checkpoint)
        merged["updated_at"] = now.isoformat()
        task.checkpoint_json = merged
        if lease_token:
            task.lease_expires_at = now + timedelta(seconds=lease_seconds)
        session.add(TaskLog(
            id=generate_id("log"), task_id=task_id, level=level,
            event=event, message=message, metadata_json=metadata or {},
        ))
        await session.commit()
        return True


async def load_task_checkpoint(task_id: str) -> Dict[str, Any]:
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        return dict(task.checkpoint_json or {}) if task else {}
