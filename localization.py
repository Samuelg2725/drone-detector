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


# Sensors that are online but DON'T hear the drone are evidence too: a
# position that predicts one of them should hear it clearly is penalised.
SILENT_THRESHOLD_DB = 15.0     # roughly the detection threshold
SILENT_MARGIN_DB = 3.0


def _sse_grid(gx, gy, xy, lv, n, silent_xy=None):
    X, Y = np.meshgrid(gx, gy)
    d = np.maximum(np.sqrt((X[..., None] - xy[:, 0]) ** 2 + (Y[..., None] - xy[:, 1]) ** 2), 1.0)
    model = -10 * n * np.log10(d)                         # level minus P0
    p0 = np.mean(lv - model, axis=-1, keepdims=True)      # best P0 per point
    sse = np.sum((lv - (p0 + model)) ** 2, axis=-1)
    if silent_xy is not None and len(silent_xy):
        ds = np.maximum(np.sqrt((X[..., None] - silent_xy[:, 0]) ** 2 + (Y[..., None] - silent_xy[:, 1]) ** 2), 1.0)
        predicted = p0 - 10 * n * np.log10(ds)
        excess = np.maximum(predicted - (SILENT_THRESHOLD_DB + SILENT_MARGIN_DB), 0.0)
        sse = sse + np.sum(excess ** 2, axis=-1)
    return X, Y, sse


COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
# A grid point "fits about as well" as the best one if its squared error
# is within this much per sensor (dB^2). Sets the reported +/- radius;
# chosen with simulate_sensors.py --offline so the true position falls
# inside the +/- about 2 times in 3 with ~4dB level wobble.
UNC_SSE_PER_SENSOR = 4.0
# Candidate positions kept for the tracker (alternative fits within this
# much per sensor of the best) - this is how the mirror ambiguity inside /
# outside a wall is resolved using where the drone just was.
CANDIDATE_SSE_PER_SENSOR = 6.0
CANDIDATE_MIN_SEPARATION_M = 25.0


def _hull(points):
    """Convex hull (monotone chain) of (x, y) points, counter-clockwise."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _inside(hull, x, y, margin=0.0):
    if len(hull) < 3:
        return None
    for (x1, y1), (x2, y2) in zip(hull, hull[1:] + hull[:1]):
        # signed distance to each edge (positive = inside for a CCW hull)
        ex, ey = x2 - x1, y2 - y1
        if (ex * (y - y1) - ey * (x - x1)) / (np.hypot(ex, ey) + 1e-9) < -margin:
            return False
    return True


def _bearing(x, y):
    return COMPASS[int(((np.degrees(np.arctan2(x, y)) + 360 + 22.5) % 360) // 45)]


def locate(readings, n=PATH_LOSS_EXPONENT, perimeter=None, silent=None):
    """readings: list of {"sensor_id", "lat", "lon", "level_db"} (level =
    dB above that sensor's noise floor; higher = closer).
    perimeter: optional [(lat, lon), ...] of ALL placed sensors - their
    outline is treated as the site perimeter.
    silent: optional [(lat, lon), ...] of online sensors that do NOT hear it.

    Returns {"lat", "lon", "uncertainty_m", "method", "nearest_sensor",
    "sensors_used", "inside_perimeter", "bearing", "at_search_edge",
    "candidates"} or None if no reading has a position."""
    pts = [r for r in readings if r.get("lat") is not None and r.get("lon") is not None]
    if not pts:
        return None
    perim = perimeter or [(r["lat"], r["lon"]) for r in pts]
    lat0 = float(np.mean([p[0] for p in perim]))
    lon0 = float(np.mean([p[1] for p in perim]))
    hull = _hull([to_local(la, lo, lat0, lon0) for la, lo in perim])
    nearest = max(pts, key=lambda r: r["level_db"])
    xy = np.array([to_local(r["lat"], r["lon"], lat0, lon0) for r in pts])
    lv = np.array([r["level_db"] for r in pts], dtype=float)
    sxy = np.array([to_local(la, lo, lat0, lon0) for la, lo in (silent or [])]).reshape(-1, 2)

    def result(x, y, unc, method, at_edge=False, candidates=()):
        lat, lon = to_latlon(x, y, lat0, lon0)
        inside = _inside(hull, x, y)
        return {"lat": round(lat, 7), "lon": round(lon, 7),
                "uncertainty_m": None if unc is None else round(float(unc), 1),
                "method": method, "nearest_sensor": nearest["sensor_id"], "sensors_used": len(pts),
                "inside_perimeter": False if at_edge else (None if inside is None else bool(inside)),
                "bearing": _bearing(x, y), "at_search_edge": bool(at_edge),
                "candidates": [dict(zip(("lat", "lon"), to_latlon(cx, cy, lat0, lon0)), sse=round(float(cs), 2))
                               for cs, cx, cy in candidates]}

    if len(pts) == 1:
        # One sensor: it's somewhere around that sensor - distance only.
        return result(xy[0, 0], xy[0, 1], None, "single-sensor")

    # Weighted centroid: weights grow as the (implied) distance shrinks.
    w = 10 ** ((lv - lv.max()) / (10 * n))
    cx, cy = (xy * w[:, None]).sum(axis=0) / w.sum()
    spread = float(np.max(np.linalg.norm(xy - [cx, cy], axis=1)))
    if len(pts) == 2:
        return result(cx, cy, spread / 2, "weighted-centroid")

    # 3+ sensors: grid search minimising the squared error of the path-loss
    # model, with the drone's unknown transmit level P0 solved per point.
    # Coarse grid first, then a fine grid around distinct candidates -
    # close to a sensor the level changes so fast with distance that a
    # coarse point next to the truth can fit worse than a wrong far one.
    lo = xy.min(axis=0) - SEARCH_MARGIN_M
    hi = xy.max(axis=0) + SEARCH_MARGIN_M
    X, Y, sse = _sse_grid(np.arange(lo[0], hi[0], GRID_STEP_M), np.arange(lo[1], hi[1], GRID_STEP_M), xy, lv, n, sxy)
    seeds = []
    for k in np.argsort(sse, axis=None)[:400]:
        px, py = X.flat[k], Y.flat[k]
        if all(np.hypot(px - sx, py - sy) >= CANDIDATE_MIN_SEPARATION_M for sx, sy in seeds):
            seeds.append((px, py))
        if len(seeds) >= 6:
            break
    refined = []
    for sx, sy in seeds:
        fx, fy, fs = _sse_grid(np.arange(sx - 2 * GRID_STEP_M, sx + 2 * GRID_STEP_M, 0.25),
                               np.arange(sy - 2 * GRID_STEP_M, sy + 2 * GRID_STEP_M, 0.25), xy, lv, n, sxy)
        j = np.argmin(fs)
        refined.append((float(fs.flat[j]), float(fx.flat[j]), float(fy.flat[j])))
    refined.sort()
    best, bx, by = refined[0]
    candidates = [c for c in refined if c[0] <= best + len(pts) * CANDIDATE_SSE_PER_SENSOR]

    # Uncertainty: how far points whose fit is about as good spread.
    near = sse <= best + len(pts) * UNC_SSE_PER_SENSOR
    unc = float(np.sqrt(np.max((X[near] - bx) ** 2 + (Y[near] - by) ** 2))) if near.any() else GRID_STEP_M

    # Best fit on the edge of the search area = "further out than we can
    # tell" - only the direction is meaningful, not the point.
    at_edge = (bx - lo[0] < 2 * GRID_STEP_M or hi[0] - bx < 2 * GRID_STEP_M or
               by - lo[1] < 2 * GRID_STEP_M or hi[1] - by < 2 * GRID_STEP_M)
    return result(bx, by, max(unc, GRID_STEP_M), "outside-perimeter" if at_edge else "rssi-multilateration",
                  at_edge, candidates)


def inside_perimeter(lat, lon, perimeter):
    """True/False if (lat, lon) is inside the outline of the perimeter
    points (all placed sensors), None if fewer than 3."""
    if not perimeter or len(perimeter) < 3:
        return None
    lat0 = float(np.mean([p[0] for p in perimeter]))
    lon0 = float(np.mean([p[1] for p in perimeter]))
    hull = _hull([to_local(la, lo, lat0, lon0) for la, lo in perimeter])
    x, y = to_local(lat, lon, lat0, lon0)
    inside = _inside(hull, x, y)
    return (None if inside is None else bool(inside)), _bearing(x, y)


# ======================== Tracking over time ======================== #

MAX_SPEED_MS = 40.0        # fast FPV drones; nothing real moves faster
SMOOTHING = 0.8            # 1 = use each new fix as-is; lower = smoother but laggier
JUMP_SLACK_M = 15.0


class PositionTrack:
    """Light smoothing of one drone's position fixes over time.

    Each fix offers the best-fitting position plus any near-equal
    alternatives. Normally the best fit is used. Only if it would need a
    physically impossible move (faster than MAX_SPEED_MS, beyond the fix's
    own +/-) and an alternative is consistent with where the drone was, is
    the alternative used instead. If nothing is consistent the best fit is
    accepted - so a wrong history can never lock the track in place.

    Measured with the simulated flights (6 flights, 9 sensors, 4dB wobble):
    a stronger filter (velocity prediction + hard speed clamp) made the
    median error WORSE (24m -> 32m) by locking onto the mirror position
    outside the wall; this lighter version keeps the error about the same
    and calls inside/outside correctly ~76% of the time instead of ~70%."""

    def __init__(self):
        self.origin = None
        self.x = None
        self.t = None

    def update(self, fix, t):
        if not fix or fix["method"] in ("single-sensor", "outside-perimeter"):
            return fix          # no usable point to track - show as is
        if self.origin is None:
            self.origin = (fix["lat"], fix["lon"])
        lat0, lon0 = self.origin
        cands = [(c.get("sse", 0.0), np.array(to_local(c["lat"], c["lon"], lat0, lon0)))
                 for c in (fix.get("candidates") or [fix])]
        unc = fix["uncertainty_m"] or 0.0
        z = cands[0][1]
        if self.x is None or t - self.t > 15:
            self.x = z
        else:
            limit = MAX_SPEED_MS * max(t - self.t, 0.2) + unc + JUMP_SLACK_M
            if np.linalg.norm(z - self.x) > limit:
                ok = [c for c in cands if np.linalg.norm(c[1] - self.x) <= limit]
                if ok:
                    z = min(ok, key=lambda c: c[0])[1]
            self.x = self.x + SMOOTHING * (z - self.x)
        self.t = t
        lat, lon = to_latlon(self.x[0], self.x[1], lat0, lon0)
        return dict(fix, lat=round(lat, 7), lon=round(lon, 7), method=fix["method"] + "+tracked")
