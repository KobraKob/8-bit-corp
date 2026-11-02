from typing import List, Optional
from fastapi import APIRouter, Query

from app.events.event_bus import event_bus
from app.events.event_types import EventPayload

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=List[EventPayload])
async def get_events(
    after: int = Query(0, ge=0, description="Return events strictly after this monotonic ID"),
    project_id: Optional[str] = Query(None, description="Optional project filter"),
):
    """Retrieve historical events after an ID for replay and sync catch-up."""
    return await event_bus.get_events_after(last_event_id=after, project_id=project_id)
