"""
drone-detector/app/__init__.py
Application Layer

Layer ini berisi orchestration logic dan use-case level workflow.
Tidak boleh mengandung:
- implementasi hardware langsung
- detail database
- detail framework (FastAPI, WebSocket, dll)

App layer hanya mengatur:
- alur data
- lifecycle aplikasi
- pemanggilan domain + infrastructure
"""

from app.startup import initialize_app, shutdown_app
from app.pipelines import run_detection_pipeline
from app.services import (
    HardwareService,
    SignalProcessingService,
    DetectionService,
)

__all__ = [
    "initialize_app",
    "shutdown_app",
    "run_detection_pipeline",
    "HardwareService",
    "SignalProcessingService",
    "DetectionService",
]
