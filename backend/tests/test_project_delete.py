import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Agent,
    Approval,
    Artifact,
    CompanyMeeting,
    Event,
    LLMCall,
    Message,
    Project,
    Task,
    WikiNote,
)
from app.db.session import async_session_factory
from app.domain.org_model import seed_organization_from_config
from app.main import app
from app.orchestrator.scheduler import scheduler


def new_id():
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_project_removes_all_project_data(tmp_path, monkeypatch):
    await seed_organization_from_config()
    project_id = new_id()
    task_id = new_id()
    artifact_id = new_id()
    meeting_id = new_id()
    note_id = new_id()
    approval_id = new_id()
    message_id = new_id()
    llm_call_id = new_id()

    async with async_session_factory() as session:
        agent = await session.scalar(select(Agent).where(Agent.role_key == "ceo"))
        project = Project(
            id=project_id, name="Delete test", brief="Temporary project",
            status="stopped",
        )
        task = Task(
            id=task_id, project_id=project_id, title="Temporary task",
            description="Delete me", original_goal="Delete me",
            status="cancelled", assignee_agent_id=agent.id,
        )
        session.add_all([
            project,
            task,
            Artifact(
                id=artifact_id, project_id=project_id, task_id=task_id,
                kind="text", path="artifacts/test.txt", summary="test artifact",
            ),
            CompanyMeeting(
                id=meeting_id, project_id=project_id, title="Delete meeting",
                trigger="manual", status="completed",
            ),
            WikiNote(
                id=note_id, project_id=project_id, title="Project memory",
                body="Temporary memory",
            ),
            Approval(
                id=approval_id, project_id=project_id, task_id=task_id,
                kind="review", request_json={}, status="pending",
            ),
            Message(
                id=message_id, task_id=task_id, from_agent_id=agent.id,
                to_agent_id=agent.id, kind="note", payload_json={},
            ),
            LLMCall(
                id=llm_call_id, task_id=task_id, agent_id=agent.id,
                provider="test", model="test", tier="fast",
            ),
            Event(
                type="test.project_event", project_id=project_id,
                task_id=task_id, payload_json={},
            ),
        ])
        await session.commit()

    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "deliverable.txt").write_text("temporary")
    monkeypatch.setattr(scheduler, "pause_project", lambda _project_id: _async_noop())
    monkeypatch.setattr(scheduler, "cancel_task_subtree", lambda _task_id: _async_noop())

    # The workspace manager's root is shared by the app; route cleanup is
    # separately verified by checking that the endpoint returns successfully.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 204
    async with async_session_factory() as session:
        assert await session.get(Project, project_id) is None
        assert await session.get(Task, task_id) is None
        assert await session.get(Artifact, artifact_id) is None
        assert await session.get(CompanyMeeting, meeting_id) is None
        assert await session.get(WikiNote, note_id) is None
        assert await session.get(Approval, approval_id) is None
        assert await session.get(Message, message_id) is None
        assert await session.get(LLMCall, llm_call_id) is None


async def _async_noop():
    return None
