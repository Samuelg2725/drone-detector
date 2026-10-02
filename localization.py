#!/usr/bin/env python3
"""
localization.py - estimate where a drone is from how strongly several
sensors hear it (RSSI / "received signal strength" positioning).

Each sensor reports how far the drone's signal is above its noise floor.
Signal strength falls with distance roughly as

    level_dB = P0 - 10 * n * log10(distance)

where P0 is the drone's (unknown) transmit level and n is the path-loss
exponent (~2 open air, 2.5-3 around buildings). With 3+ sensors we search
a grid over the site for the point (and P0) that best explains every
sensor's level at once. With 2 sensors, or when the fit is poor, it falls
back to a signal-weighted centroid.

What this can and can't do - honestly:
  * It always tells you the NEAREST sensor reliably (loudest one).
  * Position accuracy is limited by how much signal strength wobbles
    (walls, drone orientation, multipath): typically several dB, which
    means tens of metres of error with sensors ~100-200m apart.
    simulate_sensors.py measures this for a given layout and noise level.
  * The uncertainty radius returned is how far the "almost as good" fits
    spread - a guide, not a guarantee.
  * Precise positions need time-difference-of-arrival (TDOA: GPS-
    disciplined, time-synced receivers) or the drone broadcasting its own
    GPS (Remote ID / DJI DroneID).
"""
import math

import numpy as np

PATH_LOSS_EXPONENT = 2.5
GRID_STEP_M = 3.0
SEARCH_MARGIN_M = 150.0
EARTH_RADIUS_M = 6_371_000.0


def to_local(lat, lon, lat0, lon0):
    """Lat/lon -> metres east/north of (lat0, lon0). Fine over a few km."""
    x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return x, y


def to_latlon(x, y, lat0, lon0):
    lat = lat0 + math.degrees(y / EARTH_RADIUS_M)
    lon = lon0 + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
    return lat, lon


def _sse_grid(gx, gy, xy, lv, n):
    X, Y = np.meshgrid(gx, gy)
    d = np.maximum(np.sqrt((X[..., None] - xy[:, 0]) ** 2 + (Y[..., None] - xy[:, 1]) ** 2), 1.0)
    model = -10 * n * np.log10(d)                         # level minus P0
    p0 = np.mean(lv - model, axis=-1, keepdims=True)      # best P0 per point
    return X, Y, np.sum((lv - (p0 + model)) ** 2, axis=-1)


def locate(readings, n=PATH_LOSS_EXPONENT):
    """readings: list of {"sensor_id", "lat", "lon", "level_db"} (level =
    dB above that sensor's noise floor; higher = closer).

    Returns {"lat", "lon", "uncertainty_m", "method", "nearest_sensor",
    "sensors_used"} or None if no reading has a position."""
    pts = [r for r in readings if r.get("lat") is not None and r.get("lon") is not None]
    if not pts:
        return None
    nearest = max(pts, key=lambda r: r["level_db"])
    lat0 = float(np.mean([r["lat"] for r in pts]))
    lon0 = float(np.mean([r["lon"] for r in pts]))
    xy = np.array([to_local(r["lat"], r["lon"], lat0, lon0) for r in pts])
    lv = np.array([r["level_db"] for r in pts], dtype=float)

    def result(x, y, unc, method):
        lat, lon = to_latlon(x, y, lat0, lon0)
        return {"lat": round(lat, 7), "lon": round(lon, 7), "uncertainty_m": round(float(unc), 1),
                "method": method, "nearest_sensor": nearest["sensor_id"], "sensors_used": len(pts)}

    if len(pts) == 1:
        # One sensor: we only know it's somewhere around that sensor.
        return result(xy[0, 0], xy[0, 1], 0.0, "single-sensor")

    # Weighted centroid: weights grow as the (implied) distance shrinks.
    w = 10 ** ((lv - lv.max()) / (10 * n))
    cx, cy = (xy * w[:, None]).sum(axis=0) / w.sum()
    spread = float(np.max(np.linalg.norm(xy - [cx, cy], axis=1)))
    if len(pts) == 2:
        return result(cx, cy, spread / 2, "weighted-centroid")

    # 3+ sensors: grid search minimising the squared error of the path-loss
    # model, with the drone's unknown transmit level P0 solved per point.
    # Coarse grid first, then a fine grid around the best few candidates -
    # close to a sensor the level changes so fast with distance that a
    # coarse point next to the truth can fit worse than a wrong far one.
    lo = xy.min(axis=0) - SEARCH_MARGIN_M
    hi = xy.max(axis=0) + SEARCH_MARGIN_M
    X, Y, sse = _sse_grid(np.arange(lo[0], hi[0], GRID_STEP_M), np.arange(lo[1], hi[1], GRID_STEP_M), xy, lv, n)
    best = (np.inf, 0.0, 0.0)
    for k in np.argsort(sse, axis=None)[:15]:
        cx0, cy0 = X.flat[k], Y.flat[k]
        fx, fy, fs = _sse_grid(np.arange(cx0 - 2 * GRID_STEP_M, cx0 + 2 * GRID_STEP_M, 0.25),
                               np.arange(cy0 - 2 * GRID_STEP_M, cy0 + 2 * GRID_STEP_M, 0.25), xy, lv, n)
        j = np.argmin(fs)
        if fs.flat[j] < best[0]:
            best = (float(fs.flat[j]), float(fx.flat[j]), float(fy.flat[j]))
    best, bx, by = best

    # Uncertainty: how far points whose fit is "nearly as good" spread
    # (within ~1 dB RMS per sensor of the best fit).
    near = sse <= best + len(pts) * 1.0
    unc = float(np.sqrt(np.max((X[near] - bx) ** 2 + (Y[near] - by) ** 2))) if near.any() else GRID_STEP_M
    return result(bx, by, max(unc, GRID_STEP_M), "rssi-multilateration")
