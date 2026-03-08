import asyncio
import json
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# Simple in-process pub/sub for realtime events
_subscribers: list[asyncio.Queue] = []


async def broadcast_event(event: dict[str, Any]):
    """Call this from other routers when a new conversation is inserted."""
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _subscribers.remove(q)


@router.websocket("/ws/activity")
async def activity_websocket(websocket: WebSocket):
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)
    try:
        while True:
            # Send ping to keep connection alive every 30s if no events
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_text(json.dumps(event))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)
