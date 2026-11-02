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

    async def client_listener():
        """Listen for messages from client (e.g. resume requests with last_event_id)."""
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "resume":
                        last_id = msg.get("last_event_id", 0)
                        project_id = msg.get("project_id")
                        missed_events = await event_bus.get_events_after(last_event_id=last_id, project_id=project_id)
                        for evt in missed_events:
                            await websocket.send_text(evt.model_dump_json())
                except Exception as parse_err:
                    logger.warning(f"Failed to process client WS message: {parse_err}")
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    listener_task = asyncio.create_task(client_listener())

    try:
        while True:
            try:
                event_obj: EventPayload = await asyncio.wait_for(subscriber_queue.get(), timeout=0.5)
                await websocket.send_text(event_obj.model_dump_json())
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.warning(f"WebSocket connection closed: {exc}")
    finally:
        listener_task.cancel()
        await event_bus.unsubscribe(subscriber_queue)
