from sqlalchemy import select, update

from app.core.logging import logger
from app.db.models import Artifact, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.workspace.workspace_manager import workspace_manager


class IntegrationEngine:
    """Integrate reviewed child work, review the parent, then recurse toward the CEO."""

    @staticmethod
    async def integrate_parent_task(parent_task_id: str) -> None:
        async with async_session_factory() as session:
            parent = await session.get(Task, parent_task_id)
            if not parent or parent.status in (TaskStatus.INTEGRATING.value, TaskStatus.IN_REVIEW.value, TaskStatus.REVIEWING.value, TaskStatus.REVISION_REQUESTED.value, TaskStatus.DONE.value, TaskStatus.BLOCKED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
                return
            children = (await session.execute(
                select(Task).where(Task.parent_id == parent_task_id)
            )).scalars().all()
            if not children or not all(child.status == TaskStatus.DONE.value for child in children):
                return

            claim = await session.execute(
                update(Task)
                .where(
                    Task.id == parent_task_id,
                    Task.status.not_in([TaskStatus.INTEGRATING.value, TaskStatus.IN_REVIEW.value, TaskStatus.REVIEWING.value, TaskStatus.REVISION_REQUESTED.value, TaskStatus.DONE.value, TaskStatus.BLOCKED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]),
                )
                .values(status=TaskStatus.INTEGRATING.value)
            )
            if claim.rowcount != 1:
                return
            await session.commit()

            parent = await session.get(Task, parent_task_id)
            if not parent:
                return
            parent_id = parent.id
            parent_title = parent.title
            parent_goal = parent.original_goal
            project_id = parent.project_id
            assignee_id = parent.assignee_agent_id
            parent_parent_id = parent.parent_id
            child_ids = [child.id for child in children]
            summaries = []
            for child in children:
                artifacts = (await session.execute(
                    select(Artifact).where(Artifact.task_id == child.id)
                )).scalars().all()
                artifact_sections = []
                for artifact in artifacts:
                    section = f"#### {artifact.path.rsplit('/', 1)[-1]}\n- Type: {artifact.kind}\n- File: {artifact.path}\n- Summary: {artifact.summary}"
                    if artifact.kind in ("markdown", "text", "code"):
                        try:
                            artifact_content = workspace_manager.read_file(project_id, artifact.path)
                        except Exception:
                            artifact_content = artifact.summary or ""
                        excerpt = artifact_content[:12000]
                        section += f"\n\n{excerpt}"
                        if len(artifact_content) > 12000:
                            section += "\n\n[Content excerpt truncated at 12,000 characters.]"
                    artifact_sections.append(section)
                artifact_lines = "\n\n".join(artifact_sections) or "- No file artifact attached; see completed task notes."
                summaries.append(
                    f"### {child.title}\n- Assignee: {child.assignee_agent_id or 'Unassigned'}"
                    f"\n- Description: {child.description}\n{artifact_lines}"
                )

        content = (
            f"# Integrated deliverable: {parent_title}\n\n"
            f"**Original goal:** {parent_goal}\n\n"
            "## Reviewed work packages\n\n" + "\n\n".join(summaries) +
            "\n\n## Completion status\nEvery child work package passed its designated review. "
            "This integrated document is submitted for parent-level review."
        )

        try:
            artifact = await workspace_manager.create_artifact(
                project_id=project_id, task_id=parent_id, agent_id=assignee_id,
                kind="markdown", title=f"Integrated_{parent_title[:30]}", content=content,
            )
            async with async_session_factory() as session:
                parent = await session.get(Task, parent_id)
                if not parent or parent.status == TaskStatus.CANCELLED.value:
                    return
                parent.deliverable_artifact_id = artifact.id
                parent.status = TaskStatus.IN_REVIEW.value
                await session.commit()

            await event_bus.emit(
                event_type=EventType.TASK_REVIEW_REQUESTED,
                project_id=project_id, task_id=parent_id, agent_id=assignee_id,
                payload={"deliverable_artifact_id": artifact.id, "integrated_children": child_ids},
            )

            from app.orchestrator.review import ReviewEngine
            report = await ReviewEngine.review_task(parent_id)
            if report.decision.lower().strip() != "approve":
                return
            if parent_parent_id:
                await IntegrationEngine.integrate_parent_task(parent_parent_id)
            else:
                logger.info("Root project integration approved for %s", project_id)
        except Exception:
            async with async_session_factory() as session:
                parent = await session.get(Task, parent_id)
                if parent and parent.status == TaskStatus.INTEGRATING.value:
                    parent.status = TaskStatus.ASSIGNED.value
                    await session.commit()
                elif parent and parent.status in (TaskStatus.IN_REVIEW.value, TaskStatus.REVIEWING.value):
                    parent.status = TaskStatus.IN_REVIEW.value
                    await session.commit()
            raise
