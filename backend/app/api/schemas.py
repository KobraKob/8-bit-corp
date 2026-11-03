from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    client_name: Optional[str] = None
    brief: str = Field(min_length=1)
    due_at: Optional[datetime] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class ProjectResponse(BaseModel):
    id: str
    name: str
    client_name: Optional[str]
    brief: str
    status: str
    created_at: datetime
    due_at: Optional[datetime]
    settings_json: Dict[str, Any]


class TaskSubmitRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    acceptance_criteria: List[str] = Field(default_factory=list)
    priority: int = 5


class TaskResponse(BaseModel):
    id: str
    project_id: str
    parent_id: Optional[str]
    root_id: Optional[str]
    depth: int
    title: str
    description: str
    original_goal: str
    acceptance_criteria_json: List[str]
    assignee_agent_id: Optional[str]
    creator_agent_id: Optional[str]
    reviewer_agent_id: Optional[str]
    status: str
    attempt: int
    max_attempts: int
    depends_on_json: List[str]
    deliverable_artifact_id: Optional[str]
    review_notes_json: List[str]
    token_budget: int
    tokens_used: int
    priority: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]


class TaskTreeNode(TaskResponse):
    children: List["TaskTreeNode"] = Field(default_factory=list)


class AgentHireRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    department: str = Field(default="Special Projects")
    level: int = Field(default=5, ge=1, le=10)
    reports_to_agent_id: Optional[str] = None
    model_tier: str = Field(default="fast")
    system_prompt: str = Field(default="")
    tools: List[str] = Field(default_factory=list)
    api_key: Optional[str] = None


class AgentUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    system_prompt: Optional[str] = None
    model_tier: Optional[str] = None
    tools_json: Optional[List[str]] = None
    department: Optional[str] = None
    api_key: Optional[str] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role_key: str
    display_name: str
    department: str
    level: int
    reports_to_agent_id: Optional[str]
    model_tier: str
    system_prompt: str
    tools_json: List[str]
    status: str
    sprite_json: Dict[str, Any]
    has_custom_api_key: bool = False
    masked_api_key: Optional[str] = None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class UsageResponse(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_estimate: float
    models_daily_usage: List[Dict[str, Any]]


class KeyStatusResponse(BaseModel):
    alias: str
    masked_key: str
    is_manager_dedicated: bool
    is_healthy: bool
    total_calls: int
    cooldown_remaining_sec: float


class KeyAddRequest(BaseModel):
    key: str = Field(min_length=4)
    alias: Optional[str] = None
    is_manager_dedicated: bool = False
