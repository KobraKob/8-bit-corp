import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.events.event_bus import event_bus
from app.events.event_types import EventPayload

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_event_stream(websocket: WebSocket):
    await websocket.accept()
    subscriber_queue = await event_bus.subscribe()
    outbound_queue: asyncio.Queue[EventPayload] = asyncio.Queue()
    replay_complete = asyncio.Event()

    async def client_listener():
        """Queue replay events; the main coroutine remains the only socket writer."""
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    if message.get("type") == "resume":
                        last_id = max(0, int(message.get("last_event_id", 0)))
                        missed = await event_bus.get_events_after(last_event_id=last_id)
                        for event in missed:
                            await outbound_queue.put(event)
                        replay_complete.set()
                except (TypeError, ValueError, json.JSONDecodeError) as parse_error:
                    logger.warning("Invalid WebSocket message: %s", parse_error)
        except WebSocketDisconnect:
            return

    async def relay_live_events():
        await replay_complete.wait()
        while True:
            event = await subscriber_queue.get()
            await outbound_queue.put(event)

    listener_task = asyncio.create_task(client_listener())
    relay_task = asyncio.create_task(relay_live_events())

    try:
        while True:
            event: EventPayload = await outbound_queue.get()
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.warning("WebSocket connection closed: %s", exc)
    finally:
        listener_task.cancel()
        relay_task.cancel()
        await event_bus.unsubscribe(subscriber_queue)
