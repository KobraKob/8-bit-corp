from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.ids import generate_id
from app.db.models import Agent, Project, Task, TaskLog
from app.db.session import async_session_factory, init_db
from app.domain.task_fsm import TaskStatus
from app.llm.provider import (
    GroqProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderFactory,
    ProviderRequestError,
)
from app.orchestrator.checkpoints import load_task_checkpoint, save_task_checkpoint
from app.orchestrator.delegation import DelegationEngine
from app.orchestrator.scheduler import Scheduler


async def _make_project_and_task(status: str = TaskStatus.ASSIGNED.value):
    project_id = generate_id("proj")
    task_id = generate_id("tsk")
    async with async_session_factory() as session:
        session.add(Project(id=project_id, name="Runtime test", brief="Test brief"))
        session.add(Task(
            id=task_id, project_id=project_id, title="Runtime task",
            description="Exercise runtime resilience.", original_goal="Runtime resilience",
            status=status,
        ))
        await session.commit()
    return project_id, task_id


def test_provider_factory_selects_explicit_adapters():
    assert isinstance(ProviderFactory.create("groq", "groq", "https://example.test/v1", "key"), GroqProvider)
    assert isinstance(ProviderFactory.create("local", "ollama", "http://localhost:11434/v1", ""), OllamaProvider)
    assert isinstance(ProviderFactory.create("gateway", "openai_compatible", "https://example.test/v1", "key"), OpenAICompatibleProvider)
    with pytest.raises(ValueError, match="Unsupported adapter"):
        ProviderFactory.create("unknown", "not-a-provider", "https://example.test/v1", "key")


def test_provider_request_error_exposes_retry_metadata():
    error = ProviderRequestError("busy", status_code=429, retry_after=12.5, retryable=True)
    assert error.rate_limited is True
    assert error.retry_after == 12.5
    assert error.retryable is True


@pytest.mark.asyncio
async def test_checkpoint_persists_and_renews_task_lease():
    await init_db()
    _, task_id = await _make_project_and_task(TaskStatus.IN_PROGRESS.value)
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        task.lease_token = "lease-owner"
        task.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        await session.commit()

    saved = await save_task_checkpoint(
        task_id, {"phase": "tool_execution", "step": 2},
        lease_token="lease-owner", event="test.checkpoint", message="Persisted test checkpoint.",
    )
    assert saved is True
    checkpoint = await load_task_checkpoint(task_id)
    assert checkpoint["phase"] == "tool_execution"
    assert checkpoint["step"] == 2
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        expiry = task.lease_expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        assert expiry > datetime.now(timezone.utc)
        logs = (await session.execute(select(TaskLog).where(TaskLog.task_id == task_id))).scalars().all()
        assert any(log.event == "test.checkpoint" for log in logs)


@pytest.mark.asyncio
async def test_checkpoint_rejects_a_stale_worker_lease():
    await init_db()
    _, task_id = await _make_project_and_task(TaskStatus.IN_PROGRESS.value)
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        task.lease_token = "current-owner"
        await session.commit()
    with pytest.raises(RuntimeError, match="lease was lost"):
        await save_task_checkpoint(task_id, {"phase": "stale"}, lease_token="old-owner")


@pytest.mark.asyncio
async def test_atomic_task_claim_allows_only_one_worker():
    await init_db()
    _, task_id = await _make_project_and_task()
    scheduler = Scheduler()
    first = await scheduler._claim_task(task_id)
    second = await scheduler._claim_task(task_id)
    assert (first is None) != (second is None)
    claim = first or second
    assert claim is not None
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        assert task.status == TaskStatus.IN_PROGRESS.value
        assert task.lease_token == claim[1]
        assert task.lease_expires_at is not None


@pytest.mark.asyncio
async def test_expired_lease_recovers_without_discarding_checkpoint():
    await init_db()
    _, task_id = await _make_project_and_task(TaskStatus.IN_PROGRESS.value)
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        task.lease_token = "dead-worker"
        task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        task.checkpoint_json = {"phase": "after_tool_result"}
        await session.commit()

    await Scheduler().recover_stuck_tasks_on_startup()
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        assert task.status == TaskStatus.ASSIGNED.value
        assert task.lease_token is None
        assert task.checkpoint_json["phase"] == "after_tool_result"
        assert "recovered_at" in task.checkpoint_json


@pytest.mark.asyncio
async def test_delegation_is_idempotent_and_cannot_grow_a_task_tree_twice():
    await init_db()
    project_id = generate_id("proj")
    parent_id = generate_id("tsk")
    agent_id = generate_id("agt")
    async with async_session_factory() as session:
        session.add(Project(id=project_id, name="Delegation test", brief="Test brief"))
        session.add(Agent(
            id=agent_id, role_key="test_manager", display_name="Test Manager",
            department="Engineering", level=2, system_prompt="Test manager",
        ))
        session.add(Task(
            id=parent_id, project_id=project_id, title="Parent task",
            description="Parent", original_goal="Parent goal",
            status=TaskStatus.IN_PROGRESS.value, assignee_agent_id=agent_id,
        ))
        await session.commit()

    first = await DelegationEngine.delegate_subtasks(
        parent_id, agent_id,
        [{"title": "Child one", "description": "First child", "depends_on": []}],
    )
    second = await DelegationEngine.delegate_subtasks(
        parent_id, agent_id,
        [{"title": "Different child", "description": "Must not be created", "depends_on": []}],
    )
    assert [task.id for task in first] == [task.id for task in second]
    async with async_session_factory() as session:
        count = await session.scalar(select(Task.id).where(Task.parent_id == parent_id))
        assert count == first[0].id



@pytest.mark.asyncio
async def test_router_retries_transient_provider_failures(monkeypatch):
    from app.llm.router import LLMRouter
    from app.llm.types import ChatMessage, ChatResponse, UsageInfo

    class FlakyProvider:
        def __init__(self):
            self.calls = 0

        async def chat(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ProviderRequestError("temporary upstream outage", status_code=503, retryable=True)
            return ChatResponse(text="recovered", usage=UsageInfo(total_tokens=1))

    await init_db()
    provider = FlakyProvider()
    router = LLMRouter(override_provider=provider)
    router.settings.settings.llm_max_retries = 1
    router.settings.settings.llm_retry_base_seconds = 0.01
    response = await router.execute_chat(
        tier="fast",
        messages=[ChatMessage(role="user", content="Test retry")],
    )
    assert response.text == "recovered"
    assert provider.calls == 2
