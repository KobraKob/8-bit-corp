from typing import Any, Dict, List, Optional
from sqlalchemy import func, select

from app.core.config import get_app_settings
from app.core.errors import CycleDetectedError, InvalidStateTransitionError
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import Agent, Task
from app.db.session import async_session_factory
from app.domain.dag import detect_cycles_in_subtasks
from app.domain.task_fsm import TaskFSM, TaskStateGuard, TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType


class DelegationEngine:
    """Handles agent delegation, role assignment with load balancing, DAG validation, and subtask creation."""

    @staticmethod
    async def find_best_agent(role_key: Optional[str] = None, department: Optional[str] = None) -> Optional[Agent]:
        """Find the active agent for a role or department with the lowest active workload."""
        async with async_session_factory() as session:
            stmt = select(Agent).where(Agent.status == "active")
            if role_key:
                stmt = stmt.where(Agent.role_key == role_key)
            elif department:
                stmt = stmt.where(Agent.department == department)

            result = await session.execute(stmt)
            candidates = result.scalars().all()
            if not candidates:
                # Fallback to any agent in department or CEO
                stmt_fallback = select(Agent).where(Agent.status == "active")
                res_fb = await session.execute(stmt_fallback)
                candidates = res_fb.scalars().all()
                if not candidates:
                    return None

            # Load balancing: choose candidate with least assigned/in_progress tasks
            candidate_ids = [c.id for c in candidates]
            task_counts_stmt = (
                select(Task.assignee_agent_id, func.count(Task.id))
                .where(
                    Task.assignee_agent_id.in_(candidate_ids),
                    Task.status.in_([TaskStatus.ASSIGNED.value, TaskStatus.IN_PROGRESS.value]),
                )
                .group_by(Task.assignee_agent_id)
            )
            count_res = await session.execute(task_counts_stmt)
            workloads = dict(count_res.all())

            # Return candidate with minimal current workload
            best_agent = min(candidates, key=lambda a: workloads.get(a.id, 0))
            return best_agent

    @staticmethod
    async def delegate_subtasks(
        parent_task_id: str,
        creator_agent_id: str,
        subtasks_data: List[Dict[str, Any]],
    ) -> List[Task]:
        """Validate DAG and caps, instantiate child tasks, and persist to database."""
        # 1. Cycle detection
        detect_cycles_in_subtasks(subtasks_data)

        settings = get_app_settings()
        guards = TaskStateGuard(
            max_depth=settings.settings.max_depth,
            max_children=settings.settings.max_children,
            max_attempts=settings.settings.max_attempts,
            token_budget=settings.settings.task_token_budget,
        )

        created_tasks: List[Task] = []

        async with async_session_factory() as session:
            parent = await session.get(Task, parent_task_id)
            if not parent:
                raise ValueError(f"Parent task {parent_task_id} not found")

            # Check existing child count
            child_count_stmt = select(func.count(Task.id)).where(Task.parent_id == parent_task_id)
            existing_count = (await session.execute(child_count_stmt)).scalar() or 0

            # Guard validation
            TaskFSM.validate_delegation_guard(
                current_depth=parent.depth,
                existing_children_count=existing_count,
                new_children_count=len(subtasks_data),
                guards=guards,
            )

            # Map from title or temp_id to new real task ID
            title_to_id: Dict[str, str] = {}
            for item in subtasks_data:
                key = item.get("id") or item.get("temp_id") or item.get("title")
                title_to_id[key] = generate_id("tsk")

            for item in subtasks_data:
                sub_id = title_to_id[item.get("id") or item.get("temp_id") or item.get("title")]
                role_key = item.get("role_key")
                dept = item.get("department")

                assignee = await DelegationEngine.find_best_agent(role_key=role_key, department=dept)
                assignee_id = assignee.id if assignee else creator_agent_id
                reviewer_id = assignee.reports_to_agent_id if assignee and assignee.reports_to_agent_id else creator_agent_id

                # Resolve depends_on keys to real subtask IDs where possible
                resolved_deps = [title_to_id.get(dep, dep) for dep in item.get("depends_on", [])]

                child_task = Task(
                    id=sub_id,
                    project_id=parent.project_id,
                    parent_id=parent.id,
                    root_id=parent.root_id or parent.id,
                    depth=parent.depth + 1,
                    title=item["title"],
                    description=item.get("description", item["title"]),
                    original_goal=parent.original_goal,
                    acceptance_criteria_json=item.get("acceptance_criteria", []),
                    assignee_agent_id=assignee_id,
                    creator_agent_id=creator_agent_id,
                    reviewer_agent_id=reviewer_id,
                    status=TaskStatus.ASSIGNED.value,
                    attempt=0,
                    max_attempts=guards.max_attempts,
                    depends_on_json=resolved_deps,
                    token_budget=guards.token_budget,
                    priority=parent.priority + 1,
                )
                session.add(child_task)
                created_tasks.append(child_task)

            await session.commit()

        # Emit events
        for ct in created_tasks:
            await event_bus.emit(
                event_type=EventType.TASK_CREATED,
                project_id=ct.project_id,
                task_id=ct.id,
                agent_id=ct.assignee_agent_id,
                payload={
                    "title": ct.title,
                    "depth": ct.depth,
                    "assignee_agent_id": ct.assignee_agent_id,
                    "parent_id": ct.parent_id,
                },
            )
            await event_bus.emit(
                event_type=EventType.TASK_DELEGATED,
                project_id=ct.project_id,
                task_id=ct.id,
                agent_id=creator_agent_id,
                payload={"subtask_id": ct.id, "to_agent_id": ct.assignee_agent_id},
            )

        return created_tasks
