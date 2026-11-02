import os
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from app.core.config import get_app_settings
from app.core.errors import RateLimitExhaustedError
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import LLMCall
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.llm.json_repair import extract_and_repair_json
from app.llm.limiter import rate_limiter
from app.llm.provider import (
    GenericOpenAICompatProvider,
    GroqProvider,
    LLMProvider,
    MockProvider,
)
from app.llm.types import ChatMessage, ChatRequest, ChatResponse

T = TypeVar("T", bound=BaseModel)


class LLMRouter:
    """Manages tier resolution, provider selection, fallback chains, rate limiting, and call logging."""

    def __init__(self, override_provider: Optional[LLMProvider] = None) -> None:
        self.settings = get_app_settings()
        self.providers: Dict[str, LLMProvider] = {}
        self.override_provider = override_provider
        self._init_providers()

    def _init_providers(self) -> None:
        if self.override_provider:
            self.providers["default"] = self.override_provider
            self.providers["mock"] = self.override_provider
            return

        # Setup Mock Provider
        self.providers["mock"] = MockProvider()

        # Setup Groq Provider if env exists or default
        groq_cfg = self.settings.models.providers.get("groq")
        if groq_cfg:
            api_key = os.getenv(groq_cfg.api_key_env, "")
            self.providers["groq"] = GroqProvider(base_url=groq_cfg.base_url, api_key=api_key)

    def get_provider(self, name: str) -> LLMProvider:
        if self.override_provider:
            return self.override_provider
        if name in self.providers:
            return self.providers[name]
        return self.providers.get("mock", MockProvider())

    async def execute_chat(
        self,
        tier: str,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        priority: int = 5,
    ) -> ChatResponse:
        """Execute a chat call with tier fallbacks, rate limiting, and DB logging."""
        tier_cfg = self.settings.models.tiers.get(tier)
        if not tier_cfg:
            # Fallback to smart
            tier_cfg = self.settings.models.tiers.get("smart")

        models_to_try = [tier_cfg.model] + tier_cfg.fallbacks if tier_cfg else ["mock-model"]
        provider_name = tier_cfg.provider if tier_cfg else "mock"
        provider = self.get_provider(provider_name)

        last_error = None

        for model_name in models_to_try:
            # If using override_provider (mock/tests), skip rate-limiting delay
            if self.override_provider:
                acquired = True
            else:
                acquired = await rate_limiter.acquire(model_name, estimated_tokens=600, max_wait_sec=5.0)

            # Concurrency limit and rate limit acquisition
            async with rate_limiter.concurrency_semaphore:
                if not acquired:
                    logger.warning(f"Rate limiter backed off for model: {model_name}")
                    await event_bus.emit(
                        event_type=EventType.SYSTEM_RATE_LIMITED,
                        task_id=task_id,
                        agent_id=agent_id,
                        payload={"model": model_name, "tier": tier},
                    )
                    continue

                call_id = generate_id("llm")
                start_time = time.monotonic()
                req = ChatRequest(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    priority=priority,
                    task_id=task_id,
                    agent_id=agent_id,
                )

                try:
                    resp = await provider.chat(req)
                    latency = (time.monotonic() - start_time) * 1000.0

                    # Log to DB
                    await self._log_call(
                        call_id=call_id,
                        agent_id=agent_id,
                        task_id=task_id,
                        provider=provider_name,
                        model=model_name,
                        tier=tier,
                        prompt_tokens=resp.usage.prompt_tokens,
                        completion_tokens=resp.usage.completion_tokens,
                        latency_ms=latency,
                        status="success",
                        error=None,
                    )
                    return resp

                except Exception as exc:
                    latency = (time.monotonic() - start_time) * 1000.0
                    last_error = str(exc)
                    logger.error(f"LLM call failed for model {model_name}: {exc}")
                    await self._log_call(
                        call_id=call_id,
                        agent_id=agent_id,
                        task_id=task_id,
                        provider=provider_name,
                        model=model_name,
                        tier=tier,
                        prompt_tokens=0,
                        completion_tokens=0,
                        latency_ms=latency,
                        status="error",
                        error=str(exc),
                    )

        # If all models in the fallback chain were exhausted:
        raise RateLimitExhaustedError(
            f"All models exhausted for tier '{tier}'. Last error: {last_error}"
        )

    async def execute_structured(
        self,
        tier: str,
        messages: List[ChatMessage],
        schema_cls: Type[T],
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> T:
        """Call LLM and parse response into Pydantic schema, performing 1 repair call on failure."""
        schema_desc = schema_cls.model_json_schema()
        system_instruction = (
            f"\nYou must respond ONLY with valid JSON conforming to the following JSON Schema:\n"
            f"{schema_desc}\nNo conversational commentary."
        )

        # Inject schema instruction into last message or new prompt
        msgs = list(messages)
        if msgs and msgs[0].role == "system":
            msgs[0] = ChatMessage(role="system", content=(msgs[0].content or "") + "\n" + system_instruction)
        else:
            msgs.insert(0, ChatMessage(role="system", content=system_instruction))

        resp = await self.execute_chat(
            tier=tier,
            messages=msgs,
            task_id=task_id,
            agent_id=agent_id,
        )

        raw_text = resp.text or ""
        try:
            parsed_json = extract_and_repair_json(raw_text)
            return schema_cls.model_validate(parsed_json)
        except (ValueError, ValidationError) as parse_err:
            logger.warning(f"Structured output validation failed: {parse_err}. Initiating 1 repair call...")

            # Repair call
            repair_messages = list(msgs) + [
                ChatMessage(role="assistant", content=raw_text),
                ChatMessage(
                    role="user",
                    content=(
                        f"Your output failed validation with the following error:\n{parse_err}\n"
                        f"Please fix and output ONLY valid JSON conforming to the required schema."
                    ),
                ),
            ]

            repair_resp = await self.execute_chat(
                tier=tier,
                messages=repair_messages,
                task_id=task_id,
                agent_id=agent_id,
            )

            second_json = extract_and_repair_json(repair_resp.text or "")
            return schema_cls.model_validate(second_json)

    async def _log_call(
        self,
        call_id: str,
        agent_id: Optional[str],
        task_id: Optional[str],
        provider: str,
        model: str,
        tier: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        status: str,
        error: Optional[str],
    ) -> None:
        async with async_session_factory() as session:
            # Estimate cost ($0 for groq free tier / mock, but provide estimate formula)
            cost_estimate = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)
            db_call = LLMCall(
                id=call_id,
                agent_id=agent_id,
                task_id=task_id,
                provider=provider,
                model=model,
                tier=tier,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status=status,
                error=error,
                cost_estimate=cost_estimate,
            )
            session.add(db_call)
            await session.commit()


# Singleton router
llm_router = LLMRouter()
