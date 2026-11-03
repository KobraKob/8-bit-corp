import asyncio
import pytest
from app.db.session import init_db, async_session_factory
from app.core.config import get_app_settings
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.domain.org_model import seed_organization_from_config, hire_dynamic_agent, validate_org_config
from app.db.models import Agent
from sqlalchemy import select


@pytest.mark.asyncio
async def test_event_bus_emit_and_replay():
    await init_db()

    q = await event_bus.subscribe()

    evt1 = await event_bus.emit(
        event_type=EventType.TASK_CREATED,
        project_id="p1",
        task_id="t1",
        payload={"title": "Test Task 1"},
    )
    assert evt1.id is not None

    received = await asyncio.wait_for(q.get(), timeout=2.0)
    assert received.id == evt1.id
    assert received.type == EventType.TASK_CREATED

    await event_bus.unsubscribe(q)

    # Replay catch-up
    events_after = await event_bus.get_events_after(last_event_id=evt1.id - 1)
    assert len(events_after) >= 1
    assert any(e.id == evt1.id for e in events_after)


@pytest.mark.asyncio
async def test_org_seeding_and_dynamic_hire():
    await init_db()
    org_config = get_app_settings().org
    validate_org_config(org_config)
    await seed_organization_from_config(org_config)

    async with async_session_factory() as session:
        result = await session.execute(select(Agent))
        agents = result.scalars().all()
        assert len(agents) == 46
        assert sum(1 for agent in agents if agent.reports_to_agent_id) == 45

        # Verify CEO exists
        ceo = next((a for a in agents if a.role_key == "ceo"), None)
        assert ceo is not None
        assert ceo.level == 1

        # Verify subordinate reports_to wiring
        coo = next((a for a in agents if a.role_key == "coo"), None)
        assert coo is not None
        assert coo.reports_to_agent_id == ceo.id

        by_role = {}
        for agent in agents:
            if agent.status == "active":
                by_role.setdefault(agent.role_key, []).append(agent)
        assert all(len(by_role.get(key, [])) == role.count for key, role in org_config.roles.items())
        by_id = {agent.id for agent in agents if agent.status == "active"}
        for role_key, role in org_config.roles.items():
            if role.reports_to:
                manager_id = by_role[role.reports_to][0].id
                assert all(agent.reports_to_agent_id == manager_id for agent in by_role[role_key])
            else:
                assert all(agent.reports_to_agent_id is None for agent in by_role[role_key])
        assert all(agent.reports_to_agent_id is None or agent.reports_to_agent_id in by_id for agent in agents if agent.status == "active")

    # Test dynamic hire
    dynamic_agent = await hire_dynamic_agent(
        title="Web3 Rust Specialist",
        department="Special Projects",
        system_prompt="You build smart contracts in Rust.",
    )
    assert dynamic_agent.id is not None
    assert dynamic_agent.role_key == "web3_rust_specialist"
    assert dynamic_agent.department == "Special Projects"


def test_org_config_has_46_roles_and_valid_reporting_tree():
    roles = get_app_settings().org.roles
    assert sum(role.count for role in roles.values()) == 46
    assert roles["ceo"].reports_to is None

    for role_key, role in roles.items():
        if role_key == "ceo":
            continue
        assert role.reports_to in roles, f"{role_key} reports to missing role {role.reports_to}"
        assert roles[role.reports_to].level < role.level, f"{role_key} must report upward"

        visited = set()
        current = role_key
        while current:
            assert current not in visited, f"Reporting cycle detected at {current}"
            visited.add(current)
            current = roles[current].reports_to
