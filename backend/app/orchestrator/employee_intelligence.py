from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.models import Agent, Task
from app.db.session import async_session_factory


async def get_employee_performance():
    """Compute transparent performance indicators from persisted task history."""
    async with async_session_factory() as session:
        agents = (await session.scalars(select(Agent).order_by(Agent.department, Agent.display_name))).all()
        tasks = (await session.scalars(select(Task))).all()

    by_agent = defaultdict(list)
    for task in tasks:
        if task.assignee_agent_id:
            by_agent[task.assignee_agent_id].append(task)

    now = datetime.now(timezone.utc)
    results = []
    for agent in agents:
        assigned = by_agent.get(agent.id, [])
        completed = [task for task in assigned if task.status == "done"]
        failed = [task for task in assigned if task.status == "failed"]
        cancelled = [task for task in assigned if task.status == "cancelled"]
        revised = [task for task in assigned if max(0, int(task.attempt or 0)) > 0 or bool(task.review_notes_json)]
        durations = []
        for task in completed:
            if task.started_at and task.completed_at:
                start = task.started_at if task.started_at.tzinfo else task.started_at.replace(tzinfo=timezone.utc)
                end = task.completed_at if task.completed_at.tzinfo else task.completed_at.replace(tzinfo=timezone.utc)
                durations.append(max(0.0, (end - start).total_seconds()))
        completed_count = len(completed)
        total = len(assigned)
        results.append({
            "agent_id": agent.id,
            "display_name": agent.display_name,
            "department": agent.department,
            "role_key": agent.role_key,
            "status": agent.status,
            "tasks_assigned": total,
            "tasks_completed": completed_count,
            "tasks_failed": len(failed),
            "tasks_cancelled": len(cancelled),
            "revision_count": sum(max(0, int(task.attempt or 0)) for task in assigned),
            "tasks_revised": len(revised),
            "completion_rate": round(completed_count / total, 3) if total else None,
            "reliability_rate": round(completed_count / (completed_count + len(failed)), 3) if completed_count + len(failed) else None,
            "average_completion_seconds": round(sum(durations) / len(durations), 1) if durations else None,
            "average_quality_score": round(completed_count / max(1, completed_count + len(revised)), 3) if total else None,
            "quality_score_note": "Proxy: completed tasks divided by completed tasks plus tasks with revision evidence; not an LLM quality judgment.",
            "last_completed_at": max((task.completed_at for task in completed if task.completed_at), default=None),
        })
    return results
