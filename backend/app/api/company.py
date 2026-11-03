from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import CompanyMeeting, Project, WikiNote
from app.db.session import async_session_factory
from app.orchestrator.company_memory import save_memory, search_memory
from app.orchestrator.employee_intelligence import get_employee_performance
from app.orchestrator.meeting_service import convene_project_meeting

router = APIRouter(prefix="/api/company", tags=["company"])


class MemoryWriteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    tags: str = ""
    project_id: Optional[str] = None


class MeetingRequest(BaseModel):
    project_id: str
    reason: str = "manual"


@router.get("/memory")
async def list_company_memory(q: str = "", project_id: Optional[str] = None, limit: int = Query(30, ge=1, le=100)):
    notes = await search_memory(q, project_id, limit)
    return [{
        "id": note.id, "project_id": note.project_id, "title": note.title,
        "body": note.body, "tags": note.tags, "created_by_agent_id": note.created_by_agent_id,
        "updated_at": note.updated_at,
    } for note in notes]


@router.post("/memory")
async def write_company_memory(req: MemoryWriteRequest):
    if req.project_id:
        async with async_session_factory() as session:
            if not await session.get(Project, req.project_id):
                raise HTTPException(status_code=404, detail="Project not found")
    note = await save_memory(title=req.title, body=req.body, tags=req.tags, project_id=req.project_id)
    return {
        "id": note.id, "project_id": note.project_id, "title": note.title,
        "body": note.body, "tags": note.tags, "updated_at": note.updated_at,
    }


@router.get("/employees/performance")
async def employee_performance():
    return await get_employee_performance()


@router.get("/meetings")
async def list_meetings(project_id: Optional[str] = None, limit: int = Query(30, ge=1, le=100)):
    async with async_session_factory() as session:
        stmt = select(CompanyMeeting)
        if project_id:
            stmt = stmt.where(CompanyMeeting.project_id == project_id)
        rows = (await session.scalars(stmt.order_by(CompanyMeeting.created_at.desc()).limit(limit))).all()
        return [{
            "id": m.id, "project_id": m.project_id, "title": m.title, "trigger": m.trigger,
            "status": m.status, "attendees": m.attendees_json, "agenda": m.agenda_json,
            "discussion": m.discussion_json, "decisions": m.decisions_json,
            "created_at": m.created_at, "completed_at": m.completed_at,
        } for m in rows]


@router.post("/meetings")
async def create_meeting(req: MeetingRequest):
    meeting = await convene_project_meeting(req.project_id, req.reason)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Project not found or meeting is not required")
    return {
        "id": meeting.id, "project_id": meeting.project_id, "title": meeting.title,
        "trigger": meeting.trigger, "status": meeting.status,
        "attendees": meeting.attendees_json, "agenda": meeting.agenda_json,
        "discussion": meeting.discussion_json, "decisions": meeting.decisions_json,
        "created_at": meeting.created_at, "completed_at": meeting.completed_at,
    }
