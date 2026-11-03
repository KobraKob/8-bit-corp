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
    pending_outbound_task: asyncio.Task[EventPayload] | None = None

    try:
        while True:
            # Watch both the outbound queue and the receive loop. Otherwise a
            # disconnected client can leave this handler blocked forever.
            pending_outbound_task = asyncio.create_task(outbound_queue.get())
            done, _ = await asyncio.wait(
                {pending_outbound_task, listener_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if listener_task in done:
                pending_outbound_task.cancel()
                await asyncio.gather(pending_outbound_task, return_exceptions=True)
                pending_outbound_task = None
                # Propagate unexpected listener failures; normal disconnects
                # return cleanly from client_listener.
                await listener_task
                logger.info("WebSocket client disconnected.")
                break

            event = pending_outbound_task.result()
            pending_outbound_task = None
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except asyncio.CancelledError:
        # Preserve cancellation semantics while still running the cleanup below.
        logger.info("WebSocket connection cancelled during server shutdown.")
        raise
    except Exception as exc:
        logger.warning("WebSocket connection closed: %s", exc)
    finally:
        background_tasks = [listener_task, relay_task]
        if pending_outbound_task is not None:
            background_tasks.append(pending_outbound_task)

        for task in background_tasks:
            if not task.done():
                task.cancel()

        # Collect cancelled tasks before releasing the event-bus subscription.
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await event_bus.unsubscribe(subscriber_queue)
