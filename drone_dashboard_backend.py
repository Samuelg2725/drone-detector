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
# Sweeps spent learning the normal background (WiFi etc.) at startup,
# before calibration-free hopping detection switches on. Keep drones
# OFF for this (~25s with both bands). Overridden by --learn-sweeps.
LEARN_SWEEPS = 20

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
    now = time.time()
    active = [d for d in detections if is_active(d, now)]
    return {
        "total_detections": len(detections),
        "active_threats": sum(1 for d in active if d["threat_level"] == "high"),
        "active_drones": len(active),
        # Live value for the confidence chart: strongest active track, 0 if none.
        "current_confidence": max((d["confidence"] for d in active), default=0.0),
        "avg_confidence": round(sum(d["confidence"] for d in detections) / len(detections), 3) if detections else 0,
        "system_uptime": now - start_time,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ======================== HackRF scanning loop (own thread) ======================== #

# A drone is a "track": ACTIVE while it keeps being seen, GONE once it
# hasn't been seen for TRACK_TIMEOUT_S (~10 sweeps with both bands - a
# real drone recording never went more than one sweep without a match).
# A sighting after it's gone starts a new track.
TRACK_TIMEOUT_S = 12.0


def is_active(d, now=None):
    return ((now or time.time()) - d["_last_seen"]) <= TRACK_TIMEOUT_S


def record_detection(det):
    """Merge into the matching ACTIVE track, or start a new one. Returns
    True if this is a new track."""
    now = time.time()
    for d in detections:
        if not is_active(d, now):
            continue
        same_track = det.get("track_key") and d.get("track_key") == det["track_key"]
        same_signal = (d["drone_type"] == det["drone_type"]
                       and abs(d["frequency_mhz"] - det["frequency_mhz"]) <= 2.0)
        if d["band"] == det["band"] and (same_track or same_signal):
            if same_track and det["confidence"] > d["confidence"]:
                d["drone_type"] = det["drone_type"]   # e.g. upgraded to "matches calibrated ..."
            d["_last_seen"] = now
            d["hits"] += 1
            d["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            d["confidence"] = max(d["confidence"], det["confidence"])
            d["threat_level"] = rf.threat_level(d["confidence"])
            for k in ("frequency_mhz", "power_db", "above_noise_db", "bandwidth_mhz", "estimated_distance_m"):
                d[k] = det[k]
            if det.get("channels_seen"):
                d["channels_seen"] = det["channels_seen"]
            return False
    det.update({
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hits": 1,
        "_first_seen": now,
        "_last_seen": now,
    })
    detections.appendleft(det)
    return True


def end_lost_tracks():
    """Mark tracks that just went quiet as GONE and raise an alert."""
    now = time.time()
    for d in detections:
        if d.get("_ended") or is_active(d, now):
            continue
        d["_ended"] = True
        alert = {
            "title": "Drone signal lost",
            "message": f"{d['drone_type']} - last seen {d['last_seen'][11:]}, "
                       f"active for {int(d['_last_seen'] - d['_first_seen'])}s",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "severity": "info",
        }
        alerts.appendleft(alert)
        broadcast({"type": "alert", "data": alert})


def current_tracks(max_age_s=600):
    """Active tracks first, then recently ended ones."""
    now = time.time()
    tracks = [d for d in detections if now - d["_last_seen"] <= max_age_s]
    tracks.sort(key=lambda d: (not is_active(d, now), -d["_last_seen"]))
    return [public(d) for d in tracks[:20]]


def public(det):
    now = time.time()
    out = {k: v for k, v in det.items() if not k.startswith("_") and k != "track_key"}
    out["status"] = "active" if is_active(det, now) else "gone"
    out["duration_s"] = int(det["_last_seen"] - det["_first_seen"])
    out["seen_ago_s"] = int(now - det["_last_seen"])
    return out


# Shape-rule matches below this confidence are mostly WiFi (they're
# halved on WiFi channels) - left on the live spectrum as RF activity,
# not listed as detections. On a real drone-off recording this removed
# 7 of the 8 generic matches; the drone's own signal is caught by the
# hopping detector instead.
MIN_SHAPE_CONFIDENCE = 0.5
LINK_SPAN_MEMORY_SWEEPS = 10


class BandState:
    def __init__(self, learn_sweeps):
        self.background = rf.BackgroundModel()
        self.hop = rf.HopDetector(self.background)
        self.trackers = {}
        self.learn_sweeps = learn_sweeps
        self.link_span = None        # (lo_mhz, hi_mhz) of the last hopping link
        self.link_span_ttl = 0       # sweeps left before that span is forgotten

    @property
    def learning(self):
        return self.background.sweeps < self.learn_sweeps


def fuse_band(band, dets, clusters, state):
    """Turn one band's raw per-cluster matches into what the dashboard
    shows: at most one 'frequency-hopping link' detection (calibration-
    free hop detector and/or a confirmed calibrated signature), plus any
    remaining shape matches that aren't just fragments of it."""
    hop = state.hop.update(clusters)
    if state.learning:
        hop = None

    # Calibrated signatures for this band.
    cal_confirmed, cal_unconfirmed = None, None
    for sig in signatures:
        if sig.get("band") != band:
            continue
        tracker = state.trackers.setdefault(sig["name"], rf.SignatureTracker(sig))
        hits = [d for d in dets if d.get("signature") == sig["name"]]
        confirmed, seen = tracker.update({d["channel_mhz"] for d in hits})
        if hits:
            best = dict(max(hits, key=lambda d: d["above_noise_db"]))
            best["channels_seen"] = seen
            if confirmed:
                cal_confirmed = (sig, best)
            else:
                cal_unconfirmed = (sig, best)

    out = []
    span = None
    if hop or cal_confirmed:
        hopping = bool(hop) or bool(cal_confirmed and cal_confirmed[0].get("hopping"))
        kind = f"Frequency-hopping video link ({band})" if hopping else f"Drone video link ({band})"
        if hop:
            det = rf.cluster_detection(band, hop["cluster"], kind, 0.85, "hopping")
            det["channels_seen"] = hop["channels_mhz"]
        else:
            det = dict(cal_confirmed[1], drone_type=kind)
        if cal_confirmed:
            sig = cal_confirmed[0]
            det["drone_type"] = f"{kind} - matches calibrated '{sig['name']}'"
            det["confidence"] = max(det["confidence"], float(sig.get("confidence", 0.85)))
            det["signature"] = sig["name"]
            det["channels_seen"] = sorted(set(det.get("channels_seen", [])) | set(cal_confirmed[1]["channels_seen"]))
        det["threat_level"] = rf.threat_level(det["confidence"])
        det["track_key"] = f"link:{band}"   # one entry however much it hops
        out.append(det)
        chans = det.get("channels_seen") or [det["frequency_mhz"]]
        span = (min(chans) - 12.0, max(chans) + 12.0)
        state.link_span, state.link_span_ttl = span, LINK_SPAN_MEMORY_SWEEPS
    elif state.link_span_ttl > 0:
        # Hopping link seen recently but not confirmed this sweep: its
        # fragments still mustn't show up as separate "analog" signals.
        span = state.link_span
        state.link_span_ttl -= 1
    # A single-channel calibrated sighting (not yet seen hopping) isn't
    # listed - live, these fired on ordinary 2.4GHz traffic with the drone off.

    for d in dets:
        if d["method"] != "shape" or d["confidence"] < MIN_SHAPE_CONFIDENCE:
            continue
        if span and span[0] <= d["frequency_mhz"] <= span[1]:
            continue  # a fragment of the hopping link already reported
        out.append(d)

    # Keep learning what's normal - but never from a sweep with a
    # detection in it, so a drone can't become "background".
    if state.learning or (not out and state.link_span_ttl == 0):
        state.background.update(clusters)
    return out


def scanning_loop():
    global latest_spectrum
    analyzer = None
    if MODULATION_ANALYSIS_AVAILABLE:
        try:
            analyzer = create_spectrum_analyzer(sample_rate=rf.SAMPLE_RATE_HZ)
        except Exception as e:
            print(f"Modulation analyzer unavailable ({e}) - continuing without it")

    states = {band: BandState(LEARN_SWEEPS) for band in SWEEP_BANDS}
    learning_announced = False
    while True:
        try:
            t0 = time.time()
            spectra, found = {}, []
            for band in SWEEP_BANDS:
                result = rf.sweep_band(receiver, band)
                spectra[band] = rf.spectrum_summary(result)
                dets, clusters = rf.detections_for_band(result, signatures, analyzer)
                st = states[band]
                found.extend(fuse_band(band, dets, clusters, st))
                spectra[band]["background"] = {
                    "learning": st.learning,
                    "sweeps": min(st.background.sweeps, st.learn_sweeps),
                    "learn_sweeps": st.learn_sweeps,
                    "busy_channels_mhz": st.background.busy_channels_mhz(),
                }
            if not learning_announced and not any(st.learning for st in states.values()):
                learning_announced = True
                print("Background learned - hopping detection is now active.")

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
                sig = next((x for x in signatures if x["name"] == det.get("signature")), None)
                det["estimated_distance_m"] = rf.estimate_distance_m(det["above_noise_db"], sig)
                if not record_detection(det):
                    continue
                broadcast({"type": "detection", "data": public(det)})
                if det["threat_level"] == "high":
                    alert = {
                        "title": "Drone detected",
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

            end_lost_tracks()
            broadcast({"type": "tracks", "data": current_tracks()})
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


@app.get("/api/tracks")
def api_tracks():
    return {"success": True, "data": {"items": current_tracks()}}


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
    ap.add_argument("--learn-sweeps", type=int, default=20,
                    help="sweeps spent learning the background at startup, drones off (default 20, ~25s)")
    ap.add_argument("--amp", action="store_true",
                    help="enable the HackRF's +14dB front-end amp (helps weak 5.8GHz signals; "
                         "can overload near strong WiFi)")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    SWEEP_BANDS = [b + "GHz" for b in args.bands]
    LEARN_SWEEPS = args.learn_sweeps
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
    print(f"Learning the background for the first {LEARN_SWEEPS} sweeps - keep drones switched OFF until "
          f"it says 'Background learned'.")
    print("Dashboard: http://localhost:8000")
    print("WebSocket: ws://localhost:8082/ws")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        receiver.close(pyhackrf)
