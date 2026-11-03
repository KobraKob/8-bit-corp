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
from app.orchestrator.scheduler import scheduler


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



@pytest.mark.asyncio
async def test_scheduler_dependencies_require_stable_task_ids():
    await init_db()
    project_id = generate_id("proj")
    dependency_id = generate_id("tsk")
    title_reference_id = generate_id("tsk")
    id_reference_id = generate_id("tsk")

    async with async_session_factory() as session:
        session.add(Project(id=project_id, name="Dependency Test", brief="Test stable dependency IDs"))
        session.add(Task(
            id=dependency_id, project_id=project_id, depth=1, title="Completed upstream task",
            description="done", original_goal="done", status=TaskStatus.DONE.value,
        ))
        session.add(Task(
            id=title_reference_id, project_id=project_id, depth=1, title="Title-only dependency",
            description="must wait", original_goal="must wait", status=TaskStatus.ASSIGNED.value,
            depends_on_json=["Completed upstream task"],
        ))
        session.add(Task(
            id=id_reference_id, project_id=project_id, depth=1, title="ID dependency",
            description="ready", original_goal="ready", status=TaskStatus.ASSIGNED.value,
            depends_on_json=[dependency_id],
        ))
        await session.commit()

    ready_ids = {task.id for task in await scheduler._fetch_ready_tasks()}
    assert id_reference_id in ready_ids
    assert title_reference_id not in ready_ids


@pytest.mark.asyncio
async def test_recovered_root_does_not_duplicate_delegated_children():
    await init_db()
    project_id = generate_id("proj")
    root_id = generate_id("tsk")
    child_id = generate_id("tsk")
    async with async_session_factory() as session:
        session.add(Project(id=project_id, name="Recovery Test", brief="Resume safely"))
        session.add(Task(
            id=root_id, project_id=project_id, depth=0, title="Root",
            description="root", original_goal="root", status=TaskStatus.IN_PROGRESS.value,
        ))
        session.add(Task(
            id=child_id, project_id=project_id, parent_id=root_id, depth=1, title="Existing child",
            description="child", original_goal="root", status=TaskStatus.ASSIGNED.value,
        ))
        await session.commit()

    await scheduler.recover_stuck_tasks_on_startup()
    await scheduler._process_task(root_id)

    async with async_session_factory() as session:
        children = (await session.execute(select(Task).where(Task.parent_id == root_id))).scalars().all()
        root = await session.get(Task, root_id)
        assert len(children) == 1
        assert root.status == TaskStatus.IN_PROGRESS.value
