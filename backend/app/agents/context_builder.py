from typing import List, Optional
from sqlalchemy import select

from app.core.config import get_app_settings
from app.db.models import Agent, Artifact, Task, WikiNote
from app.db.session import async_session_factory
from app.llm.types import ChatMessage
from app.tools.registry import TOOL_DEFINITIONS


class ContextBuilder:
    """Builds a rich, structured task packet preventing information loss across hierarchy levels."""

    def __init__(self, task: Task, agent: Agent) -> None:
        self.task = task
        self.agent = agent
        self.settings = get_app_settings()

    async def build_messages(self, is_wrap_up: bool = False) -> List[ChatMessage]:
        charter = self.settings.org.company_charter

        # 1. System Prompt
        system_content = (
            f"=== COMPANY CHARTER ===\n{charter}\n\n"
            f"=== YOUR ROLE: {self.agent.display_name} ({self.agent.department}, Level {self.agent.level}) ===\n"
            f"{self.agent.system_prompt}\n\n"
            f"Guidelines:\n"
            f"- Output concrete deliverables using tools.\n"
            f"- Call submit_deliverable when your work satisfies all acceptance criteria.\n"
            f"- If you need to break this down for subordinates, call delegate.\n"
            f"- If blocked, call report_blocked.\n"
        )
        messages: List[ChatMessage] = [ChatMessage(role="system", content=system_content)]

        # 2. Ancestor Context & Dependencies
        async with async_session_factory() as session:
            # Build ancestor chain
            ancestor_lines: List[str] = []
            curr_parent_id = self.task.parent_id
            while curr_parent_id:
                stmt = select(Task).where(Task.id == curr_parent_id)
                res = await session.execute(stmt)
                parent = res.scalar_one_or_none()
                if not parent:
                    break
                ancestor_lines.append(f"- Level {parent.depth}: {parent.title} -> {parent.description[:120]}")
                curr_parent_id = parent.parent_id

            # Dependency outputs
            dep_lines: List[str] = []
            for dep_id_or_title in self.task.depends_on_json:
                stmt = select(Task).where(
                    (Task.id == dep_id_or_title) | (Task.title == dep_id_or_title),
                    Task.project_id == self.task.project_id,
                )
                res = await session.execute(stmt)
                dep_task = res.scalar_one_or_none()
                if dep_task and dep_task.deliverable_artifact_id:
                    art_stmt = select(Artifact).where(Artifact.id == dep_task.deliverable_artifact_id)
                    art_res = await session.execute(art_stmt)
                    art = art_res.scalar_one_or_none()
                    art_info = f" (Artifact: {art.path} - Summary: {art.summary})" if art else ""
                    dep_lines.append(f"- {dep_task.title}: Completed.{art_info}")
                elif dep_task:
                    dep_lines.append(f"- {dep_task.title}: Status {dep_task.status}")

            # Wiki notes
            wiki_stmt = select(WikiNote).where(
                (WikiNote.project_id == self.task.project_id) | (WikiNote.project_id.is_(None))
            )
            w_res = await session.execute(wiki_stmt)
            wiki_notes = w_res.scalars().all()
            wiki_lines = [f"- {w.title}: {w.body[:150]}" for w in wiki_notes[:3]]

        # 3. Assemble User Task Prompt
        criteria_list = "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(self.task.acceptance_criteria_json))
        ancestor_block = "\n".join(reversed(ancestor_lines)) if ancestor_lines else "None (Root Task)"
        dep_block = "\n".join(dep_lines) if dep_lines else "None"
        wiki_block = "\n".join(wiki_lines) if wiki_lines else "None"

        review_notes_block = ""
        if self.task.review_notes_json:
            review_notes_block = "\n=== PREVIOUS REVISION FEEDBACK (MUST ADDRESS) ===\n" + "\n".join(
                f"- {note}" for note in self.task.review_notes_json
            )

        task_prompt = (
            f"=== ORIGINAL USER GOAL ===\n{self.task.original_goal}\n\n"
            f"=== CURRENT TASK (Depth: {self.task.depth}, Attempt: {self.task.attempt + 1}/{self.task.max_attempts}) ===\n"
            f"Title: {self.task.title}\n"
            f"Description: {self.task.description}\n"
            f"Acceptance Criteria:\n{criteria_list}\n\n"
            f"=== ANCESTOR OBJECTIVES ===\n{ancestor_block}\n\n"
            f"=== DEPENDENCY DELIVERABLES ===\n{dep_block}\n\n"
            f"=== SHARED KNOWLEDGE (WIKI) ===\n{wiki_block}"
            f"{review_notes_block}\n\n"
            f"Execute your role and produce concrete deliverables."
        )

        if is_wrap_up:
            task_prompt += "\n\nCRITICAL NOTICE: Step/Budget cap reached! Submit your best-effort deliverable now."

        messages.append(ChatMessage(role="user", content=task_prompt))
        return messages

    def get_allowed_tool_specs(self) -> List[dict]:
        allowed = self.agent.tools_json or []
        specs = []
        for name in allowed:
            if name in TOOL_DEFINITIONS:
                specs.append(TOOL_DEFINITIONS[name])
        return specs
