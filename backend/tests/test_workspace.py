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
