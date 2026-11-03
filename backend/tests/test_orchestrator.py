import asyncio
import pytest
from sqlalchemy import select

from app.core.ids import generate_id
from app.db.models import Agent, Project, Task
from app.db.session import async_session_factory, init_db
from app.domain.org_model import seed_organization_from_config
from app.domain.task_fsm import TaskStatus
from app.llm.provider import MockProvider
from app.llm.router import llm_router
from app.orchestrator.scheduler import dependencies_are_complete, scheduler


@pytest.mark.asyncio
async def test_crash_recovery_on_startup():
    await init_db()
    proj_id = generate_id("proj")
    task_id = generate_id("tsk")
    async with async_session_factory() as session:
        proj = Project(id=proj_id, name="Crash Test", brief="Test crash")
        t = Task(
            id=task_id,
            project_id=proj_id,
            depth=1,
            title="In flight task",
            description="desc",
            original_goal="goal",
            status="in_progress",
        )
        session.add(proj)
        session.add(t)
        await session.commit()

    # Run recovery
    await scheduler.recover_stuck_tasks_on_startup()

    async with async_session_factory() as session:
        recovered = await session.get(Task, task_id)
        assert recovered.status == TaskStatus.ASSIGNED.value


@pytest.mark.asyncio
async def test_golden_path_orchestration():
    await init_db()
    await seed_organization_from_config()

    # Use deterministic MockProvider
    mock_prov = MockProvider()
    llm_router.override_provider = mock_prov

    project_id = generate_id("proj")
    root_task_id = generate_id("tsk")

    async with async_session_factory() as session:
        # Find CEO
        ceo_stmt = select(Agent).where(Agent.role_key == "ceo")
        res = await session.execute(ceo_stmt)
        ceo = res.scalar_one()

        proj = Project(
            id=project_id,
            name="Golden Path Landing Page",
            brief="Design and build a responsive retro landing page with SVG logo.",
        )
        root_task = Task(
            id=root_task_id,
            project_id=project_id,
            depth=0,
            title="Build Retro Landing Page",
            description="Design and build a responsive retro landing page with SVG logo.",
            original_goal="Design and build a responsive retro landing page with SVG logo.",
            acceptance_criteria_json=["Design spec ready", "HTML components built"],
            assignee_agent_id=ceo.id,
            status=TaskStatus.ASSIGNED.value,
        )
        session.add(proj)
        session.add(root_task)
        await session.commit()

    # Start scheduler
    await scheduler.start()

    # Wait for orchestration cascade to complete
    max_wait = 15.0
    elapsed = 0.0
    completed = False

    while elapsed < max_wait:
        await asyncio.sleep(0.5)
        elapsed += 0.5
        async with async_session_factory() as session:
            p = await session.get(Project, project_id)
            if p and p.status == "completed":
                completed = True
                break

    await scheduler.stop()

    assert completed is True, "Project did not complete within timeout"

    # Verify children tasks were created and completed
    async with async_session_factory() as session:
        stmt = select(Task).where(Task.project_id == project_id)
        tasks = (await session.execute(stmt)).scalars().all()
        assert len(tasks) >= 3  # Root CEO + 2 subtasks
        assert all(t.status == TaskStatus.DONE.value for t in tasks)



def test_dependency_readiness_uses_only_stable_task_ids():
    assert dependencies_are_complete([], {})
    assert dependencies_are_complete(["task-a", "task-b"], {
        "task-a": TaskStatus.DONE.value,
        "task-b": TaskStatus.DONE.value,
    })
    assert not dependencies_are_complete(["task-a", "missing"], {
        "task-a": TaskStatus.DONE.value,
    })
    assert not dependencies_are_complete(["task-a"], {
        "task-a": TaskStatus.IN_PROGRESS.value,
    })
    # Repeated references do not make a completed dependency appear unresolved.
    assert dependencies_are_complete(["task-a", "task-a"], {
        "task-a": TaskStatus.DONE.value,
    })
