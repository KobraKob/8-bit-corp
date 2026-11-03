import asyncio
import os
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from app.core.config import get_app_settings
from app.core.errors import RateLimitExhaustedError
from app.core.ids import generate_id
from app.core.logging import logger
from app.db.models import Agent, LLMCall
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType
from app.llm.json_repair import extract_and_repair_json
from app.llm.key_pool import key_pool
from app.llm.limiter import rate_limiter
from app.llm.provider import (
    GenericOpenAICompatProvider,
    GroqProvider,
    LLMProvider,
    MockProvider,
)
from app.llm.types import ChatMessage, ChatRequest, ChatResponse

T = TypeVar("T", bound=BaseModel)
LLM_REQUEST_TIMEOUT_SECONDS = 45.0


class LLMRouter:
    """Manages tier resolution, multi-key pool selection, manager priority allocation,
    rate limit isolation per key, automatic failover, and call logging."""

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

        # Build every configured provider through the shared OpenAI-compatible adapter.
        for name, provider_cfg in self.settings.models.providers.items():
            if name == "mock":
                self.providers[name] = MockProvider()
                continue
            api_key = os.getenv(provider_cfg.api_key_env, "")
            if name == "groq":
                self.providers[name] = GroqProvider(base_url=provider_cfg.base_url, api_key=api_key)
            else:
                self.providers[name] = GenericOpenAICompatProvider(
                    base_url=provider_cfg.base_url,
                    api_key=api_key,
                )

    def get_provider(self, name: str) -> LLMProvider:
        if self.override_provider:
            return self.override_provider
        if name in self.providers:
            return self.providers[name]
        raise ValueError(
            f"LLM provider '{name}' is not configured. Add it to config/models.yaml; "
            "the router will not silently substitute the mock provider."
        )

    async def execute_chat(
        self,
        tier: str,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        priority: int = 5,
    ) -> ChatResponse:
        """Execute a chat call with per-key rate limiting, manager key isolation, and fallbacks."""
        tier_cfg = self.settings.models.tiers.get(tier)
        if not tier_cfg:
            tier_cfg = self.settings.models.tiers.get("smart")

        models_to_try = [tier_cfg.model] + tier_cfg.fallbacks if tier_cfg else ["mock-model"]
        provider_name = os.getenv("LLM_PROVIDER", tier_cfg.provider if tier_cfg else self.settings.models.default_provider).strip()
        provider = self.get_provider(provider_name)

        # Inspect calling agent for manager priority & dedicated custom API key
        agent_level = priority
        agent_dedicated_key = None
        if agent_id:
            try:
                async with async_session_factory() as session:
                    agt = await session.get(Agent, agent_id)
                    if agt:
                        agent_level = agt.level
                        agent_dedicated_key = agt.api_key
            except Exception as e:
                logger.warning(f"Could not load agent details for key allocation: {e}")

        last_error = None

        for model_name in models_to_try:
            # Select key for this agent from the pool
            if provider_name == "groq":
                api_key, key_alias = key_pool.select_key_for_agent(
                    agent_level=agent_level,
                    dedicated_key=agent_dedicated_key,
                )
            else:
                provider_cfg = self.settings.models.providers[provider_name]
                api_key = agent_dedicated_key or os.getenv(provider_cfg.api_key_env, "") or "no-key-set"
                key_alias = f"{provider_name}_agent" if agent_dedicated_key else f"{provider_name}_default"

            # Check rate limiting for this specific key
            if self.override_provider or provider_name == "mock":
                acquired = True
            else:
                acquired = await rate_limiter.acquire(
                    model=model_name,
                    key_alias=key_alias,
                    estimated_tokens=600,
                    max_wait_sec=5.0,
                )

            async with rate_limiter.concurrency_semaphore:
                if not acquired:
                    logger.warning(f"Rate limiter backed off for key '{key_alias}' on model {model_name}")
                    await event_bus.emit(
                        event_type=EventType.SYSTEM_RATE_LIMITED,
                        task_id=task_id,
                        agent_id=agent_id,
                        payload={"model": model_name, "tier": tier, "key_alias": key_alias},
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
                    api_key=api_key,
                    key_alias=key_alias,
                )

                try:
                    # Bound every provider request. The runtime's task-level
                    # timeout is checked between calls; without a provider-level
                    # timeout a single stalled HTTP request can occupy a worker
                    # indefinitely and prevent all project progress.
                    resp = await asyncio.wait_for(provider.chat(req), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
                    latency = (time.monotonic() - start_time) * 1000.0

                    # Log successful call to DB
                    await self._log_call(
                        call_id=call_id,
                        agent_id=agent_id,
                        task_id=task_id,
                        provider=provider_name,
                        model=model_name,
                        tier=tier,
                        key_alias=key_alias,
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
                    logger.error(f"LLM call failed with key '{key_alias}' on model {model_name}: {exc}")

                    # If 429 rate limit error, put this specific key on cooldown
                    if "429" in str(exc) or "rate_limit" in str(exc).lower():
                        key_pool.mark_key_rate_limited(key_alias, cooldown_sec=30.0)

                    await self._log_call(
                        call_id=call_id,
                        agent_id=agent_id,
                        task_id=task_id,
                        provider=provider_name,
                        model=model_name,
                        tier=tier,
                        key_alias=key_alias,
                        prompt_tokens=0,
                        completion_tokens=0,
                        latency_ms=latency,
                        status="error",
                        error=str(exc),
                    )

        # If all models/keys exhausted
        raise RateLimitExhaustedError(
            f"All models and keys exhausted for tier '{tier}'. Last error: {last_error}"
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
        key_alias: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        status: str,
        error: Optional[str],
    ) -> None:
        async with async_session_factory() as session:
            cost_estimate = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)
            db_call = LLMCall(
                id=call_id,
                agent_id=agent_id,
                task_id=task_id,
                provider=provider,
                model=model,
                tier=tier,
                key_alias=key_alias,
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
