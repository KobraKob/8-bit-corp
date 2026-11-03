from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update

from app.db.models import Agent, Message, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType

router = APIRouter(prefix="/api/office", tags=["office"])


class OfficeAction(BaseModel):
    action: Literal["meeting_start", "meeting_end", "meeting_join", "meeting_leave", "message", "handoff"]
    agent_id: str
    target_agent_id: Optional[str] = None
    task_id: Optional[str] = None
    room: str = Field(default="Boardroom", min_length=1, max_length=80)
    message: Optional[str] = Field(default=None, max_length=2000)


@router.post("/actions")
async def office_action(req: OfficeAction):
    async with async_session_factory() as session:
        actor = await session.get(Agent, req.agent_id)
        if not actor or actor.status != "active":
            raise HTTPException(status_code=404, detail="Active employee not found")

        target = None
        if req.target_agent_id:
            target = await session.get(Agent, req.target_agent_id)
            if not target or target.status != "active":
                raise HTTPException(status_code=404, detail="Target employee not found")

        if req.action in {"meeting_start", "meeting_end", "meeting_join", "meeting_leave"}:
            kind = {
                "meeting_start": EventType.OFFICE_MEETING_STARTED,
                "meeting_end": EventType.OFFICE_MEETING_ENDED,
                "meeting_join": EventType.OFFICE_MEETING_JOINED,
                "meeting_leave": EventType.OFFICE_MEETING_LEFT,
            }[req.action]
            payload = {"room": req.room, "agent_name": actor.display_name}
            if target:
                payload["target_agent_id"] = target.id
            event = await event_bus.emit(kind, agent_id=actor.id, payload=payload)
            return {"success": True, "event_id": event.id}

        if req.action == "message":
            if not target:
                raise HTTPException(status_code=422, detail="A recipient is required")
            message_text = (req.message or "").strip()
            if not message_text:
                raise HTTPException(status_code=422, detail="Message cannot be empty")
            row = Message(
                id=str(uuid4()), task_id=req.task_id, from_agent_id=actor.id,
                to_agent_id=target.id, kind="office_chat",
                payload_json={"text": message_text, "room": req.room},
            )
            session.add(row)
            await session.commit()
            event = await event_bus.emit(
                EventType.OFFICE_CONVERSATION, task_id=req.task_id,
                agent_id=actor.id,
                payload={"to_agent_id": target.id, "from_name": actor.display_name,
                         "to_name": target.display_name, "text": message_text, "room": req.room},
            )
            return {"success": True, "message_id": row.id, "event_id": event.id}

        if req.action == "handoff":
            if not target or not req.task_id:
                raise HTTPException(status_code=422, detail="A recipient and task are required")
            task = await session.get(Task, req.task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task.status not in {TaskStatus.PENDING.value, TaskStatus.ASSIGNED.value} or task.lease_token:
                raise HTTPException(status_code=409, detail="Only queued tasks without an active worker lease can be handed off")
            previous_agent_id = task.assignee_agent_id
            claim_update = await session.execute(
                update(Task)
                .where(
                    Task.id == task.id,
                    Task.status.in_([TaskStatus.PENDING.value, TaskStatus.ASSIGNED.value]),
                    Task.lease_token.is_(None),
                )
                .values(
                    assignee_agent_id=target.id,
                    status=TaskStatus.ASSIGNED.value,
                    next_retry_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            if claim_update.rowcount != 1:
                raise HTTPException(status_code=409, detail="Task was claimed while the handoff was being processed")
            row = Message(
                id=str(uuid4()), task_id=task.id, from_agent_id=actor.id,
                to_agent_id=target.id, kind="task_handoff",
                payload_json={"previous_assignee_id": previous_agent_id, "title": task.title},
            )
            session.add(row)
            await session.commit()
            await event_bus.emit(
                EventType.TASK_ASSIGNED, project_id=task.project_id, task_id=task.id,
                agent_id=target.id,
                payload={"from_agent_id": actor.id, "from_name": actor.display_name,
                         "to_agent_id": target.id, "to_name": target.display_name,
                         "handoff": True, "task_title": task.title},
            )
            event = await event_bus.emit(
                EventType.OFFICE_HANDOFF, project_id=task.project_id, task_id=task.id,
                agent_id=actor.id,
                payload={"to_agent_id": target.id, "from_name": actor.display_name,
                         "to_name": target.display_name, "task_title": task.title},
            )
            return {"success": True, "event_id": event.id}

    raise HTTPException(status_code=422, detail="Unsupported office action")
