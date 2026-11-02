import asyncio
import pytest
from pydantic import BaseModel, Field

from app.core.errors import RateLimitExhaustedError
from app.db.session import init_db
from app.llm.json_repair import extract_and_repair_json
from app.llm.limiter import TokenBucket, RateLimiter
from app.llm.provider import MockProvider
from app.llm.router import LLMRouter
from app.llm.types import ChatMessage, ChatResponse, UsageInfo


class SamplePlan(BaseModel):
    objective: str
    steps: list[str] = Field(default_factory=list)


def test_json_repair_with_markdown_fences():
    raw = "```json\n{\n  \"objective\": \"Build app\",\n  \"steps\": [\"step 1\", \"step 2\"]\n}\n```"
    parsed = extract_and_repair_json(raw)
    assert parsed["objective"] == "Build app"
    assert len(parsed["steps"]) == 2


def test_json_repair_with_trailing_fluff_and_commas():
    raw = "Here is your output:\n{\n  \"objective\": \"Fix bug\",\n  \"steps\": [\"step 1\", \"step 2\",],\n}\nHope this helps!"
    parsed = extract_and_repair_json(raw)
    assert parsed["objective"] == "Fix bug"
    assert len(parsed["steps"]) == 2


@pytest.mark.asyncio
async def test_token_bucket_rate_limiting():
    # Capacity 2, refill 1 token/sec
    bucket = TokenBucket(capacity=2, refill_rate=1.0)
    assert await bucket.consume(1.0) is True
    assert await bucket.consume(1.0) is True
    # Now empty
    assert await bucket.consume(1.0) is False

    # Wait time should be positive
    wait = await bucket.wait_time_for(1.0)
    assert wait > 0.0


@pytest.mark.asyncio
async def test_rate_limiter_daily_counters():
    await init_db()
    limiter = RateLimiter()

    # Model mock-model has large quota, should succeed
    allowed, reason = await limiter.check_and_increment_daily("mock-model", est_tokens=100)
    assert allowed is True
    assert reason == ""


@pytest.mark.asyncio
async def test_llm_router_structured_repair():
    await init_db()

    # 1st response is malformed, 2nd response is valid JSON
    bad_resp = ChatResponse(
        text="Sorry I cannot do this: {objective: invalid_json...",
        usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    )
    good_resp = ChatResponse(
        text="```json\n{\"objective\": \"Deploy backend\", \"steps\": [\"build\", \"test\"]}\n```",
        usage=UsageInfo(prompt_tokens=15, completion_tokens=15, total_tokens=30),
    )

    mock_prov = MockProvider(script_responses=[bad_resp, good_resp])
    router = LLMRouter(override_provider=mock_prov)

    result = await router.execute_structured(
        tier="smart",
        messages=[ChatMessage(role="user", content="Plan backend deployment")],
        schema_cls=SamplePlan,
    )

    assert result.objective == "Deploy backend"
    assert result.steps == ["build", "test"]
    assert len(mock_prov.call_history) == 2  # 1 initial + 1 repair call
