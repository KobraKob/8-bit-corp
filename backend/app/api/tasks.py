from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.schemas import TaskResponse
from app.db.models import Message, Task, TaskLog
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.orchestrator.scheduler import scheduler
from app.orchestrator.checkpoints import log_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_detail(task_id: str):
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        msg_stmt = select(Message).where(Message.task_id == task_id).order_by(Message.created_at.asc())
        messages = (await session.execute(msg_stmt)).scalars().all()

        return {
            "task": TaskResponse(
                id=task.id,
                project_id=task.project_id,
                parent_id=task.parent_id,
                root_id=task.root_id,
                depth=task.depth,
                title=task.title,
                description=task.description,
                original_goal=task.original_goal,
                acceptance_criteria_json=task.acceptance_criteria_json or [],
                assignee_agent_id=task.assignee_agent_id,
                creator_agent_id=task.creator_agent_id,
                reviewer_agent_id=task.reviewer_agent_id,
                status=task.status,
                attempt=task.attempt,
                max_attempts=task.max_attempts,
                depends_on_json=task.depends_on_json or [],
                deliverable_artifact_id=task.deliverable_artifact_id,
                review_notes_json=task.review_notes_json or [],
                token_budget=task.token_budget,
                tokens_used=task.tokens_used,
                priority=task.priority,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                error=task.error,
            ),
            "messages": [
                {
                    "id": m.id,
                    "from_agent_id": m.from_agent_id,
                    "to_agent_id": m.to_agent_id,
                    "kind": m.kind,
                    "payload": m.payload_json,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
            "review_notes": task.review_notes_json or [],
        }


@router.get("/{task_id}/logs")
async def get_task_logs(task_id: str, limit: int = 200):
    """Return recent task execution diagnostics in chronological order."""
    limit = max(1, min(limit, 500))
    async with async_session_factory() as session:
        if not await session.get(Task, task_id):
            raise HTTPException(status_code=404, detail="Task not found")
        stmt = (
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": row.id,
                "level": row.level,
                "event": row.event,
                "message": row.message,
                "metadata": row.metadata_json,
                "created_at": row.created_at,
            }
            for row in reversed(rows)
        ]


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    await scheduler.cancel_task_subtree(task_id)
    return {"success": True, "message": f"Task subtree {task_id} cancelled."}


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    async with async_session_factory() as session:
        t = await session.get(Task, task_id)
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        await scheduler.pause_project(t.project_id)
    return {"success": True, "message": f"Project for task {task_id} paused."}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    async with async_session_factory() as session:
        t = await session.get(Task, task_id)
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        await scheduler.resume_project(t.project_id)
    return {"success": True, "message": f"Project for task {task_id} resumed."}


@router.post("/{task_id}/retry")
async def retry_task(task_id: str):
    async with async_session_factory() as session:
        t = await session.get(Task, task_id)
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        t.status = TaskStatus.ASSIGNED.value
        t.attempt = 0
        t.error = None
        t.next_retry_at = None
        t.lease_token = None
        t.lease_expires_at = None
        await session.commit()
    await log_task(task_id, "task.manual_retry", "Task manually reset for a fresh attempt.")
    return {"success": True, "message": f"Task {task_id} reset to assigned for retry."}
