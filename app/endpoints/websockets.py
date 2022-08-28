"""
WebSocket endpoints
"""

from fastapi import APIRouter, WebSocket


router = APIRouter()


@router.websocket("")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
):
    """
    websocket
    """
    await websocket.accept()
    await websocket.send_json({"ping": "pong"})
    await websocket.close()
