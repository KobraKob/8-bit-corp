import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core.config import get_app_settings
from app.core.errors import SecurityViolationError
from app.core.ids import generate_id
from app.db.models import Artifact
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType


class WorkspaceManager:
    """Manages isolated per-project file workspaces with strict path-traversal guards."""

    def __init__(self, root_path: Optional[Path] = None) -> None:
        self.root_path = root_path or get_app_settings().workspaces_root
        self.root_path.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: str) -> Path:
        """Get or create the root directory for a project workspace."""
        safe_id = "".join(c for c in project_id if c.isalnum() or c in ("-", "_"))
        proj_dir = (self.root_path / safe_id).resolve()
        proj_dir.mkdir(parents=True, exist_ok=True)
        return proj_dir

    def resolve_safe_path(self, project_id: str, relative_path: str) -> Path:
        """Resolve a relative path inside project directory, blocking directory traversal and absolute escapes."""
        proj_dir = self.get_project_dir(project_id)
        
        # Check for disallowed absolute path attempts or malicious escapes
        p = Path(relative_path)
        if p.is_absolute() or relative_path.startswith("/") or relative_path.startswith("\\"):
            raise SecurityViolationError(f"Absolute paths not allowed in workspace: '{relative_path}'")

        # Resolve path
        target = (proj_dir / relative_path).resolve()

        # Security check: target must strictly be inside proj_dir
        try:
            target.relative_to(proj_dir)
        except ValueError:
            raise SecurityViolationError(f"Path traversal detected: '{relative_path}' resolves outside workspace.")

        return target

    def write_file(self, project_id: str, relative_path: str, content: str) -> str:
        """Write content safely to a workspace file."""
        target = self.resolve_safe_path(project_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self.get_project_dir(project_id)).as_posix())

    def read_file(self, project_id: str, relative_path: str) -> str:
        """Read content from a workspace file."""
        target = self.resolve_safe_path(project_id, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found in workspace: {relative_path}")
        return target.read_text(encoding="utf-8")

    def list_files(self, project_id: str, subpath: str = "") -> List[str]:
        """List files in the workspace or a subfolder."""
        target = self.resolve_safe_path(project_id, subpath)
        if not target.exists() or not target.is_dir():
            return []
        proj_dir = self.get_project_dir(project_id)
        files = []
        for p in target.rglob("*"):
            if p.is_file():
                files.append(str(p.relative_to(proj_dir).as_posix()))
        return sorted(files)

    async def create_artifact(
        self,
        project_id: str,
        task_id: Optional[str],
        agent_id: Optional[str],
        kind: str,
        title: str,
        content: str,
        extension: str = "",
    ) -> Artifact:
        """Create an artifact file in the workspace and persist metadata in DB."""
        if not extension:
            ext_map = {
                "markdown": ".md",
                "code": ".py",
                "json": ".json",
                "image_svg": ".svg",
                "text": ".txt",
                "file": ".txt",
            }
            extension = ext_map.get(kind, ".txt")

        artifact_id = generate_id("art")
        filename = f"{title.lower().replace(' ', '_')}_{artifact_id[:6]}{extension}"
        rel_path = f"artifacts/{filename}"

        self.write_file(project_id, rel_path, content)

        summary = content[:200] + ("..." if len(content) > 200 else "")

        async with async_session_factory() as session:
            db_artifact = Artifact(
                id=artifact_id,
                project_id=project_id,
                task_id=task_id,
                kind=kind,
                path=rel_path,
                summary=summary,
                created_by_agent_id=agent_id,
                version=1,
            )
            session.add(db_artifact)
            await session.commit()
            await session.refresh(db_artifact)

        await event_bus.emit(
            event_type=EventType.ARTIFACT_CREATED,
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            payload={
                "artifact_id": artifact_id,
                "title": title,
                "kind": kind,
                "path": rel_path,
                "summary": summary,
            },
        )
        return db_artifact


workspace_manager = WorkspaceManager()
