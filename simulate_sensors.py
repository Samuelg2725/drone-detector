#!/usr/bin/env python3
"""
simulate_sensors.py - test the multi-sensor setup and the positioning
("GPS") WITHOUT any hardware.

It places virtual sensors around a site, flies a virtual drone along a
known path, works out how strongly each sensor would hear it (path loss
+ random wobble, the same model localization.py assumes, plus extra
error it doesn't know about), and either:

  * sends those reports to a running dashboard (default) - watch the
    drone, the sensors and the position estimate move on the map, and
    get the real position error at every step, or
  * --offline: just measures position accuracy for a layout, no server.

Usage:
    python3 drone_dashboard_backend.py --no-local-sensor     # terminal 1
    python3 simulate_sensors.py --lat 51.5072 --lon -0.1276  # terminal 2
    python3 simulate_sensors.py --offline --layout perimeter8+centre --wobble-db 4

The honest test of real-world accuracy is a field test: fly a drone on a
known route (or hover it at marked spots), log its real GPS position, and
compare with what the dashboard estimated. This script is the dry run.
"""
import argparse
import json
import math
import time
import urllib.request

import numpy as np

import localization as L

LAYOUTS = {
    "corners4": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "corners4+centre": [(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)],
    "perimeter8": [(0, 0), (0.5, 0), (1, 0), (1, 0.5), (1, 1), (0.5, 1), (0, 1), (0, 0.5)],
    "perimeter8+centre": [(0, 0), (0.5, 0), (1, 0), (1, 0.5), (1, 1), (0.5, 1), (0, 1), (0, 0.5), (0.5, 0.5)],
}

DETECT_THRESHOLD_DB = 15.0   # the hopping detector needs ~15dB above noise


def sensor_positions(layout, size_m):
    return [(x * size_m - size_m / 2, y * size_m - size_m / 2) for x, y in LAYOUTS[layout]]


def drone_path(size_m, steps):
    """Flies in from outside the south-west, across the site, hovers over
    the middle (a drop), then leaves to the north-east."""
    pts = []
    a, b, c = (-size_m, -size_m * 0.8), (0.0, 0.0), (size_m, size_m * 0.9)
    n1 = steps * 2 // 5
    n2 = steps // 5
    n3 = steps - n1 - n2
    for i in range(n1):
        t = i / n1
        pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    pts += [b] * n2
    for i in range(n3):
        t = (i + 1) / n3
        pts.append((b[0] + (c[0] - b[0]) * t, b[1] + (c[1] - b[1]) * t))
    return pts


def levels_at(drone_xy, sensors_xy, level_at_1m, n_true, wobble_db, offsets, rng):
    out = []
    for (sx, sy), off in zip(sensors_xy, offsets):
        d = max(math.hypot(drone_xy[0] - sx, drone_xy[1] - sy), 1.0)
        out.append(level_at_1m - 10 * n_true * math.log10(d) + off + rng.normal(0, wobble_db))
    return out


def offline(args):
    rng = np.random.default_rng(args.seed)
    S = sensor_positions(args.layout, args.size_m)
    errs, nearest_ok, heard = [], 0, 0
    for _ in range(args.trials):
        tx, ty = rng.uniform(-args.size_m / 2, args.size_m / 2, 2)
        offsets = rng.normal(0, args.sensor_offset_db, len(S))
        lv = levels_at((tx, ty), S, args.level_at_1m, args.true_exponent, args.wobble_db, offsets, rng)
        rd = []
        for i, ((sx, sy), level) in enumerate(zip(S, lv)):
            if level < DETECT_THRESHOLD_DB:
                continue
            lat, lon = L.to_latlon(sx, sy, args.lat, args.lon)
            rd.append({"sensor_id": i, "lat": lat, "lon": lon, "level_db": level})
        if not rd:
            continue
        heard += 1
        r = L.locate(rd)
        ex, ey = L.to_local(r["lat"], r["lon"], args.lat, args.lon)
        errs.append(math.hypot(ex - tx, ey - ty))
        true_nearest = int(np.argmin([math.hypot(tx - a, ty - b) for a, b in S]))
        nearest_ok += r["nearest_sensor"] == true_nearest
    print(f"Layout {args.layout}, {args.size_m:.0f}m site, {len(S)} sensors, "
          f"{args.wobble_db}dB wobble, {args.sensor_offset_db}dB per-sensor offset:")
    print(f"  drone heard by >=1 sensor in {heard}/{args.trials} random positions")
    if errs:
        print(f"  position error: median {np.median(errs):.0f}m, 90% within {np.percentile(errs, 90):.0f}m")
        print(f"  nearest sensor correct: {nearest_ok / len(errs):.0%}")


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5).read()


def online(args):
    rng = np.random.default_rng(args.seed)
    S = sensor_positions(args.layout, args.size_m)
    ids = [f"sim-{i + 1}" for i in range(len(S))]
    latlons = [L.to_latlon(x, y, args.lat, args.lon) for x, y in S]
    offsets = rng.normal(0, args.sensor_offset_db, len(S))
    path = drone_path(args.size_m, args.steps)
    base = args.server.rstrip("/")
    print(f"Simulating {len(S)} sensors ({args.layout}, {args.size_m:.0f}m site) -> {base}")
    errs, covered, side_ok = [], [], []
    for step, (dx, dy) in enumerate(path):
        lv = levels_at((dx, dy), S, args.level_at_1m, args.true_exponent, args.wobble_db, offsets, rng)
        for sid, (lat, lon), level in zip(ids, latlons, lv):
            dets = []
            if level >= DETECT_THRESHOLD_DB:
                dets.append({
                    "band": "2.4GHz", "drone_type": "Frequency-hopping video link (2.4GHz) [SIMULATED]",
                    "method": "hopping", "signature": None, "channel_mhz": None,
                    "confidence": 0.85, "threat_level": "high", "frequency_mhz": 2462.0,
                    "power_db": round(level - 20, 1), "above_noise_db": round(level, 1),
                    "bandwidth_mhz": 15.0, "crest_factor_db": 20.0, "edge_drop_db": 20.0,
                    "track_key": "link:2.4GHz", "channels_seen": [2452.0, 2457.0, 2462.0, 2467.0],
                })
            post(f"{base}/api/sensors/{sid}/report",
                 {"lat": lat, "lon": lon, "sweep_number": step + 1, "sweep_seconds": args.interval,
                  "learning": False, "detections": dets})
        time.sleep(args.interval)
        tracks = [t for t in get_json(f"{base}/api/tracks")["data"]["items"] if t["status"] == "active"]
        heard = sum(level >= DETECT_THRESHOLD_DB for level in lv)
        t = tracks[0] if tracks else None
        p = t.get("position") if t else None
        inside_true = abs(dx) <= args.size_m / 2 and abs(dy) <= args.size_m / 2
        if p and p["method"].startswith("single-sensor"):
            print(f"step {step + 1:3d}: drone at ({dx:6.0f},{dy:6.0f})m, heard by {heard} sensor(s) - only "
                  f"{t['nearest_sensor']} hears it: position unknown")
        elif p and p["method"].startswith("outside-perimeter"):
            print(f"step {step + 1:3d}: drone at ({dx:6.0f},{dy:6.0f})m, heard by {heard} sensor(s) - "
                  f"OUTSIDE perimeter to the {p['bearing']} (really {'inside' if inside_true else 'outside'}), "
                  f"nearest {t['nearest_sensor']}, {t['trend']}")
        elif p:
            ex, ey = L.to_local(p["lat"], p["lon"], args.lat, args.lon)
            err = math.hypot(ex - dx, ey - dy)
            errs.append(err)
            covered.append(err <= (p["uncertainty_m"] or 0))
            side_ok.append(p.get("inside_perimeter") == inside_true)
            print(f"step {step + 1:3d}: drone at ({dx:6.0f},{dy:6.0f})m, heard by {heard} sensor(s), "
                  f"estimate ({ex:6.0f},{ey:6.0f})m, error {err:5.0f}m (±{p['uncertainty_m']:.0f}m), "
                  f"{'inside' if p.get('inside_perimeter') else 'OUTSIDE'} {p['bearing']}, "
                  f"nearest {t['nearest_sensor']}, {t['trend']}")
        else:
            print(f"step {step + 1:3d}: drone at ({dx:6.0f},{dy:6.0f})m, heard by {heard} sensor(s) - no estimate")
    if errs:
        print(f"\nPosition error over the flight: median {np.median(errs):.0f}m, 90% within {np.percentile(errs, 90):.0f}m")
        print(f"True position inside the reported ± circle: {np.mean(covered):.0%} of fixes")
        print(f"Inside/outside the perimeter called correctly: {np.mean(side_ok):.0%} of fixes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--lat", type=float, default=51.5072, help="site centre latitude")
    ap.add_argument("--lon", type=float, default=-0.1276, help="site centre longitude")
    ap.add_argument("--layout", choices=list(LAYOUTS), default="perimeter8+centre")
    ap.add_argument("--size-m", type=float, default=200.0, help="site width/height in metres")
    ap.add_argument("--level-at-1m", type=float, default=75.0,
                    help="drone's level 1m from a sensor, dB above noise (sets detection range)")
    ap.add_argument("--true-exponent", type=float, default=2.7,
                    help="real path-loss exponent (the estimator assumes 2.5 - deliberately not the same)")
    ap.add_argument("--wobble-db", type=float, default=4.0, help="random level variation per reading")
    ap.add_argument("--sensor-offset-db", type=float, default=2.0,
                    help="fixed per-sensor gain error (antennas/cables differ)")
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between simulated sweeps")
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--offline", action="store_true", help="measure accuracy only, no server")
    args = ap.parse_args()
    offline(args) if args.offline else online(args)


if __name__ == "__main__":
    main()
