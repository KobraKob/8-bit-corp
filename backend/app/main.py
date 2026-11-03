from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

load_dotenv()

from app.api.agents import router as agents_router
from app.api.company import router as company_router
from app.api.approvals import router as approvals_router
from app.api.artifacts import router as artifacts_router
from app.api.events import router as events_router
from app.api.keys import router as keys_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.usage import router as usage_router
from app.api.ws import router as ws_router
from app.core.config import get_app_settings
from app.core.logging import logger
from app.db.models import Agent, Project
from app.db.session import async_session_factory, init_db
from app.domain.org_model import seed_organization_from_config
from app.orchestrator.scheduler import scheduler
from app.workspace.workspace_manager import workspace_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Pixel Corp backend...")
    await init_db()
    await seed_organization_from_config()
    # Reconcile private workspaces for existing projects and the current roster.
    async with async_session_factory() as session:
        project_ids = (await session.scalars(select(Project.id))).all()
        active_agent_ids = (await session.scalars(select(Agent.id).where(Agent.status == "active"))).all()
    for project_id in project_ids:
        workspace_manager.provision_agent_directories(project_id, active_agent_ids)
    await scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down Pixel Corp backend...")
    await scheduler.stop()


settings = get_app_settings()

app = FastAPI(
    title="Pixel Corp API",
    description="Backend orchestration engine for Pixel Corp: AI Company Simulator in a Pixel-Art Office",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mount Routers
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(agents_router)
app.include_router(company_router)
app.include_router(artifacts_router)
app.include_router(approvals_router)
app.include_router(usage_router)
app.include_router(keys_router)
app.include_router(events_router)
app.include_router(ws_router)


@app.get("/api/health", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "pixel-corp-backend"}


@app.get("/api/ready", tags=["system"])
async def readiness_check():
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(f"Readiness database check failed: {exc}")
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "unavailable", "scheduler_running": scheduler.running},
        )

    if not scheduler.running:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "ok", "scheduler_running": False},
        )
    return {"ready": True, "database": "ok", "scheduler_running": True}
