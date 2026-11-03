import io
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select, update

from app.api.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    TaskResponse,
    TaskSubmitRequest,
    TaskTreeNode,
)
from app.core.ids import generate_id
from app.db.models import Agent, Approval, Message, Project, Task, WikiNote
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.orchestrator.scheduler import scheduler
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.workspace.workspace_manager import workspace_manager

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(req: ProjectCreateRequest):
    proj_id = generate_id("proj")
    async with async_session_factory() as session:
        proj = Project(
            id=proj_id,
            name=req.name,
            client_name=req.client_name,
            brief=req.brief,
            due_at=req.due_at,
            settings_json=req.settings,
            status="active",
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        active_agent_ids = (await session.scalars(select(Agent.id).where(Agent.status == "active"))).all()

    # Provision a private workspace for every currently active agent.
    workspace_manager.provision_agent_directories(proj_id, active_agent_ids)

    return proj


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    async with async_session_factory() as session:
        # Backfill projects completed before lifecycle status was persisted.
        completed_ids = (await session.execute(
            select(Task.project_id).where(
                Task.parent_id.is_(None),
                Task.status == TaskStatus.DONE.value,
            )
        )).scalars().all()
        if completed_ids:
            await session.execute(
                update(Project)
                .where(Project.id.in_(completed_ids), Project.status == "active")
                .values(status="completed")
            )
            await session.commit()

        stmt = select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
        res = await session.execute(stmt)
        return res.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    async with async_session_factory() as session:
        proj = await session.get(Project, project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return proj


@router.post("/{project_id}/pause", response_model=ProjectResponse)
async def pause_project(project_id: str):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project: raise HTTPException(status_code=404, detail="Project not found")
        if project.status in ("completed", "stopped"): raise HTTPException(status_code=409, detail=f"Cannot pause a {project.status} project")
        project.status = "paused"
        await session.commit()
        await session.refresh(project)
    await scheduler.pause_project(project_id)
    return project


@router.post("/{project_id}/resume", response_model=ProjectResponse)
async def resume_project(project_id: str):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project: raise HTTPException(status_code=404, detail="Project not found")
        if project.status != "paused": raise HTTPException(status_code=409, detail="Only paused projects can be resumed")
        project.status = "active"
        await session.commit()
        await session.refresh(project)
    await scheduler.resume_project(project_id)
    return project


@router.post("/{project_id}/stop", response_model=ProjectResponse)
async def stop_project(project_id: str):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project: raise HTTPException(status_code=404, detail="Project not found")
        if project.status == "completed": raise HTTPException(status_code=409, detail="Completed projects cannot be stopped")
        if project.status == "stopped": return project
        root_ids = (await session.execute(select(Task.id).where(Task.project_id == project_id, Task.parent_id.is_(None)))).scalars().all()
        project.status = "stopped"
        await session.commit()
        await session.refresh(project)
    await scheduler.pause_project(project_id)
    for root_id in root_ids: await scheduler.cancel_task_subtree(root_id)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str):
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project: raise HTTPException(status_code=404, detail="Project not found")
        if project.status not in ("completed", "stopped"):
            raise HTTPException(status_code=409, detail="Stop the project before deleting it. This protects running work.")
        task_ids = select(Task.id).where(Task.project_id == project_id)
        await session.execute(delete(Message).where(Message.task_id.in_(task_ids)))
        await session.execute(delete(Approval).where(Approval.project_id == project_id))
        await session.execute(delete(WikiNote).where(WikiNote.project_id == project_id))
        await session.delete(project)
        await session.commit()
    scheduler._paused_projects.discard(project_id)
    project_dir = workspace_manager.get_project_dir(project_id)
    if project_dir.exists(): shutil.rmtree(project_dir)
    return None


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_project_task(project_id: str, req: TaskSubmitRequest):
    """Client/Founder submits a task to the project. It is automatically assigned to CEO (depth 0)."""
    task_id = generate_id("tsk")
    async with async_session_factory() as session:
        proj = await session.get(Project, project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        # Find CEO
        ceo_stmt = select(Agent).where(Agent.role_key == "ceo")
        ceo = (await session.execute(ceo_stmt)).scalar_one_or_none()
        if not ceo:
            raise HTTPException(status_code=500, detail="CEO agent not seeded")

        task = Task(
            id=task_id,
            project_id=project_id,
            depth=0,
            title=req.title,
            description=req.description,
            original_goal=req.description,
            acceptance_criteria_json=req.acceptance_criteria,
            assignee_agent_id=ceo.id,
            status=TaskStatus.ASSIGNED.value,
            priority=req.priority,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

    await event_bus.emit(
        event_type=EventType.TASK_CREATED,
        project_id=project_id,
        task_id=task.id,
        agent_id=ceo.id,
        payload={"title": task.title, "depth": 0, "assignee_id": ceo.id},
    )

    return task


@router.get("/{project_id}/tree", response_model=List[TaskTreeNode])
async def get_task_tree(project_id: str):
    """Retrieve full hierarchical task tree with statuses for visualization."""
    async with async_session_factory() as session:
        stmt = select(Task).where(Task.project_id == project_id).order_by(Task.depth.asc(), Task.created_at.asc())
        tasks = (await session.execute(stmt)).scalars().all()

        nodes: dict[str, TaskTreeNode] = {}
        roots: list[TaskTreeNode] = []

        for t in tasks:
            node = TaskTreeNode(
                id=t.id,
                project_id=t.project_id,
                parent_id=t.parent_id,
                root_id=t.root_id,
                depth=t.depth,
                title=t.title,
                description=t.description,
                original_goal=t.original_goal,
                acceptance_criteria_json=t.acceptance_criteria_json or [],
                assignee_agent_id=t.assignee_agent_id,
                creator_agent_id=t.creator_agent_id,
                reviewer_agent_id=t.reviewer_agent_id,
                status=t.status,
                attempt=t.attempt,
                max_attempts=t.max_attempts,
                depends_on_json=t.depends_on_json or [],
                deliverable_artifact_id=t.deliverable_artifact_id,
                review_notes_json=t.review_notes_json or [],
                token_budget=t.token_budget,
                tokens_used=t.tokens_used,
                priority=t.priority,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
                error=t.error,
                children=[],
            )
            nodes[t.id] = node
            if t.parent_id and t.parent_id in nodes:
                nodes[t.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots


@router.get("/{project_id}/export")
async def export_project_zip(project_id: str):
    """Export the entire project deliverables and artifacts as a .zip bundle."""
    proj_dir = workspace_manager.get_project_dir(project_id)
    if not proj_dir.exists():
        raise HTTPException(status_code=404, detail="Project workspace does not exist")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in proj_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(proj_dir)
                zip_file.write(file_path, arcname=str(rel_path.as_posix()))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=project_{project_id}.zip"},
    )
