from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    JSON,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=True)
    brief = Column(Text, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=True)
    settings_json = Column(JSON, default=dict, nullable=False)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="project", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="project", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True)
    role_key = Column(String(100), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False, index=True)
    level = Column(Integer, default=5, nullable=False)
    reports_to_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    model_tier = Column(String(50), default="fast", nullable=False)
    system_prompt = Column(Text, nullable=False)
    tools_json = Column(JSON, default=list, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    sprite_json = Column(JSON, default=dict, nullable=False)
    api_key = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    @property
    def has_custom_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @property
    def masked_api_key(self) -> Optional[str]:
        if not self.api_key or len(self.api_key.strip()) < 8:
            return None
        k = self.api_key.strip()
        return f"{k[:4]}...{k[-4:]}"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    parent_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    root_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    depth = Column(Integer, default=0, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    original_goal = Column(Text, nullable=False)
    acceptance_criteria_json = Column(JSON, default=list, nullable=False)
    assignee_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    creator_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    reviewer_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    attempt = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    depends_on_json = Column(JSON, default=list, nullable=False)
    deliverable_artifact_id = Column(String(36), nullable=True)
    review_notes_json = Column(JSON, default=list, nullable=False)
    token_budget = Column(Integer, default=25000, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    priority = Column(Integer, default=5, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    project = relationship("Project", back_populates="tasks")
    children = relationship("Task", backref="parent", remote_side=[id], foreign_keys=[parent_id])


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    kind = Column(String(50), nullable=False)  # text|markdown|code|file|json|image_svg
    path = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)
    created_by_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="artifacts")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    from_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    to_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    kind = Column(String(50), nullable=False)
    payload_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    type = Column(String(100), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    payload_json = Column(JSON, default=dict, nullable=False)

    project = relationship("Project", back_populates="events")


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id = Column(String(36), primary_key=True)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    agent_id = Column(String(36), nullable=True, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    tier = Column(String(50), nullable=False)
    key_alias = Column(String(100), default="default", nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="success", nullable=False)
    error = Column(Text, nullable=True)
    cost_estimate = Column(Float, default=0.0, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    kind = Column(String(50), nullable=False)
    request_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending|approved|rejected
    decided_at = Column(DateTime(timezone=True), nullable=True)


class WikiNote(Base):
    __tablename__ = "wiki_notes"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(String(255), default="", nullable=False)
    created_by_agent_id = Column(String(36), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DailyUsage(Base):
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False, index=True)
    key_alias = Column(String(100), default="default", nullable=False, index=True)
    day = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    requests_count = Column(Integer, default=0, nullable=False)
    tokens_count = Column(Integer, default=0, nullable=False)
