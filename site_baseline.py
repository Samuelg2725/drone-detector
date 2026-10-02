#!/usr/bin/env python3
"""
site_baseline.py - a long "what's normal here" profile for one sensor
(Chris's baseline-capture phase): record 5-15 minutes with no drones, and
for every 1MHz of every band keep

    average / peak level        how loud this frequency usually is
    level variance              steady (fixed link, AP) or jumping about
    occupancy %                 how often it is busy (>= 6dB above noise)
    burst length                how long it stays busy each time (s)
    on/off changes per minute   switching activity (hopping, bursty data)
    typical signal width        of signals centred here
    persistent                  busy >= 80% of the time (a fixed emitter)
    periodic                    busy on a regular cycle (beacons, meters...)

It never delays detection: it is built in the background while detecting
(automatically the first time, over 10 minutes, from moments when nothing
suspicious is going on), saved to site_baseline.json (per sensor) and
loaded automatically on every later start, which
  * replaces the ~25s background learning - detection starts at once,
  * marks signals on frequencies that are normally busy (a known fixed
    emitter here) or normally quiet (new) in each detection's reasons.

Re-record it when the site changes (new WiFi, new equipment). A drone must
NOT be flying while it records.
"""
import json
import os
import time

import numpy as np

import rf_detector as rf

BASELINE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_baseline.json")
BIN_HZ = 1_000_000
PERSISTENT_PCT = 80.0
QUIET_PCT = 2.0
PERIODIC_MIN_CORR = 0.5


class BandBaseline:
    def __init__(self, band):
        self.band = band
        lo, hi = rf.BANDS[band]
        self.lo_hz = lo
        self.nbins = int(np.ceil((hi - lo) / BIN_HZ))
        self.times = []
        self.levels = []           # per visit: per-MHz max level (dB, uncalibrated)
        self.rel = []              # per visit: per-MHz max dB above noise
        self.strong_peaks = []     # per visit: MHz bins holding a strong wide peak (what the hop detector watches)
        self.bw_sum = np.zeros(self.nbins)
        self.bw_n = np.zeros(self.nbins)

    def _per_mhz(self, freqs_hz, values):
        idx = ((freqs_hz - self.lo_hz) // BIN_HZ).astype(int)
        out = np.full(self.nbins, -np.inf)
        ok = (idx >= 0) & (idx < self.nbins)
        np.maximum.at(out, idx[ok], values[ok])
        return out

    def add(self, result, clusters, t=None):
        self.times.append(t if t is not None else time.time())
        self.levels.append(self._per_mhz(result["freqs_hz"], result["power_db"]))
        self.rel.append(self._per_mhz(result["freqs_hz"], result["power_db"] - result["noise_db"]))
        peaks = set()
        for c in clusters:
            i = int((c["center_mhz"] * 1e6 - self.lo_hz) // BIN_HZ)
            if 0 <= i < self.nbins:
                self.bw_sum[i] += c["bandwidth_mhz"]
                self.bw_n[i] += 1
            if rf.wide_strong([c]):
                j = int((c["peak_mhz"] * 1e6 - self.lo_hz) // BIN_HZ)
                if 0 <= j < self.nbins:
                    peaks.add(j)
        self.strong_peaks.append(sorted(peaks))

    def summary(self):
        n = len(self.times)
        if n < 5:
            return None
        lv = np.array(self.levels)
        busy = np.array(self.rel) > rf.OCCUPIED_DB
        dt = (self.times[-1] - self.times[0]) / max(n - 1, 1)
        bins = []
        for i in range(self.nbins):
            b = busy[:, i]
            occ = 100.0 * b.mean()
            runs, cur = [], 0
            for v in b:
                if v:
                    cur += 1
                elif cur:
                    runs.append(cur)
                    cur = 0
            if cur:
                runs.append(cur)
            changes = int(np.sum(b[1:] != b[:-1]))
            period = None
            if QUIET_PCT < occ < PERSISTENT_PCT and n >= 20:
                x = b.astype(float) - b.mean()
                ac = np.correlate(x, x, "full")[n - 1:]
                if ac[0] > 0:
                    ac = ac / ac[0]
                    lag = int(np.argmax(ac[2:n // 2])) + 2 if n // 2 > 3 else None
                    if lag and ac[lag] >= PERIODIC_MIN_CORR:
                        period = round(lag * dt, 1)
            strong = 100.0 * np.mean([i in p for p in self.strong_peaks])
            bins.append({
                "mhz": round((self.lo_hz + (i + 0.5) * BIN_HZ) / 1e6, 1),
                "avg_db": round(float(np.mean(lv[:, i])), 1),
                "peak_db": round(float(np.max(lv[:, i])), 1),
                "var_db": round(float(np.std(lv[:, i])), 1),
                "occupancy_pct": round(occ, 1),
                "strong_peak_pct": round(strong, 1),
                "mean_burst_s": round(float(np.mean(runs)) * dt, 1) if runs else 0.0,
                "max_burst_s": round(float(np.max(runs)) * dt, 1) if runs else 0.0,
                "changes_per_min": round(changes / max((self.times[-1] - self.times[0]) / 60, 1e-9), 1),
                "avg_bw_mhz": round(float(self.bw_sum[i] / self.bw_n[i]), 1) if self.bw_n[i] else None,
                "persistent": bool(occ >= PERSISTENT_PCT),
                "periodic_s": period,
            })
        return {"band": self.band, "visits": n, "seconds": round(self.times[-1] - self.times[0], 1),
                "seconds_per_visit": round(dt, 2), "bins": bins}


class SiteBaseline:
    """Recording, saving, loading and using one sensor's baseline."""

    def __init__(self, sensor_id, bands):
        self.sensor_id = sensor_id
        self.bands = [b for b in bands if b in rf.BANDS]
        self.recorders = {b: BandBaseline(b) for b in self.bands}
        self.profile = None        # band -> summary dict, once recorded/loaded
        self.recorded_at = None
        self._lookup = {}

    # ---- recording ----
    def add(self, band, result, clusters):
        if band in self.recorders:
            self.recorders[band].add(result, clusters)

    def finish(self, minutes):
        self.profile = {b: r.summary() for b, r in self.recorders.items() if r.summary()}
        self.recorded_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._index()
        self.save(minutes)

    # ---- persistence ----
    def save(self, minutes):
        try:
            with open(BASELINE_FILE) as fh:
                allp = json.load(fh)
        except (FileNotFoundError, ValueError):
            allp = {}
        allp[self.sensor_id] = {"recorded_at": self.recorded_at, "minutes": minutes, "bands": self.profile}
        with open(BASELINE_FILE, "w") as fh:
            json.dump(allp, fh)

    def load(self):
        try:
            with open(BASELINE_FILE) as fh:
                entry = json.load(fh).get(self.sensor_id)
        except (FileNotFoundError, ValueError):
            return False
        if not entry:
            return False
        self.profile = {b: p for b, p in entry["bands"].items() if b in self.bands}
        self.recorded_at = entry.get("recorded_at")
        self._index()
        return bool(self.profile)

    def _index(self):
        self._lookup = {b: {round(x["mhz"] - 0.5): x for x in p["bins"]} for b, p in (self.profile or {}).items()}

    # ---- use ----
    def occupancy(self, band, lo_mhz, hi_mhz):
        """Highest baseline occupancy % over a signal's core (middle half)."""
        table = self._lookup.get(band)
        if not table:
            return None
        w = hi_mhz - lo_mhz
        a, b = int(np.floor(lo_mhz + w * 0.25)), int(np.floor(hi_mhz - w * 0.25))
        vals = [table[m]["occupancy_pct"] for m in range(a, b + 1) if m in table]
        return max(vals) if vals else None

    def seed_background(self, band, model):
        """Prime the hopping detector's background with where strong wide
        signals normally sit - so it doesn't need the startup learning."""
        table = self._lookup.get(band)
        if not table:
            return False
        for m, x in table.items():
            if x["strong_peak_pct"] > 0:
                key = int(m // rf.BACKGROUND_BIN_MHZ)
                model.busy[key] = max(model.busy.get(key, 0.0), x["strong_peak_pct"] / 100.0)
        return True

    def emitters(self):
        """Persistent and periodic emitters, for the dashboard."""
        out = []
        for band, p in (self.profile or {}).items():
            for x in p["bins"]:
                if x["persistent"] or x["periodic_s"]:
                    out.append(dict(x, band=band))
        return out

    def public(self):
        if not self.profile:
            return None
        return {"recorded_at": self.recorded_at,
                "bands": {b: {k: v for k, v in p.items() if k != "bins"} for b, p in self.profile.items()},
                "emitters": self.emitters()}


AUTO_MINUTES = 10


def add_args(ap):
    ap.add_argument("--baseline-minutes", type=float, default=0,
                    help="(re)build the site baseline over this many minutes, in the background while detecting. "
                         f"Not needed normally: with no saved baseline one is built automatically ({AUTO_MINUTES} min)")
    ap.add_argument("--no-baseline", action="store_true", help="ignore any saved site baseline")


def from_args(args, sensor_id, bands):
    """(baseline or None, minutes to record) - prints what it's doing."""
    if args.no_baseline:
        return None, 0
    b = SiteBaseline(sensor_id, bands)
    loaded = b.load()
    if args.baseline_minutes > 0:
        print(f"Rebuilding the site baseline for '{sensor_id}' over {args.baseline_minutes:g} min in the background - "
              f"detection runs as normal meanwhile" + (" (using the previous baseline until then)." if loaded else "."))
        return b, args.baseline_minutes
    if loaded:
        print(f"Loaded site baseline for '{sensor_id}' recorded {b.recorded_at} - no startup learning needed.")
        return b, 0
    print(f"No site baseline for '{sensor_id}' yet - building one automatically over the next {AUTO_MINUTES} min "
          f"in the background. Detection works meanwhile; it's saved and loaded instantly on later starts.")
    return b, AUTO_MINUTES

