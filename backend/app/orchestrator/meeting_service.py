from datetime import datetime, timezone
from sqlalchemy import select
from app.core.ids import generate_id
from app.db.models import Agent, CompanyMeeting, Project, Task
from app.db.session import async_session_factory
from app.events.event_bus import event_bus


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
        event_type="company.meeting_completed",
        project_id=project_id,
        payload={"meeting_id": meeting.id, "title": meeting.title, "decision_count": len(decisions), "trigger": reason},
    )
    return meeting
