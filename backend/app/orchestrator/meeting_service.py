from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from app.llm.router import llm_router
from app.llm.types import ChatMessage
from sqlalchemy import select
from app.core.ids import generate_id
from app.db.models import Agent, CompanyMeeting, Project, Task
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType


class ManagerContribution(BaseModel):
    summary: str = Field(description="Department position on current project health")
    blockers: List[str] = Field(default_factory=list)
    coordination_requests: List[str] = Field(default_factory=list)
    proposed_actions: List[str] = Field(default_factory=list)


class MeetingDecisionItem(BaseModel):
    decision: str
    action: str
    owner_department: str
    task_id: Optional[str] = None
    accountable_manager_id: Optional[str] = None


class MeetingSynthesis(BaseModel):
    executive_summary: str
    decisions: List[MeetingDecisionItem] = Field(default_factory=list)


async def convene_project_meeting(project_id: str, reason: str = "manual", trigger_task_id: str | None = None):
    """Create evidence-based virtual meeting minutes for a complex or blocked project."""
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            return None
        if trigger_task_id:
            existing = await session.scalar(select(CompanyMeeting).where(
                CompanyMeeting.project_id == project_id,
                CompanyMeeting.trigger_task_id == trigger_task_id,
            ))
            if existing:
                return existing
        tasks = (await session.scalars(select(Task).where(Task.project_id == project_id))).all()
        agents = (await session.scalars(select(Agent).where(Agent.status == "active"))).all()
        agent_by_id = {agent.id: agent for agent in agents}
        departments = sorted({
            agent_by_id[task.assignee_agent_id].department
            for task in tasks if task.assignee_agent_id in agent_by_id
        })
        blocked = [task for task in tasks if task.status in ("blocked", "failed")]
        revision = [task for task in tasks if task.status == "revision_requested" or (task.attempt or 0) > 1]
        if reason == "automatic" and not blocked and len(departments) < 3 and len(tasks) < 8:
            return None

        managers = [agent for agent in agents if agent.level <= 3]
        ceo = next((agent for agent in agents if agent.role_key == "ceo"), None)
        attendee_agents = []
        if ceo:
            attendee_agents.append(ceo)
        for department in departments:
            manager = next((agent for agent in managers if agent.department == department), None)
            if manager and manager.id not in {a.id for a in attendee_agents}:
                attendee_agents.append(manager)
        if not attendee_agents:
            attendee_agents = [agent for agent in agents if agent.level <= 2][:5]

        discussion = []
        decisions = []
        for department in departments:
            dept_tasks = [
                task for task in tasks
                if task.assignee_agent_id in agent_by_id and agent_by_id[task.assignee_agent_id].department == department
            ]
            dept_blockers = [task for task in dept_tasks if task.status in ("blocked", "failed")]
            dept_revisions = [task for task in dept_tasks if task.status == "revision_requested" or (task.attempt or 0) > 1]
            discussion.append({
                "department": department,
                "manager_id": next((a.id for a in attendee_agents if a.department == department), None),
                "workload": len(dept_tasks),
                "blockers": [{"task_id": t.id, "title": t.title, "status": t.status, "reason": t.error} for t in dept_blockers],
                "revision_items": [{"task_id": t.id, "title": t.title, "revision_attempts": t.attempt} for t in dept_revisions],
                "position": (
                    f"{len(dept_blockers)} blocker(s) need resolution and {len(dept_revisions)} item(s) need quality follow-up."
                    if dept_blockers or dept_revisions else
                    f"{len(dept_tasks)} work package(s) are active; confirm dependencies and handoffs."
                ),
            })
        for task in blocked:
            owner = agent_by_id.get(task.assignee_agent_id)
            decisions.append({
                "decision": "Escalate blocked work to the responsible department manager",
                "action": "Resolve blocker, then return task to assigned or revision_requested",
                "task_id": task.id,
                "task_title": task.title,
                "owner_department": owner.department if owner else "Unassigned",
                "accountable_manager_id": next((a.id for a in attendee_agents if owner and a.department == owner.department), ceo.id if ceo else None),
                "status": "open",
            })
        for task in revision:
            owner = agent_by_id.get(task.assignee_agent_id)
            decisions.append({
                "decision": "Review revision feedback before further integration",
                "action": "Address recorded review notes and resubmit acceptance criteria",
                "task_id": task.id,
                "task_title": task.title,
                "owner_department": owner.department if owner else "Unassigned",
                "accountable_manager_id": next((a.id for a in attendee_agents if owner and a.department == owner.department), ceo.id if ceo else None),
                "status": "open",
            })
        if not decisions:
            decisions.append({
                "decision": "Confirm cross-department dependencies and handoff owners",
                "action": "Managers verify dependency order and shared deliverable ownership",
                "task_id": None,
                "task_title": None,
                "owner_department": "Cross-functional",
                "accountable_manager_id": ceo.id if ceo else (attendee_agents[0].id if attendee_agents else None),
                "status": "open",
            })

        # Each attending manager contributes a structured position using the
        # company's configured model provider. If a provider is unavailable,
        # the evidence-based department summary above remains as a safe fallback.
        async def manager_contribution(manager):
            own_tasks = [
                task for task in tasks
                if task.assignee_agent_id in agent_by_id
                and agent_by_id[task.assignee_agent_id].department == manager.department
            ]
            brief = "\n".join(
                f"- {task.title}: {task.status}; attempts={task.attempt}; "
                f"error={task.error or 'none'}; review_notes={'; '.join(task.review_notes_json or [])}"
                for task in own_tasks[:20]
            ) or "No work packages assigned to this department."
            try:
                result = await llm_router.execute_structured(
                    tier=manager.model_tier,
                    messages=[
                        ChatMessage(role="system", content=manager.system_prompt),
                        ChatMessage(
                            role="user",
                            content=(
                                f"You are attending a project coordination meeting as {manager.display_name}, "
                                f"manager of {manager.department}. Review the current evidence and contribute "
                                f"concrete coordination decisions. Do not invent facts.\n"
                                f"Project: {project.name}\nProject brief: {project.brief[:3000]}\n"
                                f"Department work packages:\n{brief}\n"
                                "Identify blockers, dependencies on other departments, and specific next actions."
                            ),
                        ),
                    ],
                    schema_cls=ManagerContribution,
                    task_id=trigger_task_id,
                    agent_id=manager.id,
                )
                return {
                    "department": manager.department,
                    "manager_id": manager.id,
                    "manager_name": manager.display_name,
                    "position": result.summary,
                    "blockers": result.blockers,
                    "coordination_requests": result.coordination_requests,
                    "proposed_actions": result.proposed_actions,
                    "source": "manager_model",
                }
            except Exception as exc:
                return {
                    "department": manager.department,
                    "manager_id": manager.id,
                    "manager_name": manager.display_name,
                    "position": next((d["position"] for d in discussion if d["department"] == manager.department), "No department update."),
                    "blockers": [],
                    "coordination_requests": [],
                    "proposed_actions": [],
                    "source": "evidence_fallback",
                    "error": str(exc)[:300],
                }

        if attendee_agents:
            import asyncio
            contributions = await asyncio.gather(*(manager_contribution(manager) for manager in attendee_agents[:6]))
            discussion.extend(contributions)

        # The CEO consolidates manager contributions into a short decision log.
        if ceo and discussion:
            try:
                synthesis = await llm_router.execute_structured(
                    tier=ceo.model_tier,
                    messages=[
                        ChatMessage(role="system", content=ceo.system_prompt),
                        ChatMessage(
                            role="user",
                            content=(
                                f"Chair the coordination meeting for {project.name}. "
                                "Synthesize only evidence-backed decisions. Each decision needs an accountable department, "
                                "an action, and a task ID when one exists.\n"
                                f"Manager discussion: {discussion}\n"
                                f"Existing blocker/revision actions: {decisions}"
                            ),
                        ),
                    ],
                    schema_cls=MeetingSynthesis,
                    task_id=trigger_task_id,
                    agent_id=ceo.id,
                )
                if synthesis.decisions:
                    decisions = [{
                        "decision": item.decision,
                        "action": item.action,
                        "task_id": item.task_id,
                        "task_title": next((task.title for task in tasks if task.id == item.task_id), None),
                        "owner_department": item.owner_department,
                        "accountable_manager_id": item.accountable_manager_id,
                        "status": "open",
                    } for item in synthesis.decisions]
                discussion.append({
                    "department": "Executive office",
                    "manager_id": ceo.id,
                    "position": synthesis.executive_summary,
                    "source": "ceo_synthesis",
                })
            except Exception:
                # Keep the deterministic decision log if the synthesis model fails.
                pass

        meeting = CompanyMeeting(
            id=generate_id("mtg"),
            project_id=project_id,
            title=f"{project.name} — coordination meeting",
            trigger=reason,
            trigger_task_id=trigger_task_id,
            status="completed",
            attendees_json=[{"agent_id": a.id, "name": a.display_name, "department": a.department, "role": a.role_key} for a in attendee_agents],
            agenda_json=[
                "Review project health and cross-department dependencies",
                "Discuss blockers and revision patterns",
                "Assign accountable owners and next actions",
            ],
            discussion_json=discussion,
            decisions_json=decisions,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        session.add(meeting)
        await session.commit()
        await session.refresh(meeting)

    await event_bus.emit(
        event_type=EventType.COMPANY_MEETING_COMPLETED,
        project_id=project_id,
        payload={"meeting_id": meeting.id, "title": meeting.title, "decision_count": len(decisions), "trigger": reason},
    )
    return meeting
