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
from app.orchestrator.checkpoints import load_task_checkpoint, save_task_checkpoint
from app.llm.router import llm_router
from app.llm.types import ChatMessage, ToolCallRequest
from app.tools.registry import ToolExecutor


class AgentRuntime:
    """Executes an agent's turn on a specific task with a bounded tool loop, loop detection, and event streaming."""

    def __init__(self, task_id: str, agent_id: str, lease_token: Optional[str] = None) -> None:
        self.task_id = task_id
        self.agent_id = agent_id
        self.lease_token = lease_token
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

        checkpoint = await load_task_checkpoint(self.task_id)
        saved_messages = checkpoint.get("runtime_messages")
        if saved_messages:
            messages = [ChatMessage.model_validate(item) for item in saved_messages]
        accumulated_tokens = int(checkpoint.get("runtime_tokens", 0))
        terminal_action: Optional[Dict[str, Any]] = checkpoint.get("terminal_action")
        consecutive_tool_signatures: List[str] = list(checkpoint.get("tool_signatures", []))
        tool_call_counts: Dict[str, int] = dict(checkpoint.get("tool_call_counts", {}))
        tool_call_total = int(checkpoint.get("tool_call_total", 0))
        created_artifact_ids: List[str] = list(checkpoint.get("created_artifact_ids", []))
        start_step = int(checkpoint.get("next_step", 0))

        if checkpoint.get("completed_runtime") and terminal_action:
            return {
                "terminal_action": terminal_action,
                "tokens_used": accumulated_tokens,
                "messages_count": len(messages),
                "resumed_from_completed_checkpoint": True,
            }

        # A crash between tool invocation and result persistence is ambiguous.
        # Never replay that side effect automatically; ask the model to inspect state.
        pending = checkpoint.get("pending_tool_call")
        if pending:
            messages.append(ChatMessage(
                role="tool",
                name=pending["name"],
                tool_call_id=pending["id"],
                content=json.dumps({
                    "success": False,
                    "interrupted": True,
                    "error": "Previous process stopped before recording this tool result. Inspect current state before attempting the action again.",
                }),
            ))
            await save_task_checkpoint(
                self.task_id,
                {"runtime_messages": [m.model_dump(mode="json") for m in messages], "pending_tool_call": None},
                lease_token=self.lease_token,
                event="runtime.recovered_pending_tool",
                message="Recovered an interrupted tool call without replaying its side effect.",
                level="warning",
                metadata={"tool": pending.get("name")},
            )

        start_time = time.monotonic()
        timeout_sec = 120.0

        for step in range(start_step, step_cap):
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
            # Execute one tool call per model turn. This makes the pending action
            # unambiguous and keeps recovery from replaying a batch of side effects.
            if resp.tool_calls:
                resp.tool_calls = resp.tool_calls[:1]
                messages.append(ChatMessage(
                    role="assistant", content=resp.text, tool_calls=resp.tool_calls,
                ))
            else:
                messages.append(ChatMessage(role="assistant", content=resp.text))
            await save_task_checkpoint(
                self.task_id,
                {
                    "runtime_tokens": accumulated_tokens,
                    "next_step": step + 1,
                    "runtime_messages": [m.model_dump(mode="json") for m in messages],
                    "tool_signatures": consecutive_tool_signatures,
                    "tool_call_counts": tool_call_counts,
                    "tool_call_total": tool_call_total,
                    "created_artifact_ids": created_artifact_ids,
                    "pending_tool_call": (
                        {"id": resp.tool_calls[0].id, "name": resp.tool_calls[0].name,
                         "arguments": resp.tool_calls[0].arguments}
                        if resp.tool_calls else None
                    ),
                },
                lease_token=self.lease_token,
                event="runtime.llm_response",
                message="Persisted model response checkpoint.",
                metadata={"step": step + 1, "tokens": resp.usage.total_tokens},
            )

            # 3. Check for tool calls
            if resp.tool_calls:
                for tc in resp.tool_calls:
                    tool_call_total += 1
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
                    tool_call_counts[sig] = tool_call_counts.get(sig, 0) + 1
                    if tool_call_total > step_cap * 2:
                        res = {"success": False, "error": "Task tool-call budget reached. Submit the best available result."}
                    elif tool_call_counts[sig] > 2:
                        logger.warning(f"Detected repeated tool call: {sig}. Intercepting.")
                        res = {"success": False, "error": "Repeated tool call limit reached. Choose a different action."}
                    else:
                        consecutive_tool_signatures.append(sig)
                        await save_task_checkpoint(
                            self.task_id,
                            {
                                "pending_tool_call": {"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                                "runtime_messages": [m.model_dump(mode="json") for m in messages],
                                "tool_signatures": consecutive_tool_signatures,
                                "tool_call_counts": tool_call_counts,
                                "tool_call_total": tool_call_total,
                                "runtime_tokens": accumulated_tokens,
                                "next_step": step + 1,
                            },
                            lease_token=self.lease_token,
                            event="runtime.tool_started",
                            message=f"Executing tool {tc.name}.",
                            metadata={"tool": tc.name, "tool_call_id": tc.id},
                        )
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
                    await save_task_checkpoint(
                        self.task_id,
                        {
                            "runtime_messages": [m.model_dump(mode="json") for m in messages],
                            "pending_tool_call": None,
                            "created_artifact_ids": created_artifact_ids,
                            "tool_signatures": consecutive_tool_signatures,
                            "tool_call_counts": tool_call_counts,
                            "tool_call_total": tool_call_total,
                            "runtime_tokens": accumulated_tokens,
                            "next_step": step + 1,
                        },
                        lease_token=self.lease_token,
                        event="runtime.tool_result",
                        message=f"Tool {tc.name} completed.",
                        metadata={"tool": tc.name, "success": bool(res.get("success", True))},
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
                # No tool calls: regular assistant message was checkpointed above.
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
            await save_task_checkpoint(
                self.task_id,
                {"runtime_tokens": accumulated_tokens,
                 "runtime_messages": [m.model_dump(mode="json") for m in wrapup_messages],
                 "next_step": step_cap},
                lease_token=self.lease_token,
                event="runtime.wrapup",
                message="Persisted final wrap-up response.",
            )

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
                t.checkpoint_json = {
                    **(t.checkpoint_json or {}),
                    "terminal_action": terminal_action,
                    "runtime_tokens": accumulated_tokens,
                    "completed_runtime": True,
                }
                await session.commit()

        return {
            "terminal_action": terminal_action,
            "tokens_used": accumulated_tokens,
            "messages_count": len(messages),
        }
