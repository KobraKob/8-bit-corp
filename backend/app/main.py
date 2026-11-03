from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
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
from app.db.session import init_db
from app.domain.org_model import seed_organization_from_config
from app.orchestrator.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Pixel Corp backend...")
    await init_db()
    await seed_organization_from_config()
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
    allow_origins=["*"],  # Permits local dev frontends
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(agents_router)
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
    return {"ready": True, "scheduler_running": scheduler.running}
