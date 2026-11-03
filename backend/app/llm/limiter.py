import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy import select

from app.core.config import LimitConfig, get_app_settings
from app.core.logging import logger
from app.db.models import DailyUsage
from app.db.session import async_session_factory
from app.events.event_bus import event_bus
from app.events.event_types import EventType


class TokenBucket:
    """Token bucket for tracking RPM and TPM rate limits."""

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)  # tokens per second
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, amount: float = 1.0) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

    async def wait_time_for(self, amount: float = 1.0) -> float:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            curr = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if curr >= amount:
                return 0.0
            deficit = amount - curr
            return deficit / self.refill_rate if self.refill_rate > 0 else 1.0


class RateLimiter:
    """Per-Key Central Rate Limiter: isolates token buckets and daily quotas per (model, key_alias).
    Enables horizontal scaling across 5-10 API keys without rate-limit interference."""

    def __init__(self) -> None:
        self.settings = get_app_settings()
        self.buckets_rpm: Dict[str, TokenBucket] = {}
        self.buckets_tpm: Dict[str, TokenBucket] = {}
        self.concurrency_semaphore = asyncio.Semaphore(self.settings.settings.global_concurrency * 4)

    def _get_bucket_key(self, model: str, key_alias: str) -> str:
        return f"{model}:{key_alias}"

    def _ensure_buckets(self, model: str, key_alias: str) -> Tuple[TokenBucket, TokenBucket]:
        b_key = self._get_bucket_key(model, key_alias)
        if b_key not in self.buckets_rpm:
            limit_cfg = self.settings.models.limits.get(model, LimitConfig())
            self.buckets_rpm[b_key] = TokenBucket(
                capacity=limit_cfg.rpm,
                refill_rate=limit_cfg.rpm / 60.0,
            )
            self.buckets_tpm[b_key] = TokenBucket(
                capacity=limit_cfg.tpm,
                refill_rate=limit_cfg.tpm / 60.0,
            )
        return self.buckets_rpm[b_key], self.buckets_tpm[b_key]

    def _get_today_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def check_and_increment_daily(
        self,
        model: str,
        key_alias: str = "default",
        est_tokens: int = 500,
    ) -> Tuple[bool, str]:
        """Check if daily limits (RPD, TPD) are exceeded for this specific API key."""
        today = self._get_today_str()
        limit_cfg = self.settings.models.limits.get(model, LimitConfig())

        async with async_session_factory() as session:
            stmt = select(DailyUsage).where(
                DailyUsage.model == model,
                DailyUsage.key_alias == key_alias,
                DailyUsage.day == today,
            )
            result = await session.execute(stmt)
            usage = result.scalar_one_or_none()

            if not usage:
                usage = DailyUsage(
                    model=model,
                    key_alias=key_alias,
                    day=today,
                    requests_count=0,
                    tokens_count=0,
                )
                session.add(usage)
                await session.flush()

            if usage.requests_count + 1 > limit_cfg.rpd:
                return False, f"Daily requests quota exceeded for key '{key_alias}' on {model} ({usage.requests_count}/{limit_cfg.rpd})"
            if usage.tokens_count + est_tokens > limit_cfg.tpd:
                return False, f"Daily tokens quota exceeded for key '{key_alias}' on {model} ({usage.tokens_count}/{limit_cfg.tpd})"

            usage.requests_count += 1
            usage.tokens_count += est_tokens
            await session.commit()

        return True, ""

    async def acquire(
        self,
        model: str,
        key_alias: str = "default",
        estimated_tokens: int = 500,
        max_wait_sec: float = 60.0,
    ) -> bool:
        """Wait for rate limit availability for this specific key within max_wait_sec."""
        bucket_rpm, bucket_tpm = self._ensure_buckets(model, key_alias)

        # Check daily quota first
        allowed, reason = await self.check_and_increment_daily(model, key_alias, estimated_tokens)
        if not allowed:
            logger.warning(reason)
            await event_bus.emit(
                event_type=EventType.SYSTEM_QUOTA_EXHAUSTED,
                payload={"model": model, "key_alias": key_alias, "reason": reason},
            )
            return False

        start_time = time.monotonic()
        while time.monotonic() - start_time < max_wait_sec:
            wait_rpm = await bucket_rpm.wait_time_for(1.0)
            wait_tpm = await bucket_tpm.wait_time_for(float(estimated_tokens))
            max_wait = max(wait_rpm, wait_tpm)

            if max_wait <= 0.05:
                consumed_rpm = await bucket_rpm.consume(1.0)
                if consumed_rpm:
                    consumed_tpm = await bucket_tpm.consume(float(estimated_tokens))
                    if consumed_tpm:
                        return True
            wait_step = min(max(max_wait, 0.1), 2.0)
            await asyncio.sleep(wait_step)

        return False


rate_limiter = RateLimiter()
