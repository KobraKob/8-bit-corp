import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from app.agents.context_builder import ContextBuilder
from app.core.config import get_app_settings
from app.core.logging import logger
from app.db.models import Agent, Message, Task
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.llm.router import llm_router
from app.llm.types import ChatMessage, ToolCallRequest
from app.tools.registry import ToolExecutor


class AgentRuntime:
    """Executes an agent's turn on a specific task with a bounded tool loop, loop detection, and event streaming."""

    def __init__(self, task_id: str, agent_id: str) -> None:
        self.task_id = task_id
        self.agent_id = agent_id
        self.settings = get_app_settings()

    async def run_turn(self, max_steps: Optional[int] = None) -> Dict[str, Any]:
        step_cap = max_steps or self.settings.settings.tool_step_cap
        token_budget = self.settings.settings.task_token_budget

        async with async_session_factory() as session:
            task = await session.get(Task, self.task_id)
            agent = await session.get(Agent, self.agent_id)
            if not task or not agent:
                raise ValueError(f"Task {self.task_id} or Agent {self.agent_id} not found")

        context_builder = ContextBuilder(task, agent)
        tool_executor = ToolExecutor(project_id=task.project_id, task_id=task.id, agent_id=agent.id)

        messages = await context_builder.build_messages()
        tools_spec = context_builder.get_allowed_tool_specs()

        accumulated_tokens = 0
        terminal_action: Optional[Dict[str, Any]] = None
        consecutive_tool_signatures: List[str] = []
        created_artifact_ids: List[str] = []

        start_time = time.monotonic()
        timeout_sec = 120.0

        for step in range(step_cap):
            # Check wall-clock timeout or token budget
            if time.monotonic() - start_time > timeout_sec or accumulated_tokens >= token_budget:
                logger.warning(f"Task {self.task_id} hit budget/timeout. Forcing wrap-up turn.")
                break

            # 1. Emit thinking event
            await event_bus.emit(
                event_type=EventType.AGENT_THINKING,
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent.id,
                payload={"step": step + 1, "agent_name": agent.display_name},
            )

            # 2. Call LLM
            resp = await llm_router.execute_chat(
                tier=agent.model_tier,
                messages=messages,
                tools=tools_spec if tools_spec else None,
                task_id=task.id,
                agent_id=agent.id,
                priority=agent.level,
            )

            accumulated_tokens += resp.usage.total_tokens

            # 3. Check for tool calls
            if resp.tool_calls:
                # Add assistant message with tool calls
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=resp.text,
                        tool_calls=resp.tool_calls,
                    )
                )

                for tc in resp.tool_calls:
                    # Emit tool call event
                    await event_bus.emit(
                        event_type=EventType.AGENT_TOOL_CALL,
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=agent.id,
                        payload={
                            "tool_name": tc.name,
                            "arguments": tc.arguments,
                        },
                    )

                    # Loop detector: check identical consecutive calls
                    sig = f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
                    if consecutive_tool_signatures and consecutive_tool_signatures[-1] == sig:
                        logger.warning(f"Detected loop call: {sig}. Intercepting.")
                        res = {"success": False, "error": "Loop detected: Identical consecutive tool call repeated."}
                    else:
                        consecutive_tool_signatures.append(sig)
                        # Execute tool
                        res = await tool_executor.execute(tc.name, tc.arguments)
                        if tc.name == "create_artifact" and res.get("artifact_id"):
                            created_artifact_ids.append(res["artifact_id"])

                    # Emit tool result event
                    await event_bus.emit(
                        event_type=EventType.AGENT_TOOL_RESULT,
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=agent.id,
                        payload={"tool_name": tc.name, "result": res},
                    )

                    # Append tool result to context
                    messages.append(
                        ChatMessage(
                            role="tool",
                            name=tc.name,
                            tool_call_id=tc.id,
                            content=json.dumps(res),
                        )
                    )

                    # Check if terminal tool was called
                    if tc.name in ("submit_deliverable", "delegate", "report_blocked"):
                        if tc.name == "submit_deliverable" and not tc.arguments.get("artifact_ids") and created_artifact_ids:
                            tc.arguments["artifact_ids"] = list(created_artifact_ids)
                        terminal_action = {"tool": tc.name, "arguments": tc.arguments, "result": res}
                        break

                if terminal_action:
                    break

            else:
                # No tool calls: regular message
                messages.append(ChatMessage(role="assistant", content=resp.text))
                await event_bus.emit(
                    event_type=EventType.AGENT_MESSAGE,
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent.id,
                    payload={"text": resp.text},
                )
                # If no tools called and no terminal tool, finish turn
                break

        # If loop finished without terminal action, trigger wrap-up call
        if not terminal_action:
            wrapup_messages = await context_builder.build_messages(is_wrap_up=True)
            wrapup_resp = await llm_router.execute_chat(
                tier=agent.model_tier,
                messages=wrapup_messages,
                tools=tools_spec,
                task_id=task.id,
                agent_id=agent.id,
            )
            accumulated_tokens += wrapup_resp.usage.total_tokens

            summary_text = wrapup_resp.text or "Completed best-effort deliverable upon reaching step limit."
            terminal_action = {
                "tool": "submit_deliverable",
                "arguments": {"summary": summary_text, "artifact_ids": []},
                "result": {"success": True},
            }

        # Update task token usage in DB
        async with async_session_factory() as session:
            t = await session.get(Task, self.task_id)
            if t:
                t.tokens_used += accumulated_tokens
                await session.commit()

        return {
            "terminal_action": terminal_action,
            "tokens_used": accumulated_tokens,
            "messages_count": len(messages),
        }
