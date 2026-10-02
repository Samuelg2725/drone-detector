#!/usr/bin/env python3
"""
drone_dashboard_backend.py - backend for ui/dashboard.html, fed by real
HackRF data.

Every sweep hops the HackRF across the whole 2.4GHz band (2400-2485MHz)
and the 5.8GHz FPV band (5645-5925MHz), 14MHz at a time, and looks for
signals shaped like drone video links - see rf_detector.py for exactly
how. If you've run calibrate_detector.py with your own drone, the
signatures it learned (drone_signatures.json) are matched first.

It does NOT identify drone models, and shape matches are labelled
"unverified": an analog video sender or WiFi can have the same shape.

Usage:
    python3 drone_dashboard_backend.py              # both bands
    python3 drone_dashboard_backend.py --bands 2.4  # just one band
Then open http://localhost:8000 in a browser.
"""
import argparse
import asyncio
import json
import os
import threading
import time
import uuid
from collections import deque

import uvicorn
import websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import rf_detector as rf

# Optional: the domain/algorithms modulation classifier. Corroborating
# info only - never required, never a vote for "this is a drone".
try:
    from domain.algorithms import create_spectrum_analyzer
    MODULATION_ANALYSIS_AVAILABLE = True
except ImportError:
    MODULATION_ANALYSIS_AVAILABLE = False

# ======================== Configuration ======================== #

SWEEP_BANDS = list(rf.BANDS)       # overridden by --bands
SWEEP_PAUSE_S = 0.2                # rest between full sweeps

# The dashboard shows "HackRF connected" only if a sweep actually
# finished recently - not just because the script is running.
STALE_AFTER_S = 10.0

receiver = None
signatures = []

# ======================== Shared state ======================== #

detections = deque(maxlen=200)
alerts = deque(maxlen=100)
start_time = time.time()
latest_spectrum = None
scan_stats = {"scans_ok": 0, "scans_failed": 0, "last_ok": 0.0, "last_error": None, "sweep_seconds": None}

# ======================== WebSocket push (own thread, own event loop) ======================== #

ws_clients = set()
ws_loop = None


async def ws_handler(websocket):
    ws_clients.add(websocket)
    try:
        async for _ in websocket:
            pass  # dashboard.html only sends plain 'subscribe:*' strings - nothing to act on
    finally:
        ws_clients.discard(websocket)


async def ws_broadcast(message: dict):
    if not ws_clients:
        return
    text = json.dumps(message)
    await asyncio.gather(*(c.send(text) for c in list(ws_clients)), return_exceptions=True)


def broadcast(message: dict):
    """Callable from any thread - schedules the actual send on the WS loop."""
    if ws_loop is not None:
        asyncio.run_coroutine_threadsafe(ws_broadcast(message), ws_loop)


def run_ws_server():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)

    async def main():
        async with websockets.serve(ws_handler, "0.0.0.0", 8082):
            await asyncio.Future()

    ws_loop.run_until_complete(main())


def current_metrics():
    return {
        "total_detections": len(detections),
        "active_threats": sum(1 for d in detections if d["threat_level"] == "high"),
        "avg_confidence": round(sum(d["confidence"] for d in detections) / len(detections), 3) if detections else 0,
        "system_uptime": time.time() - start_time,
    }


# ======================== HackRF scanning loop (own thread) ======================== #

# The same signal is seen on every sweep (~once a second). Treat a match
# within this window, same band/label, within 2MHz, as the SAME detection
# (bump its hit count) instead of flooding the table and alerts.
REPEAT_WINDOW_S = 15.0


def record_detection(det):
    now = time.time()
    for d in detections:
        if now - d["_last_seen"] > REPEAT_WINDOW_S:
            break  # newest first - everything after is older still
        if (d["band"] == det["band"] and d["drone_type"] == det["drone_type"]
                and abs(d["frequency_mhz"] - det["frequency_mhz"]) <= 2.0):
            d["_last_seen"] = now
            d["hits"] += 1
            d["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            d["confidence"] = max(d["confidence"], det["confidence"])
            return False
    det.update({
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hits": 1,
        "_last_seen": now,
    })
    detections.appendleft(det)
    return True


def public(det):
    return {k: v for k, v in det.items() if not k.startswith("_")}


def scanning_loop():
    global latest_spectrum
    analyzer = None
    if MODULATION_ANALYSIS_AVAILABLE:
        try:
            analyzer = create_spectrum_analyzer(sample_rate=rf.SAMPLE_RATE_HZ)
        except Exception as e:
            print(f"Modulation analyzer unavailable ({e}) - continuing without it")

    while True:
        try:
            t0 = time.time()
            spectra, found = {}, []
            for band in SWEEP_BANDS:
                result = rf.sweep_band(receiver, band)
                spectra[band] = rf.spectrum_summary(result)
                dets, _ = rf.detections_for_band(result, signatures, analyzer)
                found.extend(dets)

            scan_stats["scans_ok"] += 1
            scan_stats["last_ok"] = time.time()
            scan_stats["last_error"] = None
            scan_stats["sweep_seconds"] = round(time.time() - t0, 2)
            latest_spectrum = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "scan_number": scan_stats["scans_ok"],
                "sweep_seconds": scan_stats["sweep_seconds"],
                "bands": spectra,
            }
            broadcast({"type": "spectrum", "data": latest_spectrum})

            for det in found:
                if not record_detection(det):
                    continue
                broadcast({"type": "detection", "data": public(det)})
                if det["threat_level"] == "high":
                    alert = {
                        "title": "Possible drone signal",
                        "message": f"{det['drone_type']} at {det['frequency_mhz']}MHz ({det['band']}), "
                                   f"+{det['above_noise_db']}dB, ~{det['bandwidth_mhz']}MHz wide",
                        "timestamp": det["timestamp"],
                        "severity": "warning",
                    }
                    alerts.appendleft(alert)
                    broadcast({"type": "alert", "data": alert})

            if scan_stats["scans_ok"] % 5 == 1:
                parts = []
                for band, sp in spectra.items():
                    top = sp["peaks"][0] if sp["peaks"] else None
                    parts.append(f"{band}: floor {sp['noise_floor_db']}dB, " +
                                 (f"strongest +{top['above_noise_db']}dB at {top['frequency_mhz']}MHz"
                                  if top else "nothing above threshold"))
                hits = ", ".join(f"{d['drone_type']} @ {d['frequency_mhz']}MHz" for d in found) or "none"
                print(f"Sweep #{scan_stats['scans_ok']} ({scan_stats['sweep_seconds']}s) | "
                      + " | ".join(parts) + f" | drone-shaped: {hits}")

            broadcast({"type": "metrics", "data": current_metrics()})

        except Exception as e:
            scan_stats["scans_failed"] += 1
            scan_stats["last_error"] = str(e)
            print(f"Scan error: {e}")

        time.sleep(SWEEP_PAUSE_S)


# ======================== REST API (FastAPI) ======================== #

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def root():
    return FileResponse("ui/dashboard.html")


for _name in ("css", "js", "assets"):
    if os.path.isdir(f"ui/{_name}"):
        app.mount(f"/{_name}", StaticFiles(directory=f"ui/{_name}"), name=_name)


@app.get("/api/spectrum")
def api_spectrum():
    return {"success": latest_spectrum is not None, "data": latest_spectrum}


@app.get("/api/detections")
def api_detections(limit: int = 50):
    return {"success": True, "data": {"items": [public(d) for d in list(detections)[:limit]]}}


@app.get("/api/alerts")
def api_alerts(limit: int = 50, active: bool = False):
    return {"success": True, "data": {"items": list(alerts)[:limit]}}


@app.get("/api/system/metrics")
def api_metrics():
    return {"success": True, "data": current_metrics()}


@app.get("/api/hardware/status")
def api_hardware_status():
    return {
        "success": True,
        "data": {
            "device_type": "HackRF One",
            # Real status: did a capture actually finish recently?
            "connected": (time.time() - scan_stats["last_ok"]) < STALE_AFTER_S,
            "scans_ok": scan_stats["scans_ok"],
            "scans_failed": scan_stats["scans_failed"],
            "last_error": scan_stats["last_error"],
            "sweep_seconds": scan_stats["sweep_seconds"],
            "sweep_ranges_mhz": {b: [rf.BANDS[b][0] / 1e6, rf.BANDS[b][1] / 1e6] for b in SWEEP_BANDS},
            "calibrated_signatures": [sig["name"] for sig in signatures],
            "sample_rate_hz": rf.SAMPLE_RATE_HZ,
            "temperature_celsius": None,
            "uptime_seconds": time.time() - start_time,
            "cpu_percent": None,
            "memory_percent": None,
            "disk_percent": None,
            "network_io_mbps": None,
        },
    }


@app.get("/api/analytics/detections/trends")
def api_trends(days: int = 7):
    # Real counters, not fabricated history - today's bucket is the only
    # one with genuine data since this backend only just started running.
    return {"success": True, "data": {"daily_counts": [0] * (days - 1) + [len(detections)]}}


# ======================== Entry point ======================== #

def parse_args():
    ap = argparse.ArgumentParser(description="HackRF drone dashboard backend")
    ap.add_argument("--bands", nargs="+", choices=["2.4", "5.8"], default=["2.4", "5.8"],
                    help="which bands to sweep (default: both)")
    ap.add_argument("--lna", type=int, default=16, help="LNA gain 0-40 dB, steps of 8 (default 16)")
    ap.add_argument("--vga", type=int, default=20, help="VGA gain 0-62 dB, steps of 2 (default 20)")
    ap.add_argument("--amp", action="store_true",
                    help="enable the HackRF's +14dB front-end amp (helps weak 5.8GHz signals; "
                         "can overload near strong WiFi)")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    SWEEP_BANDS = [b + "GHz" for b in args.bands]
    signatures = rf.load_signatures()

    from python_hackrf import pyhackrf
    print("Connecting to HackRF...")
    receiver = rf.HackRFReceiver.open(pyhackrf, lna_gain=args.lna, vga_gain=args.vga, amp=args.amp)

    threading.Thread(target=run_ws_server, daemon=True).start()
    threading.Thread(target=scanning_loop, daemon=True).start()

    for b in SWEEP_BANDS:
        lo, hi = rf.BANDS[b]
        print(f"Sweeping {b}: {lo / 1e6:.0f}-{hi / 1e6:.0f}MHz in {len(rf.plan_hops(lo, hi))} hops")
    if signatures:
        print(f"Loaded {len(signatures)} calibrated signature(s): " + ", ".join(s_["name"] for s_ in signatures))
    else:
        print("No drone_signatures.json yet - using generic shape rules only (run calibrate_detector.py to add yours)")
    print("Dashboard: http://localhost:8000")
    print("WebSocket: ws://localhost:8082/ws")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        receiver.close(pyhackrf)
