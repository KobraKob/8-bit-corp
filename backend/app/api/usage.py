from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.schemas import UsageResponse
from app.db.models import DailyUsage, LLMCall
from app.db.session import async_session_factory

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
async def get_usage():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with async_session_factory() as session:
        # Aggregated totals from llm_calls
        tot_stmt = select(
            func.count(LLMCall.id),
            func.sum(LLMCall.prompt_tokens),
            func.sum(LLMCall.completion_tokens),
            func.sum(LLMCall.cost_estimate),
        )
        tot_res = await session.execute(tot_stmt)
        calls_count, p_tokens, c_tokens, total_cost = tot_res.one()

        # Daily usage per model
        daily_stmt = select(DailyUsage).where(DailyUsage.day == today)
        daily_res = await session.execute(daily_stmt)
        daily_usages = daily_res.scalars().all()

        models_list: List[Dict[str, Any]] = [
            {
                "model": u.model,
                "day": u.day,
                "requests_count": u.requests_count,
                "tokens_count": u.tokens_count,
            }
            for u in daily_usages
        ]

        return UsageResponse(
            total_calls=calls_count or 0,
            total_prompt_tokens=p_tokens or 0,
            total_completion_tokens=c_tokens or 0,
            total_cost_estimate=round(total_cost or 0.0, 5),
            models_daily_usage=models_list,
        )
