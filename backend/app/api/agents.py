from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.schemas import AgentHireRequest, AgentResponse, AgentUpdateRequest
from app.db.models import Agent, Project
from app.db.session import async_session_factory
from app.domain.org_model import hire_dynamic_agent
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.workspace.workspace_manager import workspace_manager

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
):
    async with async_session_factory() as session:
        stmt = select(Agent)
        if department:
            stmt = stmt.where(Agent.department == department)
        if status:
            stmt = stmt.where(Agent.status == status)
        stmt = stmt.order_by(Agent.level.asc(), Agent.created_at.asc())
        res = await session.execute(stmt)
        return res.scalars().all()


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    async with async_session_factory() as session:
        agt = await session.get(Agent, agent_id)
        if not agt:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agt


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def hire_agent(req: AgentHireRequest):
    new_agent = await hire_dynamic_agent(
        title=req.title,
        department=req.department,
        level=req.level,
        reports_to_agent_id=req.reports_to_agent_id,
        model_tier=req.model_tier,
        system_prompt=req.system_prompt,
        tools=req.tools,
        api_key=req.api_key,
    )
    async with async_session_factory() as session:
        project_ids = (await session.scalars(select(Project.id))).all()
    for project_id in project_ids:
        workspace_manager.get_agent_dir(project_id, new_agent.id)
    return new_agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, req: AgentUpdateRequest):
    async with async_session_factory() as session:
        agt = await session.get(Agent, agent_id)
        if not agt:
            raise HTTPException(status_code=404, detail="Agent not found")

        if req.display_name is not None:
            agt.display_name = req.display_name
        if req.system_prompt is not None:
            agt.system_prompt = req.system_prompt
        if req.model_tier is not None:
            agt.model_tier = req.model_tier
        if req.tools_json is not None:
            agt.tools_json = req.tools_json
        if req.department is not None:
            agt.department = req.department
        if req.api_key is not None:
            # Set or clear custom dedicated API key
            clean_key = req.api_key.strip()
            agt.api_key = clean_key if clean_key else None

        await session.commit()
        await session.refresh(agt)
        return agt


@router.delete("/{agent_id}")
async def retire_agent(agent_id: str):
    async with async_session_factory() as session:
        agt = await session.get(Agent, agent_id)
        if not agt:
            raise HTTPException(status_code=404, detail="Agent not found")
        agt.status = "retired"
        await session.commit()

    await event_bus.emit(
        event_type=EventType.AGENT_RETIRED,
        agent_id=agent_id,
        payload={"agent_id": agent_id, "display_name": agt.display_name},
    )
    return {"success": True, "message": f"Agent {agt.display_name} has retired."}
