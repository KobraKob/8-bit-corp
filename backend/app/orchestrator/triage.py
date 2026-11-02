from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.db.models import Agent, Task
from app.llm.router import llm_router
from app.llm.types import ChatMessage


class TriageObjective(BaseModel):
    title: str = Field(description="Clear title of the objective")
    department: str = Field(description="Department responsible: Engineering, Design, Marketing, Content, Research, Finance, Operations, Support, Special Projects")
    role_key: Optional[str] = Field(default=None, description="Recommended role key if known")
    description: str = Field(description="Scope and requirements for this objective")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Specific measurable criteria")
    depends_on: List[str] = Field(default_factory=list, description="Titles of prerequisites")
    notes: Optional[str] = Field(default="", description="Additional corporate directives")


class TriagePlan(BaseModel):
    complexity: str = Field(description="Complexity evaluation: trivial | standard | complex")
    summary: str = Field(description="Executive summary of the intake plan")
    objectives: List[TriageObjective] = Field(default_factory=list, description="List of high-level objectives")


class CEOTriage:
    """Intakes a user project and executes CEO triage to produce a structured TriagePlan."""

    @staticmethod
    async def triage_project(root_task: Task, ceo_agent: Agent) -> TriagePlan:
        prompt = (
            f"You are the CEO of Pixel Corp. Review this new client project submission:\n\n"
            f"Project Title: {root_task.title}\n"
            f"Client Brief: {root_task.original_goal}\n\n"
            f"Analyze requirements and produce a structured TriagePlan:\n"
            f"1. Determine complexity ('trivial', 'standard', 'complex').\n"
            f"2. Formulate 1-4 high-level objectives assigned to appropriate departments/roles.\n"
            f"3. Define concrete acceptance criteria and dependency order (DAG) if applicable.\n"
            f"Never reject any task as out of scope. If unusual, allocate to 'Special Projects'."
        )

        plan = await llm_router.execute_structured(
            tier=ceo_agent.model_tier,
            messages=[
                ChatMessage(role="system", content=ceo_agent.system_prompt),
                ChatMessage(role="user", content=prompt),
            ],
            schema_cls=TriagePlan,
            task_id=root_task.id,
            agent_id=ceo_agent.id,
        )

        logger.info(f"CEO Triage complete for task {root_task.id}: complexity={plan.complexity}, {len(plan.objectives)} objectives")
        return plan
