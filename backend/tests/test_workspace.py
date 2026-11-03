import pytest
from pathlib import Path
from app.core.errors import SecurityViolationError
from app.workspace.workspace_manager import WorkspaceManager


def test_workspace_safe_write_and_read(tmp_path: Path):
    ws = WorkspaceManager(root_path=tmp_path)
    project_id = "test_project_1"

    rel_written = ws.write_file(project_id, "src/index.html", "<h1>Hello Pixel Corp</h1>")
    assert "src/index.html" in rel_written or "src\\index.html" in rel_written

    content = ws.read_file(project_id, "src/index.html")
    assert content == "<h1>Hello Pixel Corp</h1>"

    files = ws.list_files(project_id)
    assert len(files) == 1


def test_workspace_path_traversal_prevention(tmp_path: Path):
    ws = WorkspaceManager(root_path=tmp_path)
    project_id = "test_project_2"

    traversal_paths = [
        "../outside.txt",
        "../../etc/passwd",
        "..\\..\\windows\\system32\\calc.exe",
        "src/../../outside.txt",
        "/outside.txt",
    ]

    for bad_path in traversal_paths:
        with pytest.raises(SecurityViolationError):
            ws.resolve_safe_path(project_id, bad_path)

        with pytest.raises(SecurityViolationError):
            ws.write_file(project_id, bad_path, "malicious")


def test_each_agent_gets_a_private_directory_inside_its_project(tmp_path: Path):
    ws = WorkspaceManager(root_path=tmp_path)
    project_id = "project_alpha"

    first_dir = ws.get_agent_dir(project_id, "agent_one")
    second_dir = ws.get_agent_dir(project_id, "agent_two")
    other_project_dir = ws.get_agent_dir("project_beta", "agent_one")

    assert first_dir != second_dir
    assert first_dir != other_project_dir
    assert first_dir.parent == second_dir.parent
    assert first_dir.parent.parent != other_project_dir.parent.parent

    ws.write_agent_file(project_id, "agent_one", "drafts/plan.md", "Private plan")
    assert ws.read_agent_file(project_id, "agent_one", "drafts/plan.md") == "Private plan"
    assert ws.list_agent_files(project_id, "agent_one") == ["drafts/plan.md"]
    with pytest.raises(FileNotFoundError):
        ws.read_agent_file(project_id, "agent_two", "drafts/plan.md")


def test_agents_can_explicitly_share_project_files(tmp_path: Path):
    ws = WorkspaceManager(root_path=tmp_path)
    project_id = "project_shared"

    written = ws.write_agent_file(project_id, "agent_one", "shared/research.md", "Shared research")
    assert written == "shared/research.md"
    assert ws.read_agent_file(project_id, "agent_two", "shared/research.md") == "Shared research"
    assert ws.list_agent_files(project_id, "agent_two", "shared") == ["shared/research.md"]


def test_agent_workspace_rejects_path_traversal(tmp_path: Path):
    ws = WorkspaceManager(root_path=tmp_path)
    with pytest.raises(SecurityViolationError):
        ws.write_agent_file("project_safe", "agent_safe", "../outside.txt", "blocked")
    with pytest.raises(SecurityViolationError):
        ws.read_agent_file("project_safe", "agent_safe", "shared/../../outside.txt")
    with pytest.raises(SecurityViolationError):
        ws.write_agent_file("project_safe", "agent_safe", "C:/outside.txt", "blocked")
    with pytest.raises(SecurityViolationError):
        ws.write_agent_file("project_safe", "agent_safe", "/outside.txt", "blocked")
