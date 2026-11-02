from typing import List, Optional
from sqlalchemy import select

from app.core.logging import logger
from app.db.models import Agent, Artifact, Project, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.workspace.workspace_manager import workspace_manager


class IntegrationEngine:
    """Bottom-up synthesis: synthesizes completed child tasks into a unified parent deliverable."""

    @staticmethod
    async def integrate_parent_task(parent_task_id: str) -> None:
        # Step 1: Read parent and child data
        async with async_session_factory() as session:
            parent = await session.get(Task, parent_task_id)
            if not parent:
                return

            children_stmt = select(Task).where(Task.parent_id == parent_task_id)
            res = await session.execute(children_stmt)
            children = res.scalars().all()

            if not children or not all(c.status == TaskStatus.DONE.value for c in children):
                return

            parent.status = TaskStatus.INTEGRATING.value
            await session.commit()

            parent_id = parent.id
            parent_title = parent.title
            parent_goal = parent.original_goal
            project_id = parent.project_id
            assignee_id = parent.assignee_agent_id
            is_root = parent.parent_id is None
            parent_desc = parent.description

            deliverable_summaries: List[str] = []
            for c in children:
                art_stmt = select(Artifact).where(Artifact.task_id == c.id)
                art_res = await session.execute(art_stmt)
                artifacts = art_res.scalars().all()
                art_text = ", ".join(f"{a.kind}:{a.path}" for a in artifacts)
                deliverable_summaries.append(
                    f"### Component: {c.title}\n- Assignee: {c.assignee_agent_id}\n- Artifacts: {art_text}\n- Description: {c.description}"
                )

        # Step 2: Synthesize and create artifact outside open session
        compiled_content = (
            f"# Consolidated Integration Deliverable: {parent_title}\n\n"
            f"**Original Goal:** {parent_goal}\n\n"
            f"## Integrated Child Deliverables\n\n"
            + "\n\n".join(deliverable_summaries)
            + "\n\n## Verification & Acceptance\nAll child objectives completed and verified by designated reviewers."
        )

        consolidated_artifact = await workspace_manager.create_artifact(
            project_id=project_id,
            task_id=parent_id,
            agent_id=assignee_id,
            kind="markdown",
            title=f"Integrated_{parent_title[:30]}",
            content=compiled_content,
        )

        # Step 3: Update parent and project status in DB
        async with async_session_factory() as session:
            p_rec = await session.get(Task, parent_id)
            if not p_rec:
                return
            p_rec.deliverable_artifact_id = consolidated_artifact.id

            if is_root:
                p_rec.status = TaskStatus.DONE.value
                proj = await session.get(Project, project_id)
                if proj:
                    proj.status = "completed"
            else:
                p_rec.status = TaskStatus.IN_REVIEW.value

            await session.commit()

        # Step 4: Emit events cleanly after DB commit
        if is_root:
            await event_bus.emit(
                event_type=EventType.TASK_DONE,
                project_id=project_id,
                task_id=parent_id,
                agent_id=assignee_id,
                payload={"deliverable_artifact_id": consolidated_artifact.id},
            )
            await event_bus.emit(
                event_type=EventType.PROJECT_COMPLETED,
                project_id=project_id,
                payload={
                    "project_id": project_id,
                    "root_deliverable_id": consolidated_artifact.id,
                    "summary": parent_desc,
                },
            )
            logger.info(f"Project {project_id} successfully COMPLETED by CEO integration!")
        else:
            await event_bus.emit(
                event_type=EventType.TASK_REVIEW_REQUESTED,
                project_id=project_id,
                task_id=parent_id,
                agent_id=assignee_id,
                payload={"deliverable_artifact_id": consolidated_artifact.id},
            )
