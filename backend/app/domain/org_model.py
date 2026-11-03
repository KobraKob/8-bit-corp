import json
from typing import Dict, List, Optional
from sqlalchemy import select

from app.core.config import OrgConfig, RoleDef, get_app_settings
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import Agent
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType


# Department color palettes and visual metadata for procedural office generation
DEPARTMENT_PALETTES = {
    "Executive": {"primary": "#eab308", "secondary": "#ca8a04", "badge": "crown"},
    "Operations": {"primary": "#3b82f6", "secondary": "#2563eb", "badge": "clipboard"},
    "Engineering": {"primary": "#10b981", "secondary": "#059669", "badge": "terminal"},
    "Design": {"primary": "#ec4899", "secondary": "#db2777", "badge": "palette"},
    "Marketing": {"primary": "#f97316", "secondary": "#ea580c", "badge": "megaphone"},
    "Content": {"primary": "#8b5cf6", "secondary": "#7c3aed", "badge": "feather"},
    "Research": {"primary": "#06b6d4", "secondary": "#0891b2", "badge": "microscope"},
    "Finance": {"primary": "#84cc16", "secondary": "#65a30d", "badge": "coins"},
    "Support": {"primary": "#64748b", "secondary": "#475569", "badge": "shield"},
    "Special Projects": {"primary": "#d946ef", "secondary": "#c026d3", "badge": "sparkles"},
}


def build_default_sprite(role: RoleDef, index: int = 0) -> Dict[str, any]:
    dept_style = DEPARTMENT_PALETTES.get(role.department, DEPARTMENT_PALETTES["Support"])
    return {
        "sprite_id": f"sprite_{role.key}_{index}",
        "skin_tone": (index % 4) + 1,
        "hair_style": (index % 5) + 1,
        "shirt_color": dept_style["primary"],
        "pants_color": "#1e293b",
        "accessory": "tie" if role.level <= 3 else "id_badge",
        "badge": dept_style["badge"],
    }


async def seed_organization_from_config(org_config: Optional[OrgConfig] = None) -> None:
    """Seed agents from org.yaml into the DB if the agents table is empty."""
    if org_config is None:
        org_config = get_app_settings().org

    async with async_session_factory() as session:
        result = await session.execute(select(Agent))
        existing_agents = result.scalars().all()
        if existing_agents:
            logger.info("Organization already seeded, skipping initial seed.")
            return

        logger.info("Seeding organization from configuration...")
        created_agents: Dict[str, Agent] = {}

        # 1. First pass: create all agents
        for role_key, role in org_config.roles.items():
            for i in range(role.count):
                agent_id = generate_id("agt")
                sprite = build_default_sprite(role, i)
                name = role.title if role.count == 1 else f"{role.title} {i + 1}"
                db_agent = Agent(
                    id=agent_id,
                    role_key=role.key,
                    display_name=name,
                    department=role.department,
                    level=role.level,
                    model_tier=role.tier,
                    system_prompt=role.prompt.strip(),
                    tools_json=role.tools,
                    status="active",
                    sprite_json=sprite,
                )
                session.add(db_agent)
                # Map by role_key for reporting structure
                created_agents[role_key] = db_agent

        await session.flush()

        # 2. Second pass: wire reports_to relationships
        for role_key, role in org_config.roles.items():
            if role.reports_to and role.reports_to in created_agents:
                manager_agent = created_agents[role.reports_to]
                subordinate_agent = created_agents.get(role_key)
                if subordinate_agent:
                    subordinate_agent.reports_to_agent_id = manager_agent.id

        await session.commit()
        logger.info(f"Successfully seeded {len(created_agents)} corporate agents.")


async def hire_dynamic_agent(
    title: str,
    department: str = "Special Projects",
    level: int = 5,
    reports_to_agent_id: Optional[str] = None,
    model_tier: str = "fast",
    system_prompt: str = "",
    tools: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> Agent:
    """Hire a new dynamic agent at runtime."""
    role_key = title.lower().replace(" ", "_")[:50]
    agent_id = generate_id("agt")
    tools_list = tools or ["submit_deliverable", "report_blocked", "create_artifact", "read_file", "write_file", "list_files"]
    sprite = {
        "sprite_id": f"sprite_{role_key}",
        "skin_tone": 2,
        "hair_style": 3,
        "shirt_color": DEPARTMENT_PALETTES.get(department, {}).get("primary", "#d946ef"),
        "pants_color": "#1e293b",
        "accessory": "special_badge",
        "badge": "sparkles",
    }

    async with async_session_factory() as session:
        new_agent = Agent(
            id=agent_id,
            role_key=role_key,
            display_name=title,
            department=department,
            level=level,
            reports_to_agent_id=reports_to_agent_id,
            model_tier=model_tier,
            system_prompt=system_prompt.strip(),
            tools_json=tools_list,
            status="active",
            sprite_json=sprite,
            api_key=api_key.strip() if api_key and api_key.strip() else None,
        )
        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)

    await event_bus.emit(
        event_type=EventType.AGENT_HIRED,
        agent_id=agent_id,
        payload={
            "agent_id": agent_id,
            "role_key": role_key,
            "title": title,
            "department": department,
            "model_tier": model_tier,
        },
    )
    return new_agent
