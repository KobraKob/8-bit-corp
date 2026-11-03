from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCallRequest]] = None


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    tools: Optional[List[Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    temperature: float = 0.2
    max_tokens: int = 4096
    priority: int = 5  # 1 (highest/CEO/review) to 10 (lowest)
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    api_key: Optional[str] = None
    key_alias: Optional[str] = "default"


class ChatResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[ToolCallRequest] = Field(default_factory=list)
    usage: UsageInfo = Field(default_factory=UsageInfo)
    finish_reason: Optional[str] = None
    raw_headers: Dict[str, str] = Field(default_factory=dict)
    latency_ms: float = 0.0
