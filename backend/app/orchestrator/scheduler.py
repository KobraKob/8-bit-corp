import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy import or_, select, update

from app.agents.runtime import AgentRuntime
from app.core.config import get_app_settings
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import Agent, Task, TaskLog
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskFSM, TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.orchestrator.delegation import DelegationEngine
from app.orchestrator.integration import IntegrationEngine
from app.orchestrator.review import ReviewEngine
from app.orchestrator.triage import CEOTriage
from app.orchestrator.checkpoints import log_task, save_task_checkpoint


class Scheduler:
    """Async execution scheduler with crash-safety, depth-first queueing, and lifecycle management."""

    def __init__(self) -> None:
        self.settings = get_app_settings()
        self.running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._active_tasks: Set[str] = set()
        self._paused_projects: Set[str] = set()

    async def recover_stuck_tasks_on_startup(self) -> None:
        """Recover tasks whose durable worker lease expired before this process started."""
        await self._recover_expired_leases()

    async def _recover_expired_leases(self) -> None:
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            stmt = select(Task).where(
                Task.status.in_([
                    TaskStatus.IN_PROGRESS.value,
                    TaskStatus.INTEGRATING.value,
                    TaskStatus.REVIEWING.value,
                ])
            )
            rows = (await session.execute(stmt)).scalars().all()
            recovered = []
            for task in rows:
                expiry = task.lease_expires_at
                if expiry is not None and expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry is not None and expiry > now:
                    continue
                previous_status = task.status
                task.status = (
                    TaskStatus.IN_REVIEW.value
                    if previous_status == TaskStatus.REVIEWING.value
                    else TaskStatus.ASSIGNED.value
                )
                task.lease_token = None
                task.lease_expires_at = None
                checkpoint = dict(task.checkpoint_json or {})
                checkpoint["recovered_at"] = now.isoformat()
                checkpoint["recovered_from_status"] = previous_status
                task.checkpoint_json = checkpoint
                session.add(TaskLog(
                    id=generate_id("log"), task_id=task.id, level="warning",
                    event="task.lease_recovered",
                    message="Expired worker lease recovered from the last durable checkpoint.",
                    metadata_json={"previous_status": previous_status},
                ))
                recovered.append(task.id)
            if recovered:
                await session.commit()
                logger.warning(f"Recovered {len(recovered)} tasks with expired worker leases.")

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
        cancelled = []
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
                    cancelled.append((task.project_id, task.id, task.assignee_agent_id))

                # Find children
                child_stmt = select(Task.id).where(Task.parent_id == curr_id)
                res = await session.execute(child_stmt)
                children_ids = res.scalars().all()
                to_cancel.extend(children_ids)

            await session.commit()

        for project_id, cancelled_task_id, agent_id in cancelled:
            await event_bus.emit(
                event_type=EventType.TASK_CANCELLED,
                project_id=project_id,
                task_id=cancelled_task_id,
                agent_id=agent_id,
                payload={"reason": "Cancelled by user"},
            )

    async def _fetch_ready_tasks(self) -> List[Task]:
        """Fetch all tasks that are currently assigned and whose dependencies are completely done."""
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            stmt = select(Task).where(
                Task.status.in_([TaskStatus.ASSIGNED.value, TaskStatus.REVISION_REQUESTED.value, TaskStatus.IN_REVIEW.value]),
                or_(Task.next_retry_at.is_(None), Task.next_retry_at <= now),
            )
            queued_tasks = (await session.execute(stmt)).scalars().all()
            ready: List[Task] = []
            for task in queued_tasks:
                if task.project_id in self._paused_projects or task.id in self._active_tasks:
                    continue
                # Dependencies are stable task IDs only. Titles are not unique identifiers.
                dependencies = list(dict.fromkeys(task.depends_on_json or []))
                if not dependencies:
                    ready.append(task)
                    continue
                dep_stmt = select(Task.id, Task.status).where(
                    Task.id.in_(dependencies),
                    Task.project_id == task.project_id,
                )
                dep_rows = (await session.execute(dep_stmt)).all()
                dependency_statuses = {dependency_id: status for dependency_id, status in dep_rows}
                if len(dependency_statuses) == len(dependencies) and all(
                    dependency_statuses[dependency_id] == TaskStatus.DONE.value
                    for dependency_id in dependencies
                ):
                    ready.append(task)
            ready.sort(key=lambda task: (-task.depth, task.priority, task.created_at))
            return ready

    async def _claim_task(self, task_id: str):
        """Atomically claim one queued task and assign its renewable worker lease."""
        now = datetime.now(timezone.utc)
        lease_token = generate_id("lease")
        async with async_session_factory() as session:
            queued_status = await session.scalar(select(Task.status).where(Task.id == task_id))
            target_status = (
                TaskStatus.REVIEWING.value
                if queued_status == TaskStatus.IN_REVIEW.value
                else TaskStatus.IN_PROGRESS.value
            )
            claim = await session.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.status.in_([
                        TaskStatus.ASSIGNED.value,
                        TaskStatus.REVISION_REQUESTED.value,
                        TaskStatus.IN_REVIEW.value,
                    ]),
                )
                .values(
                    status=target_status,
                    started_at=now,
                    lease_token=lease_token,
                    lease_expires_at=now + timedelta(seconds=self.settings.settings.task_lease_seconds),
                    next_retry_at=None,
                )
            )
            if claim.rowcount != 1:
                await session.rollback()
                return None
            await session.commit()
            return queued_status, lease_token

    async def _process_task(self, task_id: str) -> None:
        self._active_tasks.add(task_id)
        try:
            claimed = await self._claim_task(task_id)
            if not claimed:
                return
            queued_status, lease_token = claimed
            async with async_session_factory() as session:
                task = await session.get(Task, task_id)
                if not task:
                    return
                proj_id = task.project_id
                t_id = task.id
                agt_id = task.assignee_agent_id
                t_title = task.title
                t_depth = task.depth

            await log_task(
                task_id, "task.claimed", "Worker atomically claimed task.",
                metadata={"lease_token": lease_token, "status": TaskStatus.REVIEWING.value if queued_status == TaskStatus.IN_REVIEW.value else TaskStatus.IN_PROGRESS.value},
            )
            await event_bus.emit(
                event_type=EventType.TASK_STARTED,
                project_id=proj_id,
                task_id=t_id,
                agent_id=agt_id,
                payload={"title": t_title, "depth": t_depth},
            )

            # A review interrupted by a process restart can be safely resumed.
            if queued_status == TaskStatus.IN_REVIEW.value:
                await save_task_checkpoint(
                    task.id, {"phase": "review_started"}, lease_token=lease_token,
                    event="task.review_started", message="Review resumed from the persisted task state.",
                )
                report = await ReviewEngine.review_task(task.id)
                await save_task_checkpoint(
                    task.id, {"phase": "review_completed", "review_decision": report.decision},
                    lease_token=lease_token, event="task.review_completed",
                    message="Review completed after recovery.",
                )
                if report.decision.lower().strip() == "approve" and task.parent_id:
                    await IntegrationEngine.integrate_parent_task(task.parent_id)
                return

            # CEO root: do not duplicate an already-created delegation tree after recovery.
            if task.depth == 0 and task.parent_id is None and queued_status == TaskStatus.ASSIGNED.value:
                async with async_session_factory() as session:
                    existing_child = await session.scalar(
                        select(Task.id).where(Task.parent_id == task.id).limit(1)
                    )
                    ceo = await session.get(Agent, task.assignee_agent_id) if task.assignee_agent_id else None
                if existing_child:
                    await IntegrationEngine.integrate_parent_task(task.id)
                    return
                checkpoint = dict(task.checkpoint_json or {})
                saved_plan = checkpoint.get("delegation_plan")
                if saved_plan and checkpoint.get("phase") in ("delegation_started", "delegation_completed"):
                    subtask_dicts = saved_plan
                    await log_task(
                        task.id, "task.delegation_resumed",
                        "Resuming the persisted delegation plan without another model call.",
                        metadata={"children": len(subtask_dicts)},
                    )
                else:
                    await save_task_checkpoint(
                        task.id, {"phase": "ceo_triage_started"}, lease_token=lease_token,
                        event="task.triage_started", message="CEO triage started.",
                    )
                    triage_plan = await CEOTriage.triage_project(task, ceo)
                    await save_task_checkpoint(
                        task.id, {"phase": "ceo_triage_completed"}, lease_token=lease_token,
                        event="task.triage_completed", message="CEO triage completed.",
                        metadata={"objectives": len(triage_plan.objectives)},
                    )
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
                await save_task_checkpoint(
                    task.id, {"phase": "delegation_started", "delegation_plan": subtask_dicts},
                    lease_token=lease_token, event="task.delegation_started",
                    message="Persisted delegation plan before creating child tasks.",
                    metadata={"children": len(subtask_dicts)},
                )
                await DelegationEngine.delegate_subtasks(
                    parent_task_id=task.id,
                    creator_agent_id=task.assignee_agent_id,
                    subtasks_data=subtask_dicts,
                )
                await save_task_checkpoint(
                    task.id, {"phase": "delegation_completed"}, lease_token=lease_token,
                    event="task.delegation_completed", message="Child tasks created.",
                    metadata={"children": len(subtask_dicts)},
                )
                return

            # Recovered manager tasks with existing children should resume integration,
            # not ask the LLM to delegate the same work packages again.
            if queued_status == TaskStatus.ASSIGNED.value:
                async with async_session_factory() as session:
                    existing_child = await session.scalar(
                        select(Task.id).where(Task.parent_id == task.id).limit(1)
                    )
                if existing_child:
                    await IntegrationEngine.integrate_parent_task(task.id)
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
                    task.assignee_agent_id = assignee_id

            # Case B: Standard worker agent execution turn
            runtime = AgentRuntime(task_id=task.id, agent_id=assignee_id, lease_token=lease_token)
            result = await runtime.run_turn()
            async with async_session_factory() as session:
                current_task = await session.get(Task, task.id)
                if not current_task or current_task.status == TaskStatus.CANCELLED.value:
                    return
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
                    await save_task_checkpoint(
                        task.id, {"phase": "review_started"}, lease_token=lease_token,
                        event="task.review_started", message="Formal deliverable review started.",
                    )
                    report = await ReviewEngine.review_task(task.id)
                    await save_task_checkpoint(
                        task.id, {"phase": "review_completed", "review_decision": report.decision},
                        lease_token=lease_token, event="task.review_completed",
                        message="Formal deliverable review completed.",
                    )
                    if report.decision.lower().strip() == "approve" and task.parent_id:
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
            await log_task(
                task_id, "task.execution_error", str(exc), level="error",
                metadata={"exception_type": type(exc).__name__},
            )
            async with async_session_factory() as session:
                t = await session.get(Task, task_id)
                if t and t.lease_token == locals().get("lease_token") and not TaskFSM.is_terminal(TaskStatus(t.status)):
                    if t.status == TaskStatus.REVIEWING.value:
                        t.status = TaskStatus.IN_REVIEW.value
                    else:
                        t.attempt += 1
                        t.error = str(exc)
                        if t.attempt >= t.max_attempts:
                            t.status = TaskStatus.FAILED.value
                            t.next_retry_at = None
                        else:
                            t.status = TaskStatus.ASSIGNED.value
                            delay = min(300, 5 * (2 ** max(0, t.attempt - 1)))
                            t.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    await session.commit()
        finally:
            async with async_session_factory() as session:
                current = await session.get(Task, task_id)
                if current and current.lease_token == locals().get("lease_token"):
                    current.lease_token = None
                    current.lease_expires_at = None
                    await session.commit()
            self._active_tasks.discard(task_id)

    async def _scheduler_loop(self) -> None:
        concurrency = self.settings.settings.global_concurrency

        while self.running:
            try:
                await self._recover_expired_leases()
                available_slots = concurrency - len(self._active_tasks)
                if available_slots > 0:
                    ready_tasks = await self._fetch_ready_tasks()
                    for task in ready_tasks[:available_slots]:
                        self._active_tasks.add(task.id)
                        asyncio.create_task(self._process_task(task.id))

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as loop_exc:
                logger.error(f"Error in scheduler loop: {loop_exc}")
                await asyncio.sleep(1.0)


# Singleton scheduler
scheduler = Scheduler()
