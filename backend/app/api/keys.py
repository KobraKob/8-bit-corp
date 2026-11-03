from typing import List
from fastapi import APIRouter, HTTPException, status

from app.api.schemas import KeyAddRequest, KeyStatusResponse
from app.llm.key_pool import key_pool

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.get("", response_model=List[KeyStatusResponse])
async def list_keys() -> List[KeyStatusResponse]:
    """List all configured API keys in the pool, their health status, calls count, and manager status.
    Raw keys are masked for security."""
    pool_statuses = key_pool.get_pool_status()
    return [
        KeyStatusResponse(
            alias=s.alias,
            masked_key=s.masked_key,
            is_manager_dedicated=s.is_manager_dedicated,
            is_healthy=s.is_healthy,
            total_calls=s.total_calls,
            cooldown_remaining_sec=s.cooldown_remaining_sec,
        )
        for s in pool_statuses
    ]


@router.post("", response_model=KeyStatusResponse, status_code=status.HTTP_201_CREATED)
async def add_key(req: KeyAddRequest) -> KeyStatusResponse:
    """Add a new API key to the active rotation pool, optionally dedicated to higher managers."""
    try:
        alias = key_pool.add_key(
            key=req.key,
            alias=req.alias,
            is_manager_dedicated=req.is_manager_dedicated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    statuses = key_pool.get_pool_status()
    for s in statuses:
        if s.alias == alias:
            return KeyStatusResponse(
                alias=s.alias,
                masked_key=s.masked_key,
                is_manager_dedicated=s.is_manager_dedicated,
                is_healthy=s.is_healthy,
                total_calls=s.total_calls,
                cooldown_remaining_sec=s.cooldown_remaining_sec,
            )

    raise HTTPException(status_code=500, detail="Failed to register API key into pool.")


@router.delete("/{alias}")
async def remove_key(alias: str):
    """Remove a key from the active pool by alias."""
    removed = key_pool.remove_key(alias)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Key alias '{alias}' not found in pool.")
    return {"success": True, "message": f"Key '{alias}' removed from pool."}
