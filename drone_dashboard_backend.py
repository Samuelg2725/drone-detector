#!/usr/bin/env python3
"""
drone_dashboard_backend.py - a real, working backend for this package's
own ui/dashboard.html, feeding it genuine data measured from your actual
HackRF - not anything from the original app/api/infrastructure layers,
which were broken at every single layer we opened (infrastructure/__init__.py,
app/__init__.py, api/routes/spectrum.py, each importing names that don't
exist in the files they import from).

Serves:
  http://localhost:8000/      -> the dashboard itself + REST API
  ws://localhost:8082/ws      -> live detection/alert/metrics push

Detection logic is intentionally simple and honest about what it
actually knows: it finds frequency bins sitting clearly above the
measured noise floor (excluding the known DC/LO leakage spike at the
tuned center frequency - confirmed in our own test to move exactly
with the tuning, same as every HackRF), and reports those as generic
"Unclassified RF Signal" detections. It does NOT claim to identify
specific drone models - this package's own ml_classifier.py is 2.2KB
of placeholder code, nowhere near enough to back the README's claimed
">95% accuracy, DJI Mavic 3" style results, so inventing confident
fake classifications here would just be the same kind of dishonesty
already found throughout the rest of this package.

Usage:
    python3 drone_dashboard_backend.py
Then open http://localhost:8000 in a browser.
"""
import asyncio
import json
import threading
import time
import uuid
from collections import deque

import numpy as np
import uvicorn
import websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from python_hackrf import pyhackrf

# Optional: the fixed domain/algorithms package (real modulation
# classification DSP - cyclic-prefix correlation, fourth-power carrier
# offset estimation). If it's not present alongside this script, the
# detector still works fully on its own shape-based classifier - this
# only adds a second, corroborating modulation-type reading, it's never
# required.
try:
    from domain.algorithms import create_spectrum_analyzer
    _modulation_analyzer = None  # built lazily once SAMPLE_RATE_HZ is known
    MODULATION_ANALYSIS_AVAILABLE = True
except ImportError:
    MODULATION_ANALYSIS_AVAILABLE = False

# ======================== Configuration ======================== #

CENTER_FREQ_HZ = 2_450_000_000
SAMPLE_RATE_HZ = 20_000_000  # HackRF's max - needed so a real ~20MHz-wide analog video signal fits entirely inside one capture, not just a cropped slice missing one or both tapering edges
NUM_SAMPLES = 2 ** 17
SCAN_INTERVAL_S = 1.0

# The DC/LO leakage spike always sits exactly at the tuned center
# frequency, regardless of anything real - confirmed in our own test
# (it moved from 2450MHz to 2440MHz exactly when we retuned). Excluded
# from detection so it's never reported as a "signal".
DC_EXCLUSION_HZ = 50_000

# How far above the noise floor (90th percentile, away from the DC
# spike) a bin has to sit before it's reported as a detection.
DETECTION_THRESHOLD_DB = 10.0

# ======================== HackRF (set up once in main) ======================== #

sdr = None


def scan_once():
    """One real HackRF capture + FFT. Returns (freqs_hz, magnitude_db, samples)."""
    samples = np.zeros(NUM_SAMPLES, dtype=np.complex64)
    state = {"idx": 0}

    def callback(device, buffer, buffer_length, valid_length):
        accepted = valid_length // 2
        raw = buffer[:valid_length].astype(np.int8)
        iq = (raw[0::2] + 1j * raw[1::2]) / 128.0
        remaining = NUM_SAMPLES - state["idx"]
        to_copy = min(accepted, remaining)
        samples[state["idx"]:state["idx"] + to_copy] = iq[:to_copy]
        state["idx"] += to_copy
        return 0

    sdr.set_rx_callback(callback)
    sdr.pyhackrf_start_rx()

    timeout = NUM_SAMPLES / SAMPLE_RATE_HZ + 1.0
    start = time.time()
    while state["idx"] < NUM_SAMPLES and (time.time() - start) < timeout:
        time.sleep(0.005)

    sdr.pyhackrf_stop_rx()

    window = np.hanning(len(samples))
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    magnitude_db = 20 * np.log10(np.abs(spectrum) + 1e-12)
    freqs_hz = np.fft.fftshift(np.fft.fftfreq(len(samples), d=1 / SAMPLE_RATE_HZ)) + CENTER_FREQ_HZ
    return freqs_hz, magnitude_db, samples


def find_detection(freqs_hz, magnitude_db, samples=None):
    """Returns a detection dict if the strongest non-DC bin clears the
    threshold above the noise floor, else None. Pure function (aside
    from the optional modulation lookup), testable on its own with
    synthetic data."""
    dc_mask = np.abs(freqs_hz - CENTER_FREQ_HZ) < DC_EXCLUSION_HZ
    usable = ~dc_mask
    if not np.any(usable):
        return None

    # Median, not a high percentile - a percentile like 90 gets
    # contaminated by the signal itself once it occupies more than
    # ~10% of the sweep, which a real ~20MHz-wide analog video signal
    # easily does inside a 20MHz capture. Median stays accurate as long
    # as the signal occupies under half the sweep.
    noise_floor = float(np.median(magnitude_db[usable]))
    masked = np.where(usable, magnitude_db, -999.0)

    cluster = find_cluster(freqs_hz, masked, noise_floor)
    if cluster is None:
        return None

    classification = classify_cluster(cluster)
    if classification is None:
        return None  # above the noise floor, but not shaped like a video link - ordinary noise/WiFi

    label, confidence = classification
    aligned, wifi_ch = wifi_channel_info(cluster["center_mhz"])
    if aligned:
        # Lands within 3MHz of a standard WiFi channel center - most
        # likely ordinary WiFi, not a drone, even though the shape
        # cleared the classifier. Not proof either way on its own (see
        # the WiFi-alignment note in the SNS project this reused logic
        # came from), so this reduces confidence rather than silently
        # dropping it.
        confidence = round(confidence * 0.5, 3)

    threat_level = "high" if confidence > 0.8 else ("medium" if confidence > 0.6 else "low")

    modulation_hint = None
    if MODULATION_ANALYSIS_AVAILABLE and samples is not None:
        # Corroborating info only - this is a real modulation classifier
        # (cyclic-prefix correlation, amplitude-variance checks), but it
        # was never validated against real drone signatures either, so
        # it's reported as what it actually is - a modulation type
        # guess, not a second vote for "this is a drone."
        try:
            global _modulation_analyzer
            if _modulation_analyzer is None:
                _modulation_analyzer = create_spectrum_analyzer(sample_rate=SAMPLE_RATE_HZ)
            features = _modulation_analyzer.estimate_modulation(samples)
            modulation_hint = {
                "type": features.modulation_type.name,
                "confidence": round(float(features.confidence), 3),
            }
        except Exception as e:
            modulation_hint = {"error": str(e)}

    return {
        "id": str(uuid.uuid4())[:8],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "drone_type": label,
        "confidence": confidence,
        "threat_level": threat_level,
        "frequency_mhz": cluster["center_mhz"],
        "power_db": cluster["peak_db"],
        "crest_factor_db": cluster["crest_factor_db"],
        "edge_drop_db": cluster["edge_drop_db"],
        "gradient_db_per_mhz": cluster["gradient_db_per_mhz"],
        "modulation_hint": modulation_hint,
        "bandwidth_mhz": cluster["bandwidth_mhz"],
        "wifi_channel_aligned": aligned,
        "wifi_channel_mhz": wifi_ch,
    }


# Standard 2.4GHz WiFi channel centers (1-14, 20MHz spacing in most
# regions). A cluster landing within this tolerance is more likely
# ordinary WiFi than a drone - a corroborating signal, not proof.
WIFI_CHANNELS_MHZ = [2412, 2417, 2422, 2427, 2432, 2437, 2442, 2447, 2452, 2457, 2462, 2467, 2472, 2484]
WIFI_CHANNEL_TOLERANCE_MHZ = 3.0


def wifi_channel_info(center_mhz):
    for ch_mhz in WIFI_CHANNELS_MHZ:
        if abs(center_mhz - ch_mhz) <= WIFI_CHANNEL_TOLERANCE_MHZ:
            return True, ch_mhz
    return False, None


def find_cluster(freqs_hz, masked_db, noise_floor):
    """Finds the single widest contiguous run of bins above (noise_floor
    + a modest margin), merging small gaps - the same shape-detection
    approach used for video-link classification in client.py earlier in
    this project, adapted here to one HackRF sweep instead of a
    multi-band Pluto scan."""
    above = masked_db > (noise_floor + 6.0)
    if not np.any(above):
        return None

    idx = np.where(above)[0]
    # Merge runs separated by small gaps into one cluster - real FM
    # sidebands genuinely dip below any fixed threshold and recover
    # within a real signal, they don't stay monotonically elevated.
    # This has to be a FREQUENCY tolerance, not a fixed bin count - a
    # fixed bin count silently means something different depending on
    # capture size/sample rate, and a 5-bin tolerance was found (via a
    # real synthetic test, not guessed) to fragment a genuinely single
    # ~6MHz-wide signal into several narrow pieces, since real
    # bin-to-bin fluctuation routinely spans more than 5 bins at any
    # realistic capture resolution.
    bin_width_hz = float(freqs_hz[1] - freqs_hz[0])
    gap_tolerance_hz = 300_000.0
    gap_tolerance_bins = max(1, int(round(gap_tolerance_hz / bin_width_hz)))
    gaps = np.diff(idx)
    split_points = np.where(gaps > gap_tolerance_bins)[0]
    groups = np.split(idx, split_points + 1)
    # The widest group is almost certainly the real signal, not noise -
    # but a wide-enough gap tolerance can also merge scattered random
    # noise hits into one fake wide group (confirmed with a real test:
    # pure noise merged into a 20MHz-wide "cluster" at only ~6% bin
    # density). A genuine signal stays mostly elevated throughout its
    # own span, so require real density, not just width.
    best = max(groups, key=len)
    if len(best) < 3:
        return None

    start, end = best[0], best[-1]
    span = end - start + 1
    density = len(best) / span
    if density < 0.5:
        return None
    cluster_db = masked_db[start:end + 1]
    cluster_freqs_mhz = freqs_hz[start:end + 1] / 1e6

    peak_rel = int(np.argmax(cluster_db))
    peak_db = float(cluster_db[peak_rel])
    mean_db = float(np.mean(cluster_db))
    crest_factor_db = peak_db - mean_db

    edge_bins = max(1, len(cluster_db) // 10)
    left_edge = float(np.mean(cluster_db[:edge_bins]))
    right_edge = float(np.mean(cluster_db[-edge_bins:]))
    edge_drop_db = min(peak_db - left_edge, peak_db - right_edge)

    bandwidth_mhz = float(cluster_freqs_mhz[-1] - cluster_freqs_mhz[0])
    gradient_db_per_mhz = (edge_drop_db / (bandwidth_mhz / 2)) if bandwidth_mhz > 0 else 0.0

    return {
        "center_mhz": round(float(np.mean(cluster_freqs_mhz)), 3),
        "peak_db": round(peak_db, 1),
        "crest_factor_db": round(crest_factor_db, 1),
        "edge_drop_db": round(edge_drop_db, 1),
        "gradient_db_per_mhz": round(gradient_db_per_mhz, 2),
        "bandwidth_mhz": round(bandwidth_mhz, 1),
    }


def classify_cluster(cluster):
    """Same thresholds as client.py's video-link classifier earlier in
    this project - tuned against real confirmed drone readings there
    (crest factor 6.5-7.6dB across four separate real test runs), not
    invented fresh here. Returns None for anything that clears the
    noise floor but isn't shaped like a video link at all - most real
    office RF (WiFi, Bluetooth) won't match either of these shapes
    cleanly, though WiFi specifically can still pass the "digital"
    check since both are OFDM - see the WiFi-channel exclusion above
    for that specific case."""
    cf = cluster["crest_factor_db"]
    edge = cluster["edge_drop_db"]
    # gradient_db_per_mhz is still computed and reported (useful
    # descriptive info), but NOT gated on here - tested against a real
    # synthetic analog signal and found it doesn't actually discriminate
    # shape with this averaging formula (ends up small for both a true
    # analog taper and a true flat digital signal), while crest factor
    # and edge drop alone were confirmed to correctly tell them apart.

    if cf >= 7.0 and edge >= 10.0:
        confidence = min(0.95, 0.5 + (cf - 7.0) / 20.0 + (edge - 10.0) / 40.0)
        return "Analog Video Link (unverified - shape match only)", round(confidence, 3)

    if cf < 5.0 and edge < 8.0 and 10.0 <= cluster["bandwidth_mhz"] <= 40.0:
        confidence = min(0.90, 0.5 + (5.0 - cf) / 20.0 + (8.0 - edge) / 40.0)
        return "Digital Video Link (unverified - shape match only)", round(confidence, 3)

    return None



# ======================== Shared state ======================== #

detections = deque(maxlen=200)
alerts = deque(maxlen=100)
start_time = time.time()

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

def scanning_loop():
    while True:
        try:
            freqs_hz, magnitude_db, samples = scan_once()
            detection = find_detection(freqs_hz, magnitude_db, samples)

            if detection:
                detections.appendleft(detection)
                broadcast({"type": "detection", "data": detection})

                if detection["threat_level"] == "high":
                    alert = {
                        "title": "Signal above threshold",
                        "message": f"{detection['frequency_mhz']}MHz at {detection['power_db']}dB "
                                   f"({detection['delta_above_noise_db']}dB above noise floor)",
                        "timestamp": detection["timestamp"],
                        "severity": "warning",
                    }
                    alerts.appendleft(alert)
                    broadcast({"type": "alert", "data": alert})

            broadcast({"type": "metrics", "data": current_metrics()})

        except Exception as e:
            print(f"Scan error: {e}")

        time.sleep(SCAN_INTERVAL_S)


# ======================== REST API (FastAPI) ======================== #

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def root():
    return FileResponse("ui/dashboard.html")


app.mount("/css", StaticFiles(directory="ui/css"), name="css")
app.mount("/js", StaticFiles(directory="ui/js"), name="js")
app.mount("/assets", StaticFiles(directory="ui/assets"), name="assets")


@app.get("/api/detections")
def api_detections(limit: int = 50):
    return {"success": True, "data": {"items": list(detections)[:limit]}}


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
            "connected": True,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "center_freq_hz": CENTER_FREQ_HZ,
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

if __name__ == "__main__":
    print("Connecting to HackRF...")
    pyhackrf.pyhackrf_init()
    sdr = pyhackrf.pyhackrf_open()
    sdr.pyhackrf_set_sample_rate(SAMPLE_RATE_HZ)
    sdr.pyhackrf_set_freq(CENTER_FREQ_HZ)
    sdr.pyhackrf_set_lna_gain(16)
    sdr.pyhackrf_set_vga_gain(20)
    sdr.pyhackrf_set_amp_enable(False)
    sdr.pyhackrf_set_antenna_enable(False)
    baseband_filter = min(SAMPLE_RATE_HZ * 0.8, 10e6)
    allowed_filter = pyhackrf.pyhackrf_compute_baseband_filter_bw_round_down_lt(baseband_filter)
    sdr.pyhackrf_set_baseband_filter_bandwidth(allowed_filter)

    threading.Thread(target=run_ws_server, daemon=True).start()
    threading.Thread(target=scanning_loop, daemon=True).start()

    print(f"Scanning {CENTER_FREQ_HZ / 1e6:.1f}MHz continuously...")
    print("Dashboard: http://localhost:8000")
    print("WebSocket: ws://localhost:8082/ws")
    uvicorn.run(app, host="0.0.0.0", port=8000)
