import os
import shutil
from pathlib import Path, PurePosixPath
import re
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
        for folder in ('agents', 'shared', 'artifacts'):
            (proj_dir / folder).mkdir(parents=True, exist_ok=True)
        return proj_dir

    def provision_agent_directories(self, project_id: str, agent_ids: List[str]) -> List[Path]:
        """Create one independent working directory for each agent in a project."""
        self.get_project_dir(project_id)
        return [self.get_agent_dir(project_id, agent_id) for agent_id in agent_ids]

    def get_agent_dir(self, project_id: str, agent_id: str) -> Path:
        """Get a private working directory for one agent inside one project."""
        safe_agent_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_"))
        if not safe_agent_id:
            raise SecurityViolationError("Agent id is not a valid workspace identifier.")
        agent_dir = self.resolve_safe_path(project_id, f"agents/{safe_agent_id}")
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def resolve_agent_path(self, project_id: str, agent_id: str, relative_path: str) -> Path:
        """Resolve a private agent path or an explicitly shared project path."""
        normalized = relative_path.replace("\\", "/")
        if (
            Path(normalized).is_absolute()
            or normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or ".." in PurePosixPath(normalized).parts
        ):
            raise SecurityViolationError(f"Unsafe agent workspace path: '{relative_path}'")

        if normalized == "shared" or normalized.startswith("shared/"):
            return self.resolve_safe_path(project_id, normalized)
        if normalized == "artifacts" or normalized.startswith("artifacts/"):
            return self.resolve_safe_path(project_id, normalized)

        safe_agent_id = "".join(c for c in agent_id if c.isalnum() or c in ("-", "_"))
        if not safe_agent_id:
            raise SecurityViolationError("Agent id is not a valid workspace identifier.")
        private_path = normalized or "."
        return self.resolve_safe_path(project_id, f"agents/{safe_agent_id}/{private_path}")

    def write_agent_file(self, project_id: str, agent_id: str, relative_path: str, content: str) -> str:
        normalized = relative_path.replace("\\\\", "/")
        if normalized == "artifacts" or normalized.startswith("artifacts/"):
            raise SecurityViolationError("Use create_artifact to register deliverables in the shared artifacts directory.")
        target = self.resolve_agent_path(project_id, agent_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self.get_project_dir(project_id)).as_posix())

    def read_agent_file(self, project_id: str, agent_id: str, relative_path: str) -> str:
        target = self.resolve_agent_path(project_id, agent_id, relative_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found in agent workspace: {relative_path}")
        return target.read_text(encoding="utf-8")

    def list_agent_files(self, project_id: str, agent_id: str, subpath: str = "") -> List[str]:
        target = self.resolve_agent_path(project_id, agent_id, subpath or ".")
        if not target.exists() or not target.is_dir():
            return []

        normalized = subpath.replace("\\", "/")
        is_shared_path = normalized == "shared" or normalized.startswith("shared/")
        is_artifact_path = normalized == "artifacts" or normalized.startswith("artifacts/")
        if is_shared_path or is_artifact_path:
            base_dir = self.get_project_dir(project_id)
        else:
            base_dir = self.get_agent_dir(project_id, agent_id)

        return sorted(
            str(path.relative_to(base_dir).as_posix())
            for path in target.rglob("*")
            if path.is_file()
        )

    def resolve_safe_path(self, project_id: str, relative_path: str) -> Path:
        """Resolve a relative path inside project directory, blocking directory traversal and absolute escapes."""
        proj_dir = self.get_project_dir(project_id)
        
        # Normalize Windows separators before validating, even on POSIX hosts.
        normalized_path = relative_path.replace("\\", "/")
        if (
            Path(normalized_path).is_absolute()
            or normalized_path.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized_path)
            or ".." in PurePosixPath(normalized_path).parts
        ):
            raise SecurityViolationError(f"Unsafe workspace path: '{relative_path}'")

        # Resolve path after normalization; this also catches existing symlink escapes.
        target = (proj_dir / normalized_path).resolve()

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
