import json
import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from openai import AsyncOpenAI

from app.core.logging import logger
from app.llm.types import ChatMessage, ChatRequest, ChatResponse, ToolCallRequest, UsageInfo


@runtime_checkable
class LLMProvider(Protocol):
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat completion request and return standardized response."""
        ...


class MockProvider:
    """Deterministic, scripted mock provider for unit and golden-path integration testing."""

    def __init__(self, script_responses: Optional[List[ChatResponse]] = None) -> None:
        self.script_responses: List[ChatResponse] = script_responses or []
        self.call_history: List[ChatRequest] = []

    async def chat(self, req: ChatRequest) -> ChatResponse:
        self.call_history.append(req)

        # 1. If an explicit scripted response is queued, pop it
        if self.script_responses:
            return self.script_responses.pop(0)

        # 2. Otherwise generate intelligent response based on messages & tools
        last_msg = req.messages[-1] if req.messages else None
        last_content = last_msg.content if last_msg else ""
        system_msg = next((m.content for m in req.messages if m.role == "system"), "")

        # Default usage
        usage = UsageInfo(prompt_tokens=150, completion_tokens=80, total_tokens=230)

        # Handle Structured JSON requests (when tools are None and prompt asks for JSON)
        full_conversation = " ".join([m.content or "" for m in req.messages])
        if "ReviewReport" in full_conversation or "review the submitted deliverable" in full_conversation.lower():
            review_json = {
                "decision": "approve",
                "summary": "Deliverable satisfies all acceptance criteria.",
                "criteria_evaluations": [
                    {
                        "criterion": "General acceptance criteria",
                        "passed": True,
                        "notes": "Verified all deliverable requirements.",
                    }
                ],
                "required_revisions": [],
            }
            return ChatResponse(
                text=json.dumps(review_json),
                usage=usage,
                finish_reason="stop",
            )

        if "TriagePlan" in full_conversation:
            triage_json = {
                "complexity": "standard",
                "summary": "Triage plan formulated: UI design and frontend implementation subtasks created.",
                "objectives": [
                    {
                        "title": "Design UI Mockup & System",
                        "department": "Design",
                        "role_key": "lead_uiux",
                        "description": "Create pixel-art UI mockup specifications and theme.",
                        "acceptance_criteria": ["UI design spec delivered", "Color palette defined"],
                        "depends_on": [],
                        "notes": "Fast turnaround required",
                    },
                    {
                        "title": "Build Web Application Codebase",
                        "department": "Engineering",
                        "role_key": "lead_frontend",
                        "description": "Implement HTML/CSS responsive web layout.",
                        "acceptance_criteria": ["Clean HTML structure", "Components match design spec"],
                        "depends_on": ["Design UI Mockup & System"],
                        "notes": "Ensure high quality",
                    },
                ],
            }
            return ChatResponse(
                text=json.dumps(triage_json),
                usage=usage,
                finish_reason="stop",
            )

        # A) CEO Triage & Delegation: if tools contain 'delegate' and last msg asks for delegation or triage
        if req.tools and any(t.get("function", {}).get("name") == "delegate" for t in req.tools):
            # Check if this is triage
            if "triage" in system_msg.lower() or "ceo" in system_msg.lower():
                return ChatResponse(
                    text="Intaking project request and delegating work across departments.",
                    tool_calls=[
                        ToolCallRequest(
                            id="call_del_1",
                            name="delegate",
                            arguments={
                                "subtasks": [
                                    {
                                        "title": "Design UI Mockup & System",
                                        "role_key": "lead_uiux",
                                        "description": "Create modern pixel-art web UI mockups and design specs.",
                                        "acceptance_criteria": ["Complete UI layout spec", "CSS color variables provided"],
                                        "depends_on": [],
                                    },
                                    {
                                        "title": "Build Web Application Codebase",
                                        "role_key": "lead_frontend",
                                        "description": "Implement responsive HTML/CSS/JS web components.",
                                        "acceptance_criteria": ["Clean valid code", "All components render cleanly"],
                                        "depends_on": ["Design UI Mockup & System"],
                                    },
                                ]
                            },
                        )
                    ],
                    usage=usage,
                    finish_reason="tool_calls",
                )

        # C) Work execution step: if tools contain 'create_artifact' or 'write_file' or 'submit_deliverable'
        has_submit = req.tools and any(t.get("function", {}).get("name") == "submit_deliverable" for t in req.tools)
        has_artifact = req.tools and any(t.get("function", {}).get("name") == "create_artifact" for t in req.tools)

        # If previous message is a tool result from creating artifact, submit deliverable
        if last_msg and last_msg.role == "tool" and has_submit:
            return ChatResponse(
                text="Task deliverable produced and ready for review.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_sub_1",
                        name="submit_deliverable",
                        arguments={
                            "summary": "Completed work matching all requirements.",
                            "artifact_ids": [],
                        },
                    )
                ],
                usage=usage,
                finish_reason="tool_calls",
            )

        if has_artifact:
            return ChatResponse(
                text="Generating deliverable artifact.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_art_1",
                        name="create_artifact",
                        arguments={
                            "kind": "markdown",
                            "title": "Deliverable Summary",
                            "content": "# Deliverable Report\n\nTask objectives successfully achieved.",
                        },
                    )
                ],
                usage=usage,
                finish_reason="tool_calls",
            )

        if has_submit:
            return ChatResponse(
                text="Completed deliverable without extra artifacts.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_sub_2",
                        name="submit_deliverable",
                        arguments={
                            "summary": "Task finished successfully.",
                            "artifact_ids": [],
                        },
                    )
                ],
                usage=usage,
                finish_reason="tool_calls",
            )

        # B) Review step: if prompt specifically asks to review
        if "review" in full_conversation.lower() and req.tools and any(t.get("function", {}).get("name") == "review_decision" for t in req.tools):
            return ChatResponse(
                text="Reviewing deliverable against acceptance criteria.",
                tool_calls=[
                    ToolCallRequest(
                        id="call_rev_1",
                        name="review_decision",
                        arguments={
                            "decision": "approve",
                            "notes": "All acceptance criteria verified and passed.",
                        },
                    )
                ],
                usage=usage,
                finish_reason="tool_calls",
            )

        # Fallback text response
        return ChatResponse(
            text="Completed analysis and actions.",
            tool_calls=[],
            usage=usage,
            finish_reason="stop",
        )


class GenericOpenAICompatProvider:
    """Provider for OpenAI-compatible REST APIs (e.g., Groq, vLLM, Ollama, OpenAI)."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "no-key-set")

    async def chat(self, req: ChatRequest) -> ChatResponse:
        start_time = time.monotonic()

        formatted_messages = []
        for m in req.messages:
            msg_dict: Dict[str, Any] = {"role": m.role, "content": m.content or ""}
            if m.name:
                msg_dict["name"] = m.name
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            formatted_messages.append(msg_dict)

        kwargs: Dict[str, Any] = {
            "model": req.model,
            "messages": formatted_messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.tools:
            kwargs["tools"] = req.tools
        if req.response_format:
            kwargs["response_format"] = req.response_format

        response = await self.client.chat.completions.create(**kwargs)
        latency_ms = (time.monotonic() - start_time) * 1000.0

        choice = response.choices[0]
        text_content = choice.message.content

        tool_calls: List[ToolCallRequest] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage = UsageInfo(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

        return ChatResponse(
            text=text_content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
            latency_ms=latency_ms,
        )


class GroqProvider(GenericOpenAICompatProvider):
    """Groq-specific OpenAI-compatible client adapter."""
    pass


class AnthropicProviderStub:
    """Stub adapter for Anthropic Claude provider for future integration."""

    async def chat(self, req: ChatRequest) -> ChatResponse:
        raise NotImplementedError("Anthropic provider adapter will be enabled in a future upgrade.")
