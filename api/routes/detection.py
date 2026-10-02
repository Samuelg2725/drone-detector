"""
drone-detector/api/routes/detection.py
Detection Routes

Tanggung jawab:
- Menyediakan history deteksi via REST
- Menyediakan stream event deteksi via WebSocket (read-only)

Tidak mengandung:
- Logic detection
- DSP / ML
- Hardware access
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.startup import app_context
from domain.entities.detection import ThreatLevel
from infrastructure.messaging.websocket_server import (
    WebSocketConnection,
    WebSocketServer,
)
from infrastructure.storage.repositories import DetectionRepository

router = APIRouter(prefix="/detection", tags=["detection"])

# WebSocket broadcaster khusus detection
ws_server = WebSocketServer()


# ---------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------

@router.get("/latest")
def get_latest_detections(
    limit: int = Query(50, ge=1, le=500),
    min_threat: Optional[ThreatLevel] = Query(None),
) -> Dict[str, Any]:
    """
    Ambil history deteksi terbaru.

    Query Params:
    - limit: jumlah maksimum record
    - min_threat: filter minimum ThreatLevel
    """
    if app_context.database is None:
        return {"available": False, "items": []}

    repo = DetectionRepository(app_context.database)

    items = [
        event.to_dict()
        for event in repo.get_latest(limit=limit, min_threat=min_threat)
    ]

    return {
        "available": True,
        "count": len(items),
        "items": items,
    }


# ---------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------

class FastAPIWS(WebSocketConnection):
    """
    Adapter FastAPI WebSocket → WebSocketConnection
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    def send(self, message: str) -> None:
        import asyncio
        asyncio.create_task(self.websocket.send_text(message))


@router.websocket("/ws")
async def detection_ws(websocket: WebSocket):
    """
    WebSocket endpoint untuk real-time detection events.
    """
    await websocket.accept()
    conn = FastAPIWS(websocket)
    ws_server.register(conn)

    try:
        while True:
            # Push-only; ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_server.unregister(conn)


# ---------------------------------------------------------------------
# Wiring helper (dipanggil dari api/main.py)
# ---------------------------------------------------------------------

def wire_detection_events(global_ws_server: WebSocketServer) -> None:
    """
    Subscribe detection event dari EventBus dan broadcast ke WS client.

    Dipanggil sekali saat startup.
    """

    def on_detection(payload: Dict[str, Any]) -> None:
        ws_server.broadcast("detection", payload)

    app_context.event_bus.subscribe("detection", on_detection)
