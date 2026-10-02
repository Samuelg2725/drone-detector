"""
drone-detector/api/routes/system.py
System Routes

Tanggung jawab:
- Menyediakan status sistem (health, uptime, counters)
- Kontrol lifecycle tingkat tinggi (start/stop pipeline)
- Endpoint operasional untuk monitoring & admin

Tidak mengandung:
- Logic detection
- DSP / ML
- Akses hardware low-level
"""

import time
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from app.startup import app_context
from app.services import DetectionService

router = APIRouter(prefix="/system", tags=["system"])

# Service instance (thin controller)
detector_service = DetectionService()

# Simple uptime tracking
_START_TIME = time.time()


# ---------------------------------------------------------------------
# STATUS & HEALTH
# ---------------------------------------------------------------------

@router.get("/status")
def system_status() -> Dict[str, Any]:
    """
    Status ringkas sistem.
    """
    return {
        "status": "ok",
        "uptime_sec": int(time.time() - _START_TIME),
        "initialized": app_context.config is not None,
        "pipeline_running": detector_service.is_running(),
        "streaming": app_context.iq_stream.is_running()
        if app_context.iq_stream
        else False,
        "sdr": app_context.sdr.status() if app_context.sdr else None,
        "event_bus": {
            "running": app_context.event_bus.is_running()
            if app_context.event_bus
            else False
        },
        "database": {
            "connected": app_context.database is not None
        },
    }


@router.get("/health")
def system_health() -> Dict[str, Any]:
    """
    Health check ringan (untuk load balancer / orchestrator).
    """
    if app_context.config is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    return {"status": "healthy"}


# ---------------------------------------------------------------------
# PIPELINE CONTROL
# ---------------------------------------------------------------------

@router.post("/pipeline/start")
def start_pipeline() -> Dict[str, Any]:
    """
    Start detection pipeline (idempotent).
    """
    if detector_service.is_running():
        return {"status": "already_running"}

    detector_service.start()
    return {"status": "started"}


@router.post("/pipeline/stop")
def stop_pipeline() -> Dict[str, Any]:
    """
    Stop detection pipeline (graceful).
    """
    if not detector_service.is_running():
        return {"status": "already_stopped"}

    detector_service.stop()
    return {"status": "stopped"}
