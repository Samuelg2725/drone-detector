"""
drone-detector/api/routes/config.py
Config Routes

Tanggung jawab:
- Menyediakan konfigurasi sistem (read)
- Mengizinkan update konfigurasi tertentu (write terbatas)
- Menjadi interface aman untuk UI / operator

Tidak mengandung:
- Logic hardware langsung
- DSP / detection
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from app.startup import app_context

router = APIRouter(prefix="/config", tags=["config"])


# ---------------------------------------------------------------------
# REST: READ CONFIG
# ---------------------------------------------------------------------

@router.get("/")
def get_config() -> Dict[str, Any]:
    """
    Ambil konfigurasi sistem saat ini (read-only snapshot).
    """
    if app_context.config is None:
        return {"available": False}

    # Hindari expose data sensitif
    safe_config = {
        "hardware": app_context.config.get("hardware", {}),
        "frequency_bands": app_context.config.get("frequency_bands", {}),
        "system": app_context.config.get("system", {}),
    }

    return {
        "available": True,
        "config": safe_config,
    }


# ---------------------------------------------------------------------
# REST: UPDATE CONFIG (LIMITED)
# ---------------------------------------------------------------------

@router.post("/update")
def update_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update konfigurasi sistem terbatas (non-destructive).

    Contoh payload yang diizinkan:
    {
        "hardware": {
            "center_frequency": 2450000000,
            "sample_rate": 10000000
        }
    }
    """
    if app_context.config is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    hardware_cfg = payload.get("hardware")
    if hardware_cfg:
        _update_hardware_config(hardware_cfg)

    return {
        "status": "ok",
        "message": "Configuration updated (partial)",
    }


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def _update_hardware_config(cfg: Dict[str, Any]) -> None:
    """
    Update konfigurasi hardware secara aman.
    """
    hw = app_context.config.get("hardware", {})

    # Whitelist field yang boleh diubah runtime
    allowed_fields = {
        "center_frequency",
        "sample_rate",
        "lna_gain",
        "vga_gain",
        "rx_gain",
        "gain",
    }

    for key, value in cfg.items():
        if key not in allowed_fields:
            continue
        hw[key] = value

    # Apply ke hardware jika sedang running
    if app_context.sdr:
        # Tidak semua SDR support hot-update → best-effort
        try:
            if hasattr(app_context.sdr, "center_frequency"):
                app_context.sdr.center_frequency = hw.get(
                    "center_frequency", app_context.sdr.center_frequency
                )
            if hasattr(app_context.sdr, "sample_rate"):
                app_context.sdr.sample_rate = hw.get(
                    "sample_rate", app_context.sdr.sample_rate
                )
        except Exception:
            # Jangan crash sistem karena config update
            pass
