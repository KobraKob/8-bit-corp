import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from sqlalchemy import select

from app.core.logging import logger
from app.db.models import Event
from app.db.session import async_session_factory
from app.events.event_types import EventPayload, EventType


class EventBus:
    """Central event bus: persists events to DB, then broadcasts asynchronously to active listeners."""

    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """Register a new listener queue for real-time streaming."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unregister a listener queue."""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def emit(
        self,
        event_type: EventType,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> EventPayload:
        """Persist an event to the DB and broadcast to subscribers."""
        payload_data = payload or {}
        now = datetime.now(timezone.utc)

        # 1. Persist to DB
        async with async_session_factory() as session:
            db_event = Event(
                ts=now,
                type=event_type.value,
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                payload_json=payload_data,
            )
            session.add(db_event)
            await session.commit()
            await session.refresh(db_event)
            event_id = db_event.id

        event_obj = EventPayload(
            id=event_id,
            ts=now,
            type=event_type,
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            payload=payload_data,
        )

        # 2. Broadcast to all active queues
        async with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event_obj)
                except Exception as exc:
                    logger.warning(f"Error dispatching to subscriber queue: {exc}")

        return event_obj

    async def get_events_after(self, last_event_id: int, project_id: Optional[str] = None) -> List[EventPayload]:
        """Fetch historical events after last_event_id for reconnect catch-up."""
        async with async_session_factory() as session:
            stmt = select(Event).where(Event.id > last_event_id)
            if project_id:
                stmt = stmt.where(Event.project_id == project_id)
            stmt = stmt.order_by(Event.id.asc())
            result = await session.execute(stmt)
            rows = result.scalars().all()

            return [
                EventPayload(
                    id=row.id,
                    ts=row.ts,
                    type=EventType(row.type),
                    project_id=row.project_id,
                    task_id=row.task_id,
                    agent_id=row.agent_id,
                    payload=row.payload_json,
                )
                for row in rows
            ]


# Singleton event bus
event_bus = EventBus()
