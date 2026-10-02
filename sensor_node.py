#!/usr/bin/env python3
"""
sensor_node.py - runs on each sensor (Raspberry Pi + HackRF) and reports
to the central server (drone_dashboard_backend.py).

Each sweep it sends: the sensor's position, its live spectrum (power per
frequency for every band) and any drone detections, including how strong
each one is - which is what lets the server work out which sensor is
nearest and estimate a rough position.

Needs only: numpy, python_hackrf (no web server on the Pi).

Usage:
    python3 sensor_node.py --id north-wall --lat 51.50720 --lon -0.12760 \\
                           --server http://192.168.1.50:8000
Copy rf_detector.py, detector_pipeline.py, control_link.py and (optionally)
drone_signatures.json onto the Pi next to this file.
"""
import argparse
import json
import time
import urllib.error
import urllib.request

import rf_detector as rf
from detector_pipeline import DetectorPipeline


def post(url, payload, timeout=5.0):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True, help="unique sensor name, e.g. north-wall")
    ap.add_argument("--lat", type=float, help="sensor latitude (or set it later by clicking the dashboard map)")
    ap.add_argument("--lon", type=float, help="sensor longitude")
    ap.add_argument("--server", required=True, help="central server URL, e.g. http://192.168.1.50:8000")
    ap.add_argument("--bands", nargs="+", choices=list(rf.BAND_ARGS), default=rf.DEFAULT_BAND_ARGS,
                    help="bands to sweep: 868 2.4 5.2 5.8 (default) or 5.8wide (5.645-5.925GHz)")
    ap.add_argument("--lna", type=int, default=16)
    ap.add_argument("--vga", type=int, default=20)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--learn-sweeps", type=int, default=20,
                    help="sweeps spent learning the background at startup, drones off (default 20)")
    args = ap.parse_args()

    from python_hackrf import pyhackrf
    url = f"{args.server.rstrip('/')}/api/sensors/{args.id}/report"
    bands = rf.bands_from_args(args.bands)
    print(f"[{args.id}] Connecting to HackRF...")
    receiver = rf.HackRFReceiver.open(pyhackrf, lna_gain=args.lna, vga_gain=args.vga, amp=args.amp)
    pipeline = DetectorPipeline(receiver, bands, rf.load_signatures(), args.learn_sweeps)
    print(f"[{args.id}] Reporting to {url}. Learning background for {args.learn_sweeps} sweeps - keep drones OFF.")

    failures = 0
    try:
        while True:
            try:
                report = pipeline.sweep()
            except Exception as e:
                print(f"[{args.id}] Scan error: {e}")
                report = {"error": str(e)}
            report.update({"lat": args.lat, "lon": args.lon})
            try:
                post(url, report)
                if failures:
                    print(f"[{args.id}] Server reachable again.")
                failures = 0
            except (urllib.error.URLError, OSError) as e:
                failures += 1
                if failures in (1, 10) or failures % 60 == 0:
                    print(f"[{args.id}] Can't reach server ({e}) - still sweeping, will keep retrying.")
            if report.get("detections"):
                print(f"[{args.id}] " + ", ".join(
                    f"{d['drone_type']} @ {d['frequency_mhz']}MHz +{d['above_noise_db']}dB"
                    for d in report["detections"]))
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close(pyhackrf)


if __name__ == "__main__":
    main()
