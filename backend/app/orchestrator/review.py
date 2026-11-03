from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_app_settings
from app.core.logging import logger
from app.db.models import Agent, Artifact, Project, Task
from app.db.session import async_session_factory
from app.domain.task_fsm import TaskStatus
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.llm.router import llm_router
from app.llm.types import ChatMessage
from app.workspace.workspace_manager import workspace_manager
from app.orchestrator.company_memory import save_memory
from app.orchestrator.meeting_service import convene_project_meeting


class CriterionEvaluation(BaseModel):
    criterion: str = Field(description="The exact acceptance criterion evaluated")
    passed: bool = Field(description="Whether this criterion passed")
    notes: str = Field(description="Observations and justification")


class ReviewReport(BaseModel):
    decision: str = Field(description="Review outcome: approve | revise | escalate")
    summary: str = Field(description="Concise synthesis of deliverable quality")
    criteria_evaluations: List[CriterionEvaluation] = Field(
        default_factory=list,
        description="Individual evaluation for each acceptance criterion",
    )
    required_revisions: List[str] = Field(
        default_factory=list,
        description="Specific action items if revision requested",
    )


class ReviewEngine:
    """Conducts rigorous reviews citing acceptance criteria, manages revision loops, and handles escalations."""

    @staticmethod
    async def review_task(task_id: str) -> ReviewReport:
        settings = get_app_settings()

        async with async_session_factory() as session:
            task = await session.get(Task, task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            task.status = TaskStatus.REVIEWING.value
            await session.commit()

            # Determine reviewer agent
            reviewer_id = task.reviewer_agent_id
            reviewer = await session.get(Agent, reviewer_id) if reviewer_id else None
            if not reviewer and task.creator_agent_id:
                reviewer = await session.get(Agent, task.creator_agent_id)
            if not reviewer:
                # Fallback to CEO
                ceo_stmt = select(Agent).where(Agent.role_key == "ceo")
                reviewer = (await session.execute(ceo_stmt)).scalar_one_or_none()
            if not reviewer:
                # Ultimate fallback to any active agent
                any_stmt = select(Agent).where(Agent.status == "active")
                reviewer = (await session.execute(any_stmt)).scalars().first()

            # Deliverable artifact content
            deliverable_content = "No artifact attached."
            if task.deliverable_artifact_id:
                art = await session.get(Artifact, task.deliverable_artifact_id)
                if art:
                    try:
                        artifact_content = workspace_manager.read_file(task.project_id, art.path)
                    except Exception:
                        artifact_content = art.summary or "Artifact file unavailable."
                    content_excerpt = artifact_content[:20000]
                    deliverable_content = (
                        f"Artifact: {art.path}\n"
                        f"Summary: {art.summary}\n"
                        f"Content:\n{content_excerpt}"
                    )

            assignee = await session.get(Agent, task.assignee_agent_id) if task.assignee_agent_id else None
            assignee_name = assignee.display_name if assignee else "Worker Agent"

        criteria_list = "\n".join(f"- {c}" for c in task.acceptance_criteria_json)

        prompt = (
            f"You are {reviewer.display_name} ({reviewer.department}). "
            f"Review the submitted deliverable for task '{task.title}' produced by {assignee_name}.\n\n"
            f"Original Goal: {task.original_goal}\n"
            f"Task Description: {task.description}\n"
            f"Acceptance Criteria:\n{criteria_list}\n\n"
            f"Submitted Deliverable Details:\n{deliverable_content}\n\n"
            f"Current revision count: {task.attempt}/{settings.settings.max_revisions}\n\n"
            f"Evaluate every acceptance criterion rigorously in 'criteria_evaluations'.\n"
            f"If all criteria pass, set decision to 'approve'.\n"
            f"If any criteria fail and revisions remain, set decision to 'revise' and specify 'required_revisions'.\n"
            f"If max revisions exceeded or fundamentally blocked, set decision to 'escalate'."
        )

        report = await llm_router.execute_structured(
            tier=reviewer.model_tier,
            messages=[
                ChatMessage(role="system", content=reviewer.system_prompt),
                ChatMessage(role="user", content=prompt),
            ],
            schema_cls=ReviewReport,
            task_id=task.id,
            agent_id=reviewer.id,
        )

        # Apply review decision
        decision = report.decision.lower().strip()
        events_to_emit = []

        async with async_session_factory() as session:
            t = await session.get(Task, task_id)
            if not t:
                return report

            if decision == "approve":
                t.status = TaskStatus.DONE.value
                t.completed_at = datetime.now(timezone.utc)
                if t.parent_id is None:
                    project = await session.get(Project, t.project_id)
                    if project:
                        project.status = "completed"
                    events_to_emit.append((
                        EventType.PROJECT_COMPLETED, t.project_id, None, reviewer.id,
                        {"project_id": t.project_id, "root_deliverable_id": t.deliverable_artifact_id},
                    ))
                events_to_emit.append((
                    EventType.TASK_APPROVED,
                    t.project_id,
                    t.id,
                    reviewer.id,
                    {"notes": report.summary},
                ))
                events_to_emit.append((
                    EventType.TASK_DONE,
                    t.project_id,
                    t.id,
                    t.assignee_agent_id,
                    {"deliverable_artifact_id": t.deliverable_artifact_id},
                ))

            elif decision == "revise":
                t.attempt += 1
                if t.attempt > settings.settings.max_revisions:
                    logger.warning(f"Task {t.id} exceeded max revisions ({t.attempt}). Escalating.")
                    t.status = TaskStatus.BLOCKED.value
                    events_to_emit.append((
                        EventType.TASK_BLOCKED,
                        t.project_id,
                        t.id,
                        reviewer.id,
                        {"reason": "Max revision attempts reached; escalated to leadership."},
                    ))
                else:
                    t.status = TaskStatus.REVISION_REQUESTED.value
                    t.review_notes_json = list(t.review_notes_json or []) + report.required_revisions
                    events_to_emit.append((
                        EventType.TASK_REVISION_REQUESTED,
                        t.project_id,
                        t.id,
                        reviewer.id,
                        {"revision_notes": report.required_revisions, "attempt": t.attempt},
                    ))
                    # Scheduler resumes this explicit revision state.

            elif decision == "escalate":
                t.status = TaskStatus.BLOCKED.value
                events_to_emit.append((
                    EventType.TASK_BLOCKED,
                    t.project_id,
                    t.id,
                    reviewer.id,
                    {"reason": f"Escalated by reviewer: {report.summary}"},
                ))

            else:
                t.status = TaskStatus.BLOCKED.value
                events_to_emit.append((
                    EventType.TASK_BLOCKED, t.project_id, t.id, reviewer.id,
                    {"reason": f"Unsupported review decision: {report.decision}"},
                ))

            await session.commit()

        # Persist formal review outcomes as project memory so later tasks
        # can reuse client decisions, quality expectations and revision lessons.
        if decision in ("approve", "revise", "escalate"):
            evaluations = "\\n".join(
                f"- {item.criterion}: {'PASS' if item.passed else 'FAIL'} — {item.notes}"
                for item in report.criteria_evaluations
            )
            revision_text = "\\n".join(f"- {item}" for item in report.required_revisions)
            await save_memory(
                title=f"Review decision — {task.title}",
                body=(
                    f"Decision: {decision}\\nSummary: {report.summary}\\n"
                    f"Acceptance review:\\n{evaluations}\\n"
                    f"Required revisions:\\n{revision_text}"
                ),
                tags="review-decision, acceptance-criteria, quality-history",
                project_id=task.project_id,
                created_by_agent_id=reviewer.id,
            )

        # Emit events after session is committed to prevent SQLite lockups
        for evt_type, proj_id, t_id, agt_id, payload in events_to_emit:
            await event_bus.emit(
                event_type=evt_type,
                project_id=proj_id,
                task_id=t_id,
                agent_id=agt_id,
                payload=payload,
            )

        # A blocked/escalated review requires manager coordination.
        if decision in ("escalate",) or any(evt[0] == EventType.TASK_BLOCKED for evt in events_to_emit):
            try:
                await convene_project_meeting(
                    task.project_id,
                    reason="automatic",
                    trigger_task_id=task.id,
                )
            except Exception as meeting_exc:
                logger.warning(f"Could not convene review escalation meeting: {meeting_exc}")

        return report
