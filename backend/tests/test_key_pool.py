import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Agent
from app.db.session import async_session_factory
from app.domain.org_model import seed_organization_from_config
from app.llm.key_pool import KeyPoolManager
from app.llm.limiter import RateLimiter
from app.main import app


@pytest.mark.asyncio
async def test_key_pool_priority_allocation():
    pool = KeyPoolManager()
    # Clear any env keys for test isolation
    pool._keys.clear()

    # Add general keys and manager keys
    pool.add_key("gsk_general_alpha_12345678", alias="gen_1", is_manager_dedicated=False)
    pool.add_key("gsk_general_beta_12345678", alias="gen_2", is_manager_dedicated=False)
    pool.add_key("gsk_executive_vip_12345678", alias="mgr_1", is_manager_dedicated=True)

    # 1. Higher Manager (Level 1: CEO) should be allocated manager dedicated key
    k_mgr, alias_mgr = pool.select_key_for_agent(agent_level=1)
    assert alias_mgr == "mgr_1"
    assert k_mgr == "gsk_executive_vip_12345678"

    # 2. Subordinate / Associate (Level 5: Engineer) should be allocated from general pool
    k_assoc, alias_assoc = pool.select_key_for_agent(agent_level=5)
    assert alias_assoc in ("gen_1", "gen_2")
    assert alias_assoc != "mgr_1"

    # 3. Agent with dedicated custom API key override
    k_custom, alias_custom = pool.select_key_for_agent(
        agent_level=5, dedicated_key="gsk_custom_dev_override_9999"
    )
    assert k_custom == "gsk_custom_dev_override_9999"
    assert "custom_" in alias_custom


@pytest.mark.asyncio
async def test_key_pool_failover_on_rate_limit():
    pool = KeyPoolManager()
    pool._keys.clear()

    pool.add_key("gsk_key_11111111111", alias="key_1", is_manager_dedicated=False)
    pool.add_key("gsk_key_22222222222", alias="key_2", is_manager_dedicated=False)

    # First selection gets key_1
    _, alias1 = pool.select_key_for_agent(agent_level=5)
    assert alias1 == "key_1"

    # Simulate key_1 hitting 429
    pool.mark_key_rate_limited(alias="key_1", cooldown_sec=10.0)

    # Next call must failover automatically to key_2
    _, alias2 = pool.select_key_for_agent(agent_level=5)
    assert alias2 == "key_2"


@pytest.mark.asyncio
async def test_rate_limiter_per_key_isolation():
    limiter = RateLimiter()
    model = "llama-3.3-70b-versatile"

    # Consume all RPM on general key
    # Bucket capacity is min(rpm_limit, 30) = 30
    for _ in range(30):
        acquired = await limiter.acquire(model=model, key_alias="gen_key_1", estimated_tokens=10, max_wait_sec=0.01)
        assert acquired is True

    # 31st request on gen_key_1 should be rejected / exhausted
    blocked = await limiter.acquire(model=model, key_alias="gen_key_1", estimated_tokens=10, max_wait_sec=0.01)
    assert blocked is False

    # But request on manager_key_1 MUST succeed because keys are strictly isolated in separate buckets!
    mgr_acquired = await limiter.acquire(model=model, key_alias="manager_key_1", estimated_tokens=10, max_wait_sec=0.01)
    assert mgr_acquired is True


@pytest.mark.asyncio
async def test_keys_api_endpoints_and_agent_key_override():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Add key via API
        resp = await client.post(
            "/api/keys",
            json={
                "key": "gsk_test_api_key_via_http_1234",
                "alias": "http_test_key",
                "is_manager_dedicated": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["alias"] == "http_test_key"
        assert data["is_manager_dedicated"] is True
        assert data["masked_key"].startswith("gsk_")
        assert "..." in data["masked_key"]

        # 2. List keys
        list_resp = await client.get("/api/keys")
        assert list_resp.status_code == 200
        keys_list = list_resp.json()
        aliases = [k["alias"] for k in keys_list]
        assert "http_test_key" in aliases

        # 3. Seed org and assign custom API key to an agent
        await seed_organization_from_config()
        agents_resp = await client.get("/api/agents")
        assert agents_resp.status_code == 200
        all_agents = agents_resp.json()
        assert len(all_agents) > 0
        target_agent = all_agents[0]

        # Patch agent with custom API key
        patch_resp = await client.patch(
            f"/api/agents/{target_agent['id']}",
            json={"api_key": "gsk_agent_dedicated_secret_7777"},
        )
        assert patch_resp.status_code == 200
        patched_data = patch_resp.json()
        assert patched_data["has_custom_api_key"] is True
        assert patched_data["masked_api_key"] == "gsk_...7777"

        # 4. Remove test key from pool
        del_resp = await client.delete("/api/keys/http_test_key")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True
