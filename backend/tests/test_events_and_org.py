import asyncio
import pytest
from app.db.session import init_db, async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.domain.org_model import seed_organization_from_config, hire_dynamic_agent
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
    await seed_organization_from_config()

    async with async_session_factory() as session:
        result = await session.execute(select(Agent))
        agents = result.scalars().all()
        assert len(agents) > 10

        # Verify CEO exists
        ceo = next((a for a in agents if a.role_key == "ceo"), None)
        assert ceo is not None
        assert ceo.level == 1

        # Verify subordinate reports_to wiring
        coo = next((a for a in agents if a.role_key == "coo"), None)
        assert coo is not None
        assert coo.reports_to_agent_id == ceo.id

    # Test dynamic hire
    dynamic_agent = await hire_dynamic_agent(
        title="Web3 Rust Specialist",
        department="Special Projects",
        system_prompt="You build smart contracts in Rust.",
    )
    assert dynamic_agent.id is not None
    assert dynamic_agent.role_key == "web3_rust_specialist"
    assert dynamic_agent.department == "Special Projects"
