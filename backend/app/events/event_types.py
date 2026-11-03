from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_DELEGATED = "task.delegated"
    TASK_SUBMITTED = "task.submitted"
    TASK_REVIEW_REQUESTED = "task.review_requested"
    TASK_REVISION_REQUESTED = "task.revision_requested"
    TASK_APPROVED = "task.approved"
    TASK_BLOCKED = "task.blocked"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_DONE = "task.done"

    # Agent actions
    AGENT_THINKING = "agent.thinking"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_TOOL_RESULT = "agent.tool_result"
    AGENT_MESSAGE = "agent.message"
    AGENT_HIRED = "agent.hired"
    AGENT_RETIRED = "agent.retired"

    # Office interactions
    OFFICE_MEETING_STARTED = "office.meeting.started"
    OFFICE_MEETING_ENDED = "office.meeting.ended"
    OFFICE_MEETING_JOINED = "office.meeting.joined"
    OFFICE_MEETING_LEFT = "office.meeting.left"
    OFFICE_CONVERSATION = "office.conversation"
    OFFICE_HANDOFF = "office.handoff"

    # Artifacts & Approvals
    ARTIFACT_CREATED = "artifact.created"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"

    # System & Project
    SYSTEM_RATE_LIMITED = "system.rate_limited"
    SYSTEM_QUOTA_EXHAUSTED = "system.quota_exhausted"
    SYSTEM_RESUMED = "system.resumed"
    PROJECT_COMPLETED = "project.completed"


class EventPayload(BaseModel):
    id: Optional[int] = None
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: EventType
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
