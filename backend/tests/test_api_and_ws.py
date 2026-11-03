import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from app.db.models import Agent, Project
from app.db.session import async_session_factory
from app.domain.org_model import seed_organization_from_config
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.main import app
from app.orchestrator.scheduler import scheduler


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints(monkeypatch):
    monkeypatch.setattr(scheduler, "running", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        not_ready = await client.get("/api/ready")
        assert not_ready.status_code == 503
        assert not_ready.json()["ready"] is False

        monkeypatch.setattr(scheduler, "running", True)
        ready = await client.get("/api/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True


@pytest.mark.asyncio
async def test_project_and_task_api_workflow():
    await seed_organization_from_config()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create project
        create_resp = await client.post(
            "/api/projects",
            json={
                "name": "API Test Project",
                "client_name": "Test Client",
                "brief": "Build a responsive retro portfolio site",
            },
        )
        assert create_resp.status_code == 201
        proj_data = create_resp.json()
        project_id = proj_data["id"]
        assert proj_data["name"] == "API Test Project"

        # 2. List projects
        list_resp = await client.get("/api/projects")
        assert list_resp.status_code == 200
        assert any(p["id"] == project_id for p in list_resp.json())

        # 3. Submit a task
        task_resp = await client.post(
            f"/api/projects/{project_id}/tasks",
            json={
                "title": "Design Portfolio Theme",
                "description": "Develop CSS tokens and retro colors",
                "acceptance_criteria": ["CSS tokens ready"],
            },
        )
        assert task_resp.status_code == 201
        task_data = task_resp.json()
        assert task_data["depth"] == 0
        assert task_data["status"] == "assigned"

        # 4. Fetch tree
        tree_resp = await client.get(f"/api/projects/{project_id}/tree")
        assert tree_resp.status_code == 200
        tree = tree_resp.json()
        assert len(tree) >= 1

        # 5. List agents
        agents_resp = await client.get("/api/agents")
        assert agents_resp.status_code == 200
        assert len(agents_resp.json()) > 10

        # 6. Usage endpoint
        usage_resp = await client.get("/api/usage")
        assert usage_resp.status_code == 200
        assert "total_calls" in usage_resp.json()


@pytest.mark.asyncio
async def test_websocket_event_streaming_and_resume():
    # Emit an event
    evt = await event_bus.emit(
        event_type=EventType.TASK_CREATED,
        project_id="ws_proj",
        payload={"message": "WS live event test"},
    )
    assert evt.id is not None

    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        # Resume catch-up request
        ws.send_json({"type": "resume", "last_event_id": evt.id - 1})
        data = ws.receive_json()
        assert data["type"] == EventType.TASK_CREATED.value
        assert data["payload"]["message"] == "WS live event test"
