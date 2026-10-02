"""
drone-detector/api/routes/spectrum.py
Spectrum Routes

Tanggung jawab:
- Menyediakan data spectrum terbaru via REST
- Menyediakan stream spectrum via WebSocket (read-only)

Tidak mengandung:
- FFT / DSP
- Hardware access
- Pipeline logic
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.startup import app_context
from infrastructure.messaging.websocket_server import (
    WebSocketConnection,
    WebSocketServer,
)

router = APIRouter(prefix="/spectrum", tags=["spectrum"])

# WebSocket broadcaster khusus spectrum
ws_server = WebSocketServer()


# ---------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------

@router.get("/latest")
def get_latest_spectrum() -> Dict[str, Any]:
    """
    Ambil snapshot spectrum terbaru (jika tersedia).

    Catatan:
    - Data berasal dari cache/event terakhir
    - Jika belum ada, return empty payload
    """
    cache = getattr(app_context, "spectrum_cache", None)
    if not cache:
        return {"available": False}

    return {
        "available": True,
        "timestamp": cache["timestamp"],
        "center_frequency": cache["center_frequency"],
        "frequencies": cache["frequencies"],
        "magnitude": cache["magnitude"],
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
async def spectrum_ws(websocket: WebSocket):
    """
    WebSocket endpoint untuk real-time spectrum update.
    """
    await websocket.accept()
    conn = FastAPIWS(websocket)
    ws_server.register(conn)

    try:
        while True:
            # Client message ignored (push-only)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_server.unregister(conn)


# ---------------------------------------------------------------------
# Wiring helper (dipanggil dari api/main.py)
# ---------------------------------------------------------------------

def wire_spectrum_events(global_ws_server: WebSocketServer) -> None:
    """
    Subscribe spectrum event dari EventBus dan broadcast ke WS client.

    Dipanggil sekali saat startup.
    """

    def on_spectrum(payload: Dict[str, Any]) -> None:
        # Cache untuk REST snapshot
        app_context.spectrum_cache = payload

        # Broadcast via WS
        ws_server.broadcast("spectrum", payload)

    app_context.event_bus.subscribe("spectrum", on_spectrum)
