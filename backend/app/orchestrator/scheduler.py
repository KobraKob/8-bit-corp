import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy import select, update

from app.agents.runtime import AgentRuntime
from app.core.config import get_app_settings
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import Agent, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskFSM, TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.orchestrator.delegation import DelegationEngine
from app.orchestrator.integration import IntegrationEngine
from app.orchestrator.review import ReviewEngine
from app.orchestrator.triage import CEOTriage


def dependencies_are_complete(dependencies: List[str], statuses_by_id: Dict[str, str]) -> bool:
    """Return true only when every referenced task ID exists and is done."""
    return all(statuses_by_id.get(dependency_id) == TaskStatus.DONE.value for dependency_id in set(dependencies))


class Scheduler:
    """Async execution scheduler with crash-safety, depth-first queueing, and lifecycle management."""

    def __init__(self) -> None:
        self.settings = get_app_settings()
        self.running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._active_tasks: Set[str] = set()
        # Reserve work before spawning coroutines; create_task() does not run immediately.
        self._scheduled_tasks: Set[str] = set()
        self._paused_projects: Set[str] = set()

    async def recover_stuck_tasks_on_startup(self) -> None:
        """Crash safety: re-queue tasks stranded in_progress or integrating back to assigned."""
        async with async_session_factory() as session:
            stmt = select(Task).where(
                Task.status.in_([TaskStatus.IN_PROGRESS.value, TaskStatus.INTEGRATING.value])
            )
            res = await session.execute(stmt)
            stranded = res.scalars().all()
            if stranded:
                logger.info(f"Crash recovery: found {len(stranded)} stranded tasks. Re-queuing to assigned...")
                for t in stranded:
                    t.status = TaskStatus.ASSIGNED.value
                await session.commit()

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        await self.recover_stuck_tasks_on_startup()
        self._worker_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler background loop started.")

    async def stop(self) -> None:
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped.")

    async def pause_project(self, project_id: str) -> None:
        self._paused_projects.add(project_id)

    async def resume_project(self, project_id: str) -> None:
        self._paused_projects.discard(project_id)

    async def cancel_task_subtree(self, task_id: str) -> None:
        """Cancel a task and all its recursive descendant subtasks."""
        async with async_session_factory() as session:
            # Recursive descent
            to_cancel = [task_id]
            visited = set()

            while to_cancel:
                curr_id = to_cancel.pop(0)
                if curr_id in visited:
                    continue
                visited.add(curr_id)

                task = await session.get(Task, curr_id)
                if task and not TaskFSM.is_terminal(TaskStatus(task.status)):
                    task.status = TaskStatus.CANCELLED.value
                    await event_bus.emit(
                        event_type=EventType.TASK_CANCELLED,
                        project_id=task.project_id,
                        task_id=task.id,
                        payload={"reason": "Cancelled by user"},
                    )

                # Find children
                child_stmt = select(Task.id).where(Task.parent_id == curr_id)
                res = await session.execute(child_stmt)
                children_ids = res.scalars().all()
                to_cancel.extend(children_ids)

            await session.commit()

    async def _fetch_ready_tasks(self) -> List[Task]:
        """Fetch all tasks that are currently assigned and whose dependencies are completely done."""
        async with async_session_factory() as session:
            stmt = select(Task).where(
                Task.status == TaskStatus.ASSIGNED.value,
            )
            res = await session.execute(stmt)
            assigned_tasks = res.scalars().all()

            ready: List[Task] = []
            for t in assigned_tasks:
                if t.project_id in self._paused_projects:
                    continue
                if t.id in self._active_tasks:
                    continue

                # Check dependencies
                deps = t.depends_on_json or []
                if not deps:
                    ready.append(t)
                else:
                    # Dependencies are persisted as task IDs. Titles are not unique.
                    dep_stmt = select(Task.id, Task.status).where(
                        Task.id.in_(deps),
                        Task.project_id == t.project_id,
                    )
                    dep_res = await session.execute(dep_stmt)
                    dependency_statuses = dict(dep_res.all())
                    # Missing IDs are unresolved dependencies, never implicitly ready.
                    if dependencies_are_complete(deps, dependency_statuses):
                        ready.append(t)

            # Sort: Depth-first bias (higher depth first), then priority (lower number is higher priority), then created_at
            ready.sort(key=lambda t: (-t.depth, t.priority, t.created_at))
            return ready

    async def _process_task(self, task_id: str) -> None:
        self._active_tasks.add(task_id)
        self._scheduled_tasks.discard(task_id)
        try:
            async with async_session_factory() as session:
                # Conditional update is the claim: only one worker/process can win it.
                claim = await session.execute(
                    update(Task)
                    .where(Task.id == task_id, Task.status == TaskStatus.ASSIGNED.value)
                    .values(status=TaskStatus.IN_PROGRESS.value, started_at=datetime.now(timezone.utc))
                )
                if claim.rowcount != 1:
                    await session.rollback()
                    return
                await session.commit()
                task = await session.get(Task, task_id)
                if not task:
                    return
                proj_id = task.project_id
                t_id = task.id
                agt_id = task.assignee_agent_id
                t_title = task.title
                t_depth = task.depth

            await event_bus.emit(
                event_type=EventType.TASK_STARTED,
                project_id=proj_id,
                task_id=t_id,
                agent_id=agt_id,
                payload={"title": t_title, "depth": t_depth},
            )

            # Case A: Root CEO task triage
            if task.depth == 0 and task.parent_id is None:
                async with async_session_factory() as session:
                    ceo = await session.get(Agent, task.assignee_agent_id)
                triage_plan = await CEOTriage.triage_project(task, ceo)

                # Delegate objectives
                subtask_dicts = [
                    {
                        "title": obj.title,
                        "department": obj.department,
                        "role_key": obj.role_key,
                        "description": obj.description,
                        "acceptance_criteria": obj.acceptance_criteria,
                        "depends_on": obj.depends_on,
                    }
                    for obj in triage_plan.objectives
                ]
                await DelegationEngine.delegate_subtasks(
                    parent_task_id=task.id,
                    creator_agent_id=task.assignee_agent_id,
                    subtasks_data=subtask_dicts,
                )
                return

            # Ensure assignee_agent_id is present
            assignee_id = task.assignee_agent_id
            if not assignee_id:
                async with async_session_factory() as session:
                    ceo_stmt = select(Agent.id).where(Agent.role_key == "ceo")
                    assignee_id = (await session.execute(ceo_stmt)).scalar()
                    t = await session.get(Task, task.id)
                    t.assignee_agent_id = assignee_id
                    await session.commit()

            # Case B: Standard worker agent execution turn
            runtime = AgentRuntime(task_id=task.id, agent_id=assignee_id)
            result = await runtime.run_turn()
            terminal_action = result.get("terminal_action")

            if terminal_action:
                tool_name = terminal_action.get("tool")
                args = terminal_action.get("arguments", {})

                if tool_name == "delegate":
                    subtasks = args.get("subtasks", [])
                    await DelegationEngine.delegate_subtasks(
                        parent_task_id=task.id,
                        creator_agent_id=task.assignee_agent_id,
                        subtasks_data=subtasks,
                    )

                elif tool_name == "submit_deliverable":
                    async with async_session_factory() as session:
                        t = await session.get(Task, task.id)
                        t.status = TaskStatus.IN_REVIEW.value
                        art_ids = args.get("artifact_ids", [])
                        if art_ids:
                            t.deliverable_artifact_id = art_ids[0]
                        await session.commit()

                    await event_bus.emit(
                        event_type=EventType.TASK_SUBMITTED,
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=task.assignee_agent_id,
                        payload={"summary": args.get("summary", "")},
                    )
                    await event_bus.emit(
                        event_type=EventType.TASK_REVIEW_REQUESTED,
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=task.assignee_agent_id,
                        payload={"reviewer_id": task.reviewer_agent_id},
                    )

                    # Trigger formal review
                    await ReviewEngine.review_task(task.id)

                    # If approved, check if parent is ready for integration
                    if task.parent_id:
                        await IntegrationEngine.integrate_parent_task(task.parent_id)

                elif tool_name == "report_blocked":
                    async with async_session_factory() as session:
                        t = await session.get(Task, task.id)
                        t.status = TaskStatus.BLOCKED.value
                        await session.commit()

                    await event_bus.emit(
                        event_type=EventType.TASK_BLOCKED,
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=task.assignee_agent_id,
                        payload={"reason": args.get("reason", "Worker reported blocked")},
                    )

        except Exception as exc:
            logger.error(f"Error processing task {task_id}: {exc}", exc_info=True)
            async with async_session_factory() as session:
                t = await session.get(Task, task_id)
                if t:
                    t.attempt += 1
                    if t.attempt >= t.max_attempts:
                        t.status = TaskStatus.FAILED.value
                        t.error = str(exc)
                    else:
                        t.status = TaskStatus.ASSIGNED.value  # retry
                    await session.commit()
        finally:
            self._active_tasks.discard(task_id)
            self._scheduled_tasks.discard(task_id)

    async def _scheduler_loop(self) -> None:
        concurrency = self.settings.settings.global_concurrency

        while self.running:
            try:
                available_slots = concurrency - len(self._active_tasks) - len(self._scheduled_tasks)
                if available_slots > 0:
                    ready_tasks = await self._fetch_ready_tasks()
                    for task in ready_tasks:
                        if available_slots <= 0:
                            break
                        if task.id in self._scheduled_tasks or task.id in self._active_tasks:
                            continue
                        # Reserve synchronously before the coroutine gets a chance to run.
                        self._scheduled_tasks.add(task.id)
                        asyncio.create_task(self._process_task(task.id))
                        available_slots -= 1

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as loop_exc:
                logger.error(f"Error in scheduler loop: {loop_exc}")
                await asyncio.sleep(1.0)


# Singleton scheduler
scheduler = Scheduler()
