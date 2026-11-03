from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, update

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
        # 1. Validate identifiers and dependency graph before writing anything.
        if not subtasks_data:
            raise ValueError("At least one subtask is required for delegation.")
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

            # A task may delegate once. Existing children make retries idempotent.
            existing_children_stmt = select(Task).where(Task.parent_id == parent_task_id).order_by(Task.created_at.asc())
            existing_children = (await session.execute(existing_children_stmt)).scalars().all()
            if existing_children:
                return existing_children
            max_delegations = settings.settings.max_delegations_per_task
            if parent.delegation_count >= max_delegations:
                raise InvalidStateTransitionError(
                    f"Task {parent_task_id} reached its delegation limit ({max_delegations})."
                )

            child_count_stmt = select(func.count(Task.id)).where(Task.parent_id == parent_task_id)
            existing_count = (await session.execute(child_count_stmt)).scalar() or 0
            project_task_count = (await session.execute(
                select(func.count(Task.id)).where(Task.project_id == parent.project_id)
            )).scalar() or 0
            if project_task_count + len(subtasks_data) > settings.settings.max_project_tasks:
                raise InvalidStateTransitionError(
                    f"Delegation would exceed the project task limit ({settings.settings.max_project_tasks})."
                )

            # Claim this task's single delegation slot atomically. This prevents
            # concurrent workers from creating duplicate child trees.
            delegation_claim = await session.execute(
                update(Task)
                .where(Task.id == parent_task_id, Task.delegation_count == parent.delegation_count)
                .values(delegation_count=Task.delegation_count + 1)
            )
            if delegation_claim.rowcount != 1:
                concurrent_children = (await session.execute(existing_children_stmt)).scalars().all()
                if concurrent_children:
                    return concurrent_children
                raise InvalidStateTransitionError("Another worker already consumed this task's delegation slot.")

            # Guard validation
            TaskFSM.validate_delegation_guard(
                current_depth=parent.depth,
                existing_children_count=existing_count,
                new_children_count=len(subtasks_data),
                guards=guards,
            )

            # Map every declared alias to one stable database task ID.
            title_to_id: Dict[str, str] = {}
            for item in subtasks_data:
                sub_id = generate_id("tsk")
                for alias in {item.get("id"), item.get("temp_id"), item.get("title")}:
                    if alias:
                        if alias in title_to_id:
                            raise ValueError(f"Duplicate delegated task identifier or title: {alias}")
                        title_to_id[alias] = sub_id

            for item in subtasks_data:
                sub_id = title_to_id[item.get("id") or item.get("temp_id") or item.get("title")]
                role_key = item.get("role_key")
                dept = item.get("department")

                assignee = await DelegationEngine.find_best_agent(role_key=role_key, department=dept)
                assignee_id = assignee.id if assignee else creator_agent_id
                reviewer_id = assignee.reports_to_agent_id if assignee and assignee.reports_to_agent_id else creator_agent_id

                # Resolve dependencies to stable IDs. Reject missing or ambiguous
                # external references instead of leaving a task permanently queued.
                resolved_deps = []
                for dependency in item.get("depends_on", []):
                    dependency_id = title_to_id.get(dependency)
                    if dependency_id is None:
                        matches = (await session.execute(
                            select(Task).where(
                                (Task.id == dependency) | (Task.title == dependency),
                                Task.project_id == parent.project_id,
                            )
                        )).scalars().all()
                        if len(matches) != 1:
                            raise ValueError(
                                f"Dependency '{dependency}' for '{item['title']}' "
                                f"must resolve to exactly one task in this project."
                            )
                        dependency_id = matches[0].id
                    if dependency_id == sub_id:
                        raise ValueError(f"Task '{item['title']}' cannot depend on itself.")
                    if dependency_id == parent_task_id:
                        raise ValueError(f"Task '{item['title']}' cannot depend on its parent task.")
                    if dependency_id not in resolved_deps:
                        resolved_deps.append(dependency_id)

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
