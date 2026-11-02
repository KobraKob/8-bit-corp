import pytest
from pathlib import Path

from app.core.errors import SecurityViolationError
from app.core.ids import generate_id
from app.db.models import Agent, Project, Task
from app.db.session import async_session_factory, init_db
from app.tools.sandbox import SubprocessSandbox
from app.tools.web_guard import validate_url_safe
from app.tools.registry import ToolExecutor
from app.agents.runtime import AgentRuntime
from app.llm.provider import MockProvider
from app.llm.router import llm_router


def test_ssrf_guard_blocks_private_addresses():
    bad_urls = [
        "http://localhost:8080/admin",
        "http://127.0.0.1/secrets",
        "http://192.168.1.100/router",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
    ]
    for url in bad_urls:
        with pytest.raises(SecurityViolationError):
            validate_url_safe(url)


def test_sandbox_execution(tmp_path: Path):
    sb = SubprocessSandbox(timeout_sec=5.0)

    # Valid Python execution
    code = "import os; print('SECRET_CHECK:', os.getenv('GROQ_API_KEY'))"
    ret, out, err = sb.execute("python", code, tmp_path)
    assert ret == 0
    # Confirm env is scrubbed of secrets
    assert "SECRET_CHECK: None" in out

    # Disallowed language
    ret_bad, _, err_bad = sb.execute("bash", "echo 1", tmp_path)
    assert ret_bad != 0
    assert "Disallowed language" in err_bad

    # Timeout
    timeout_code = "import time; time.sleep(10)"
    sb_short = SubprocessSandbox(timeout_sec=0.5)
    ret_to, _, err_to = sb_short.execute("python", timeout_code, tmp_path)
    assert ret_to == -1
    assert "timed out" in err_to


@pytest.mark.asyncio
async def test_agent_runtime_turn():
    await init_db()

    project_id = generate_id("proj")
    task_id = generate_id("tsk")
    agent_id = generate_id("agt")

    async with async_session_factory() as session:
        proj = Project(id=project_id, name="Test Project", brief="Build landing page")
        agent = Agent(
            id=agent_id,
            role_key="dev_frontend",
            display_name="Frontend Dev",
            department="Engineering",
            level=5,
            model_tier="fast",
            system_prompt="You build frontend code.",
            tools_json=["create_artifact", "submit_deliverable", "write_file", "read_file"],
        )
        task = Task(
            id=task_id,
            project_id=project_id,
            depth=1,
            title="Create HTML component",
            description="Build HTML landing page",
            original_goal="Build landing page",
            acceptance_criteria_json=["Valid HTML output"],
            assignee_agent_id=agent_id,
            status="in_progress",
        )
        session.add(proj)
        session.add(agent)
        session.add(task)
        await session.commit()

    # Use MockProvider for deterministic test
    mock_provider = MockProvider()
    llm_router.override_provider = mock_provider

    runtime = AgentRuntime(task_id=task_id, agent_id=agent_id)
    result = await runtime.run_turn()

    assert result["terminal_action"] is not None
    assert result["terminal_action"]["tool"] in ("submit_deliverable", "create_artifact")
    assert result["tokens_used"] > 0
