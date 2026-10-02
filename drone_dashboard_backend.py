#!/usr/bin/env python3
"""
drone_dashboard_backend.py - the central server + dashboard.

Any number of SENSORS (a HackRF on a Raspberry Pi running sensor_node.py,
or a HackRF plugged into this machine) report to it. Each report has the
sensor's position, its live spectrum (power per frequency) and what it
detected. The server:

  * merges the same drone seen by several sensors into one track,
    ACTIVE while it keeps being seen, GONE ~12s after it goes quiet
  * keeps each sensor's signal level for every drone, so it knows which
    sensor is NEAREST (loudest) and can estimate a rough position from
    the relative levels (see localization.py for how, and its limits)
  * pushes everything live to ui/dashboard.html

Usage:
    # Single machine with a HackRF plugged in (it is the "local" sensor):
    python3 drone_dashboard_backend.py
    # Central server only, sensors are Raspberry Pis running sensor_node.py:
    python3 drone_dashboard_backend.py --no-local-sensor
Then open http://localhost:8000 (or http://<server-ip>:8000).
"""
import argparse
import asyncio
import json
import os
import threading
import time
import uuid
from collections import deque

import numpy as np
import uvicorn
import websockets
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import localization
import rf_detector as rf
import site_baseline

# ======================== Configuration ======================== #

# A drone is ACTIVE while some sensor keeps seeing it; GONE once no sensor
# has for this long (a real drone recording never went more than one
# sweep without a match). A sighting after that starts a new track.
TRACK_TIMEOUT_S = 12.0
# A sensor is "online" if it reported within this long.
SENSOR_STALE_S = 15.0
# Per-sensor levels used for positioning: median of the last few reports
# within this window, which smooths the sweep-to-sweep wobble.
LEVEL_WINDOW_S = 4.0
LEVEL_HISTORY = 3

SENSORS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensors.json")

# ======================== Shared state ======================== #

lock = threading.RLock()
detections = deque(maxlen=200)   # tracks, newest first
alerts = deque(maxlen=100)
sensors = {}                     # sensor_id -> info dict
spectra = {}                     # sensor_id -> latest spectrum message
start_time = time.time()


def load_sensor_locations():
    try:
        with open(SENSORS_FILE) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Couldn't read {SENSORS_FILE}: {e}")
        return {}


saved_locations = load_sensor_locations()


def save_sensor_location(sensor_id, lat, lon):
    saved_locations[sensor_id] = {"lat": lat, "lon": lon}
    with open(SENSORS_FILE, "w") as fh:
        json.dump(saved_locations, fh, indent=2)


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


# ======================== Sensors ======================== #

def sensor_public(s, now=None):
    now = now or time.time()
    return {
        "sensor_id": s["sensor_id"],
        "lat": s.get("lat"),
        "lon": s.get("lon"),
        "online": (now - s["last_report"]) < SENSOR_STALE_S,
        "last_report_ago_s": int(now - s["last_report"]),
        "sweeps": s.get("sweeps", 0),
        "sweep_seconds": s.get("sweep_seconds"),
        "learning": s.get("learning", False),
        "bands": s.get("bands", []),
        "last_error": s.get("last_error"),
        "reports": s.get("reports", 0),
        "sdr": s.get("sdr"),
        "baseline": s.get("baseline"),
        "level_offset_db": s.get("level_offset_db", 0.0),
    }


def all_sensors():
    now = time.time()
    return [sensor_public(s, now) for s in sorted(sensors.values(), key=lambda s: s["sensor_id"])]


def sensor_position(sensor_id):
    s = sensors.get(sensor_id, {})
    return s.get("lat"), s.get("lon")


# ======================== Tracks ======================== #

def is_active(d, now=None):
    return ((now or time.time()) - d["_last_seen"]) <= TRACK_TIMEOUT_S


def record_detection(det, sensor_id):
    """Merge into the matching ACTIVE track (from any sensor), or start a
    new one. Returns the track and whether it is new."""
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
            for k in ("frequency_mhz", "power_db", "above_noise_db", "bandwidth_mhz"):
                d[k] = det[k]
            for k in ("reasons", "duty_cycle_pct", "airtime_pct", "persistence"):
                if k in det:
                    d[k] = det[k]
            if det.get("channels_seen"):
                d["channels_seen"] = det["channels_seen"]
            add_level(d, sensor_id, det, now)
            return d, False
    det.update({
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hits": 1,
        "_first_seen": now,
        "_last_seen": now,
        "_levels": {},
    })
    add_level(det, sensor_id, det, now)
    detections.appendleft(det)
    return det, True


def add_level(track, sensor_id, det, now):
    hist = track["_levels"].setdefault(sensor_id, deque(maxlen=LEVEL_HISTORY))
    # Per-sensor offset so a Pluto and a HackRF (or different antennas)
    # hearing the same drone at the same distance report the same level.
    offset = sensors.get(sensor_id, {}).get("level_offset_db", 0.0)
    hist.append((now, det["above_noise_db"] + offset, det.get("estimated_distance_m")))


def sensor_levels(track, now):
    """Each sensor's recent level for this track (median of recent reports)."""
    out = []
    for sid, hist in track["_levels"].items():
        recent = [h for h in hist if now - h[0] <= LEVEL_WINDOW_S]
        if not recent:
            continue
        levels = sorted(h[1] for h in recent)
        lat, lon = sensor_position(sid)
        out.append({
            "sensor_id": sid,
            "level_db": round(levels[len(levels) // 2], 1),
            "estimated_distance_m": recent[-1][2],
            "lat": lat, "lon": lon,
            "seen_ago_s": int(now - recent[-1][0]),
        })
    out.sort(key=lambda r: -r["level_db"])
    return out


def public(det):
    now = time.time()
    out = {k: v for k, v in det.items() if not k.startswith("_") and k != "track_key"}
    out["status"] = "active" if is_active(det, now) else "gone"
    out["duration_s"] = int(det["_last_seen"] - det["_first_seen"])
    out["seen_ago_s"] = int(now - det["_last_seen"])
    levels = det.get("_last_levels", [])
    out["sensor_levels"] = levels
    pos = det.get("_position")
    if pos:
        pos = {k: v for k, v in pos.items() if k != "candidates"}
    out["position"] = pos
    out["nearest_sensor"] = levels[0]["sensor_id"] if levels else None
    out["estimated_distance_m"] = levels[0]["estimated_distance_m"] if levels else None
    out["trend"] = det.get("_trend", "steady")
    if len(levels) > 1:
        out["reasons"] = list(out.get("reasons") or []) + [{
            "text": f"Heard by {len(levels)} sensors at once (loudest: {levels[0]['sensor_id']} "
                    f"+{levels[0]['level_db']} dB) - used for the position estimate", "effect": None}]
    out["trend_db_per_s"] = det.get("_trend_rate")
    return out


# Level trend (the "RSSI rises then falls" sign): slope of the loudest
# sensor's level over the last TREND_WINDOW_S.
TREND_WINDOW_S = 10.0
TREND_DB_PER_S = 0.8


def update_positions():
    """Once a second for every active track: per-sensor levels -> position
    fix -> tracker (speed-limited, ambiguity resolved by history) ->
    inside/outside the perimeter; plus the approaching/moving-away trend."""
    now = time.time()
    perimeter = [(s["lat"], s["lon"]) for s in sensors.values() if s.get("lat") is not None]
    for d in detections:
        if not is_active(d, now):
            continue
        levels = sensor_levels(d, now)
        if levels:
            d["_last_levels"] = levels
        hearing = {lv["sensor_id"] for lv in levels}
        silent = [(s["lat"], s["lon"]) for s in sensors.values()
                  if s.get("lat") is not None and s["sensor_id"] not in hearing
                  and now - s["last_report"] < SENSOR_STALE_S and not s.get("learning")
                  and (not s.get("bands") or d["band"] in s["bands"])]
        fix = localization.locate(levels, perimeter=perimeter, silent=silent) if levels else None
        tracker = d.setdefault("_tracker", localization.PositionTrack())
        pos = tracker.update(fix, now)
        if pos and pos["method"].endswith("+tracked"):
            res = localization.inside_perimeter(pos["lat"], pos["lon"], perimeter)
            if res:
                pos["inside_perimeter"], pos["bearing"] = res
        if pos:
            d["_position"] = pos

        hist = d.setdefault("_level_hist", deque(maxlen=30))
        if levels:
            hist.append((now, levels[0]["level_db"]))
        pts = [(t, lv) for t, lv in hist if now - t <= TREND_WINDOW_S]
        if len(pts) >= 5 and pts[-1][0] - pts[0][0] >= 4:
            rate = float(np.polyfit([t - pts[0][0] for t, _ in pts], [lv for _, lv in pts], 1)[0])
            d["_trend_rate"] = round(rate, 2)
            # Relative to the loudest sensor, not the site - so "rising" means
            # getting closer to whichever sensor hears it best.
            d["_trend"] = ("signal rising" if rate > TREND_DB_PER_S else
                           "signal falling" if rate < -TREND_DB_PER_S else "steady")


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
        "sensors_online": sum(1 for s in sensors.values() if now - s["last_report"] < SENSOR_STALE_S),
        "sensors_total": len(sensors),
        "system_uptime": now - start_time,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ======================== Signal log & video detections ======================== #

SIGNAL_LOG_MAX = 5000
VIDEO_MATCH_MHZ = 3.0          # same transmitter if centre within this
VIDEO_FORGET_S = 3600          # emitters not seen for an hour are dropped
signal_log = deque(maxlen=SIGNAL_LOG_MAX)
video_emitters = []            # newest activity first


def log_signals(sensor_id, report):
    """Every signal every sensor saw this sweep -> the Raw Data log, and
    wide ones -> the Video Detections list. Returns the new log entries."""
    now = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    entries = []
    for band, sp in (report.get("spectra") or {}).items():
        raw = sp.get("raw") or {}
        for c in raw.get("clusters", []):
            entries.append({
                "t": now, "timestamp": stamp, "sensor_id": sensor_id, "band": band,
                "frequency_mhz": c["peak_mhz"], "center_mhz": c["center_mhz"], "bandwidth_mhz": c["bandwidth_mhz"],
                "level_db": c["above_noise_db"], "power_db": c["peak_db"],
                "crest_factor_db": c["crest_factor_db"], "edge_drop_db": c["edge_drop_db"],
                "duty_cycle_pct": c.get("duty_cycle_pct"), "airtime_pct": c.get("airtime_pct"),
                "persistence": c.get("persistence"), "video_class": c.get("video_class"),
                "classified_as": c.get("classified_as"), "wifi_channel_mhz": c.get("wifi_channel_mhz"),
                "kind": c.get("video_class") or ("Narrowband" if c["bandwidth_mhz"] < 1 else "Signal"),
                "baseline_pct": c.get("baseline_occupancy_pct"),
            })
        for p in raw.get("packets", []):
            entries.append({
                "t": now, "timestamp": stamp, "sensor_id": sensor_id, "band": band,
                "frequency_mhz": p["frequency_mhz"], "center_mhz": p["frequency_mhz"],
                "bandwidth_mhz": round(p["bandwidth_khz"] / 1000, 3), "level_db": p["above_noise_db"],
                "power_db": None, "crest_factor_db": None, "edge_drop_db": None, "duty_cycle_pct": None,
                "airtime_pct": None, "persistence": None, "video_class": None, "classified_as": None,
                "wifi_channel_mhz": None, "kind": f"868 packet ({p['duration_ms']} ms)", "baseline_pct": None,
            })
    signal_log.extend(entries)
    for e in entries:
        if e["video_class"]:
            update_video(e)
    return entries


def update_video(e):
    for v in video_emitters:
        if (v["sensor_id"] == e["sensor_id"] and v["band"] == e["band"] and v["type"] == e["video_class"]
                and abs(v["center_mhz"] - e["center_mhz"]) <= VIDEO_MATCH_MHZ):
            v["detections"] += 1
            v["last_seen"], v["_last"] = e["timestamp"], e["t"]
            v["center_mhz"] = round(0.8 * v["center_mhz"] + 0.2 * e["center_mhz"], 3)
            v["max_level_db"] = max(v["max_level_db"], e["level_db"])
            for k in ("bandwidth_mhz", "level_db", "crest_factor_db", "edge_drop_db", "duty_cycle_pct",
                      "airtime_pct", "persistence", "wifi_channel_mhz"):
                v[k] = e[k]
            video_emitters.remove(v)
            video_emitters.insert(0, v)
            return
    video_emitters.insert(0, {
        "id": str(uuid.uuid4())[:8], "sensor_id": e["sensor_id"], "band": e["band"], "type": e["video_class"],
        "center_mhz": e["center_mhz"], "bandwidth_mhz": e["bandwidth_mhz"], "level_db": e["level_db"],
        "max_level_db": e["level_db"], "crest_factor_db": e["crest_factor_db"], "edge_drop_db": e["edge_drop_db"],
        "duty_cycle_pct": e["duty_cycle_pct"], "airtime_pct": e["airtime_pct"], "persistence": e["persistence"],
        "wifi_channel_mhz": e["wifi_channel_mhz"], "first_seen": e["timestamp"], "last_seen": e["timestamp"],
        "_last": e["t"], "detections": 1,
    })
    while len(video_emitters) > 500:
        video_emitters.pop()


def video_public():
    now = time.time()
    video_emitters[:] = [v for v in video_emitters if now - v["_last"] <= VIDEO_FORGET_S]
    return [dict({k: x for k, x in v.items() if not k.startswith("_")},
                 active=(now - v["_last"]) <= TRACK_TIMEOUT_S, seen_ago_s=int(now - v["_last"]))
            for v in video_emitters[:300]]


# ======================== Ingesting sensor reports ======================== #

def ingest_report(sensor_id, report):
    """One sweep's worth of results from one sensor."""
    with lock:
        s = sensors.setdefault(sensor_id, {"sensor_id": sensor_id, "reports": 0})
        saved = saved_locations.get(sensor_id, {})
        # Position: what the sensor says, else what was set on the dashboard.
        s["lat"] = report.get("lat") if report.get("lat") is not None else saved.get("lat", s.get("lat"))
        s["lon"] = report.get("lon") if report.get("lon") is not None else saved.get("lon", s.get("lon"))
        s["last_report"] = time.time()
        s["reports"] += 1
        s["sweeps"] = report.get("sweep_number", s.get("sweeps", 0))
        s["sweep_seconds"] = report.get("sweep_seconds") or s.get("sweep_seconds")
        s["learning"] = report.get("learning", False)
        s["last_error"] = report.get("error")
        s["sdr"] = report.get("sdr", s.get("sdr"))
        s["level_offset_db"] = float(report.get("level_offset_db") or 0.0)
        if report.get("baseline"):
            s["baseline"] = report["baseline"]
        if report.get("baseline_profile"):
            s["baseline_profile"] = report["baseline_profile"]
        if report.get("spectra"):
            # Sensors now send one band at a time - keep the latest of each.
            merged = spectra.setdefault(sensor_id, {"sensor_id": sensor_id, "bands": {}})
            merged["bands"].update(report["spectra"])
            merged.update(timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"), scan_number=s["sweeps"],
                          sweep_seconds=s["sweep_seconds"])
            s["bands"] = sorted(merged["bands"])
            broadcast({"type": "spectrum", "data": dict(merged, bands=report["spectra"])})

        entries = log_signals(sensor_id, report)
        if entries:
            broadcast({"type": "signals", "data": [{k: v for k, v in e.items() if k != "t"} for e in entries]})

        for det in report.get("detections", []):
            det = dict(det)
            track, new = record_detection(det, sensor_id)
            if not new:
                continue
            broadcast({"type": "detection", "data": public(track)})
            if track["threat_level"] == "high":
                alert = {
                    "title": "Drone detected",
                    "message": f"{track['drone_type']} at {track['frequency_mhz']}MHz ({track['band']}), "
                               f"+{track['above_noise_db']}dB at sensor '{sensor_id}'",
                    "timestamp": track["timestamp"],
                    "severity": "warning",
                }
                alerts.appendleft(alert)
                broadcast({"type": "alert", "data": alert})


def housekeeping_loop():
    """Once a second: end lost tracks, re-estimate positions, push state.
    Runs independently of any sensor so the dashboard stays live even if
    every sensor goes quiet."""
    while True:
        try:
            with lock:
                end_lost_tracks()
                update_positions()
                broadcast({"type": "tracks", "data": current_tracks()})
                broadcast({"type": "metrics", "data": current_metrics()})
                broadcast({"type": "sensors", "data": all_sensors()})
                broadcast({"type": "video", "data": video_public()})
        except Exception as e:
            print(f"Housekeeping error: {e}")
        time.sleep(1.0)


# ======================== Local sensor (HackRF on this machine) ======================== #

def local_sensor_loop(pipeline, sensor_id, lat, lon, args):
    announced = False
    last_print = 0
    found_this_cycle = []
    while True:
        try:
            report = pipeline.step()
            report.update({"lat": lat, "lon": lon, "sdr": args.sdr, "level_offset_db": args.level_offset_db})
            ingest_report(sensor_id, report)
            found_this_cycle += report["detections"]
            if not announced and not report["learning"]:
                announced = True
                print("Background learned - hopping detection is now active.")
            if not pipeline.schedule and report["sweep_number"] - last_print >= 5:
                last_print = report["sweep_number"]
                hits = ", ".join(sorted({f"{d['drone_type']} @ {round(d['frequency_mhz'])}MHz"
                                         for d in found_this_cycle})) or "none"
                active = [b for b, st_ in pipeline.states.items() if st_.active]
                print(f"Cycle #{report['sweep_number']} ({report['sweep_seconds']}s for all bands)"
                      + (f" | extra visits: {', '.join(active)}" if active else "") + f" | drone-shaped: {hits}")
            if not pipeline.schedule:
                found_this_cycle = []
        except Exception as e:
            print(f"Scan error: {e}")
            ingest_report(sensor_id, {"lat": lat, "lon": lon, "error": str(e)})
            time.sleep(0.5)


# ======================== REST API (FastAPI) ======================== #

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def root():
    return FileResponse("ui/dashboard.html")


for _name in ("css", "js", "assets"):
    if os.path.isdir(f"ui/{_name}"):
        app.mount(f"/{_name}", StaticFiles(directory=f"ui/{_name}"), name=_name)


@app.post("/api/sensors/{sensor_id}/report")
async def api_sensor_report(sensor_id: str, request: Request):
    """sensor_node.py posts one sweep's results here."""
    report = await request.json()
    ingest_report(sensor_id, report)
    return {"success": True}


@app.post("/api/sensors/{sensor_id}/location")
async def api_sensor_location(sensor_id: str, request: Request):
    """Set a sensor's position from the dashboard map (saved to sensors.json)."""
    body = await request.json()
    lat, lon = float(body["lat"]), float(body["lon"])
    with lock:
        save_sensor_location(sensor_id, lat, lon)
        if sensor_id in sensors:
            sensors[sensor_id]["lat"], sensors[sensor_id]["lon"] = lat, lon
    return {"success": True}


@app.get("/api/sensors")
def api_sensors():
    with lock:
        return {"success": True, "data": {"items": all_sensors()}}


@app.get("/api/spectrum")
def api_spectrum(sensor: str = None):
    with lock:
        if sensor is None and spectra:
            sensor = sorted(spectra)[0]
        data = spectra.get(sensor)
        return {"success": data is not None, "data": data, "sensors": sorted(spectra)}


@app.get("/api/signals")
def api_signals(limit: int = 2000):
    with lock:
        items = list(signal_log)[-limit:]
    return {"success": True, "data": {"items": [{k: v for k, v in e.items() if k != "t"} for e in reversed(items)]}}


@app.get("/api/video")
def api_video():
    with lock:
        return {"success": True, "data": {"items": video_public()}}


@app.post("/api/video/clear")
def api_video_clear():
    with lock:
        video_emitters.clear()
    return {"success": True}


@app.get("/api/baseline")
def api_baseline():
    with lock:
        return {"success": True, "data": {sid: {"status": s_.get("baseline"), "profile": s_.get("baseline_profile")}
                                          for sid, s_ in sensors.items()}}


@app.get("/api/tracks")
def api_tracks():
    with lock:
        return {"success": True, "data": {"items": current_tracks()}}


@app.get("/api/detections")
def api_detections(limit: int = 50):
    with lock:
        return {"success": True, "data": {"items": [public(d) for d in list(detections)[:limit]]}}


@app.get("/api/alerts")
def api_alerts(limit: int = 50, active: bool = False):
    return {"success": True, "data": {"items": list(alerts)[:limit]}}


@app.get("/api/system/metrics")
def api_metrics():
    with lock:
        return {"success": True, "data": current_metrics()}


@app.get("/api/hardware/status")
def api_hardware_status():
    with lock:
        sens = all_sensors()
    online = [s for s in sens if s["online"]]
    return {
        "success": True,
        "data": {
            "device_type": f"{len(sens)} HackRF sensor(s)",
            "connected": bool(online),
            "sensors": sens,
            "scans_ok": sum(s["sweeps"] for s in sens),
            "scans_failed": 0,
            "last_error": next((f"{s['sensor_id']}: {s['last_error']}" for s in sens if s["last_error"]), None),
            "sweep_seconds": online[0]["sweep_seconds"] if online else None,
            "sweep_ranges_mhz": {b: [rf.BANDS[b][0] / 1e6, rf.BANDS[b][1] / 1e6] for b in rf.BANDS},
            "calibrated_signatures": [sig["name"] for sig in rf.load_signatures()],
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
    ap = argparse.ArgumentParser(description="Drone detection central server + dashboard")
    ap.add_argument("--no-local-sensor", action="store_true",
                    help="don't use an SDR on this machine - only remote sensor_node.py sensors")
    ap.add_argument("--sensor-id", default="local", help="name of the local SDR sensor (default 'local')")
    ap.add_argument("--lat", type=float, help="local sensor latitude (or click the dashboard map)")
    ap.add_argument("--lon", type=float, help="local sensor longitude")
    ap.add_argument("--bands", nargs="+", choices=list(rf.BAND_ARGS), default=rf.DEFAULT_BAND_ARGS,
                    help="bands to sweep: 868 2.4 5.2 5.8 (default) or 5.8wide (5.645-5.925GHz)")
    rf.add_sdr_args(ap)
    site_baseline.add_args(ap)
    ap.add_argument("--learn-sweeps", type=int, default=20,
                    help="sweeps spent learning the background at startup, drones off (default 20, ~25s)")
    ap.add_argument("--port", type=int, default=8000)
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()

    threading.Thread(target=run_ws_server, daemon=True).start()
    threading.Thread(target=housekeeping_loop, daemon=True).start()

    receiver = None
    if not args.no_local_sensor:
        from detector_pipeline import DetectorPipeline
        analyzer = None
        try:
            from domain.algorithms import create_spectrum_analyzer
            analyzer = create_spectrum_analyzer(sample_rate=rf.SAMPLE_RATE_HZ)
        except Exception:
            pass  # optional extra - modulation hints only
        signatures = rf.load_signatures()
        bands = rf.bands_from_args(args.bands)
        print(f"Connecting to {args.sdr}...")
        receiver = rf.receiver_from_args(args)
        baseline, minutes = site_baseline.from_args(args, args.sensor_id, bands)
        pipeline = DetectorPipeline(receiver, bands, signatures, args.learn_sweeps, analyzer,
                                    band_reps=rf.band_reps_from_args(args), baseline=baseline,
                                    baseline_minutes=minutes)
        lat = args.lat if args.lat is not None else saved_locations.get(args.sensor_id, {}).get("lat")
        lon = args.lon if args.lon is not None else saved_locations.get(args.sensor_id, {}).get("lon")
        threading.Thread(target=local_sensor_loop, args=(pipeline, args.sensor_id, lat, lon, args),
                         daemon=True).start()
        for b in bands:
            lo, hi = rf.BANDS[b]
            print(f"Sweeping {b}: {lo / 1e6:.0f}-{hi / 1e6:.0f}MHz in {len(rf.plan_hops(lo, hi))} hops")
        if signatures:
            print(f"Loaded {len(signatures)} calibrated signature(s): " + ", ".join(s_["name"] for s_ in signatures))
        if pipeline.learning:
            print(f"Learning the background for the first {args.learn_sweeps} sweeps - keep drones switched OFF "
                  f"until it says 'Background learned'.")
    else:
        print("No local SDR - waiting for sensor_node.py reports.")

    print(f"Dashboard: http://localhost:{args.port}")
    print("Sensors report to: http://<this-machine's-IP>:%d/api/sensors/<id>/report" % args.port)
    try:
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
    finally:
        if receiver is not None:
            receiver.close()
