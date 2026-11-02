from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select

from app.db.models import Artifact
from app.db.session import async_session_factory
from app.workspace.workspace_manager import workspace_manager

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str):
    async with async_session_factory() as session:
        art = await session.get(Artifact, artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")

        try:
            content = workspace_manager.read_file(art.project_id, art.path)
        except Exception:
            content = "(Unable to read content from disk)"

        return {
            "id": art.id,
            "project_id": art.project_id,
            "task_id": art.task_id,
            "kind": art.kind,
            "path": art.path,
            "summary": art.summary,
            "version": art.version,
            "created_by_agent_id": art.created_by_agent_id,
            "created_at": art.created_at,
            "content": content,
        }


@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    async with async_session_factory() as session:
        art = await session.get(Artifact, artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")

        full_path = workspace_manager.resolve_safe_path(art.project_id, art.path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Artifact file missing from disk")

        filename = Path(art.path).name
        return FileResponse(
            path=str(full_path),
            filename=filename,
            media_type="application/octet-stream",
        )
