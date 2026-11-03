from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.schemas import TaskResponse
from app.db.models import Message, Project, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.orchestrator.scheduler import scheduler

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


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    await scheduler.cancel_task_subtree(task_id)
    return {"success": True, "message": f"Task subtree {task_id} cancelled."}


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    async with async_session_factory() as session:
        t = await session.get(Task, task_id)
        if not t: raise HTTPException(status_code=404, detail="Task not found")
        project = await session.get(Project, t.project_id)
        if project and project.status not in ("completed", "stopped"):
            project.status = "paused"
            await session.commit()
        await scheduler.pause_project(t.project_id)
    return {"success": True, "message": f"Project for task {task_id} paused."}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    async with async_session_factory() as session:
        t = await session.get(Task, task_id)
        if not t: raise HTTPException(status_code=404, detail="Task not found")
        project = await session.get(Project, t.project_id)
        if project and project.status == "paused":
            project.status = "active"
            await session.commit()
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
        await session.commit()
    return {"success": True, "message": f"Task {task_id} reset to assigned for retry."}
