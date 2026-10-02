#!/usr/bin/env python3
"""
detector_pipeline.py - one full detection pass ("sweep") for ONE sensor:
sweep every band with the HackRF, find signals, and turn them into drone
detections. Shared by:
  * sensor_node.py              - runs on each Raspberry Pi + HackRF and
                                  reports to the central server
  * drone_dashboard_backend.py  - the central server/dashboard, which can
                                  also run a HackRF plugged into itself as
                                  a local sensor

Per band it keeps:
  * a learned background (WiFi etc.) - see rf_detector.BackgroundModel
  * the calibration-free frequency-hopping detector
  * trackers for calibrated signatures
"""
import time

import numpy as np

import control_link
import rf_detector as rf

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
        self.control = control_link.ControlLinkDetector()
        self.duty = rf.DutyTracker()
        self.active = False
        self.link_span = None        # (lo_mhz, hi_mhz) of the last hopping link
        self.link_span_ttl = 0       # sweeps left before that span is forgotten

    @property
    def learning(self):
        return self.background.sweeps < self.learn_sweeps


def fuse_band(band, dets, clusters, state, signatures=()):
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
    # Only the calibration-free hopping detector creates a detection. A
    # calibrated signature on its own used to be able to as well, but with
    # just 2 channels and no background check it fired on WiFi channels
    # 11-13 with no drone present (bursty, ~8% duty) - so now it can only
    # add a note to a link the hopping detector has already confirmed. And
    # no drone names in labels: the same kind of link is used by many drones.
    if hop:
        kind = f"Frequency-hopping video link ({band})"
        if True:
            det = rf.cluster_detection(band, hop["cluster"], kind, 0.85, "hopping")
            det["channels_seen"] = hop["channels_mhz"]
            det["reasons"] = [
                {"text": f"A strong (>= {rf.HOP_MIN_ABOVE_NOISE_DB:.0f} dB above noise), wide (>= {rf.HOP_MIN_BW_MHZ:.0f} MHz) "
                         f"signal was present in {hop['present']} of the last {hop['window']} sweeps", "effect": None},
                {"text": f"Its peak jumped between {len(hop['channels_mhz'])} frequencies that are normally quiet here: "
                         + ", ".join(f"{c:.0f}" for c in hop["channels_mhz"]) + " MHz", "effect": None},
                {"text": "A WiFi router stays on one channel; jumping between new channels is how this kind of "
                         "drone video link behaves", "effect": "85%"},
            ]
        if cal_confirmed:
            sig = cal_confirmed[0]
            det["confidence"] = 0.9
            det["reasons"].append(
                {"text": f"Its channels also match a hopping pattern calibrated earlier (seen on "
                         f"{len(cal_confirmed[1]['channels_seen'])} of the learned channels) - the same kind of link, "
                         "which doesn't prove it's the same drone", "effect": "+5%"})
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


# A control link and a video link count as "together" if seen by this
# sensor within this many seconds (bands are now visited one at a time).
CORRELATION_WINDOW_S = 5.0
# Adaptive priority: a band with something suspicious going on gets this
# many extra visits per cycle until it goes quiet - faster updates and
# better duty/hop measurements exactly where a drone might be.
ACTIVE_EXTRA_VISITS = 1


# ---- Dual-band correlation (Chris's F7 + F9) ----
# Many drone links use 2.4GHz and 5.xGHz at the same time. Each visit to a
# video band records its NEW activity: strong, wide signals that aren't
# where things normally are (learned background / site baseline). Then:
#   F7  co-appearance: of the recent cycles where either band had new
#       activity, in what fraction did BOTH?
#   F9  shared trend: when both are present, do their levels rise and
#       fall together (one moving transmitter)?
DUAL_PAIR_WINDOW_S = 3.0        # a 2.4 and a 5.x visit this close count as the same cycle
DUAL_HISTORY = 20               # recent cycles compared
DUAL_MIN_CYCLES = 6             # need this many cycles with activity before judging
F7_STEPS = [(0.95, 0.15), (0.80, 0.10), (0.60, 0.05)]
F9_STEPS = [(0.80, 0.10), (0.60, 0.07), (0.40, 0.03)]
DUAL_ONLY_MIN_F7 = 0.80         # F7 alone strong enough to report "dual-band activity"
DUAL_ONLY_CONF = 0.60           # ...but only ever medium: a new dual-band WiFi device could do it too


def new_activity_level(band, clusters, state, baseline):
    """Strongest NEW wide signal this visit (dB above noise), or None."""
    best = None
    for c in rf.wide_strong(clusters):
        if state.background.is_background(c["peak_mhz"]):
            continue
        bo = c.get("baseline_occupancy_pct")
        if bo is not None and bo > rf.BASELINE_COMMON_PCT:
            continue
        best = c["above_noise_db"] if best is None else max(best, c["above_noise_db"])
    return best


def dual_band_evidence(history, cycle_s=None):
    """history: band -> deque[(t, level or None)]. Returns a dict with F7/F9
    values and bonuses, or None if there isn't enough to judge."""
    low = [b for b in history if b.startswith("2.4")]
    highs = [b for b in history if rf.is_5ghz(b)]
    if not low or not highs:
        return None
    # Same cycle = within one cycle's time of each other (at least 3s), so a
    # slower sensor (e.g. a Pi, or many bands) still pairs its visits.
    window = max(DUAL_PAIR_WINDOW_S, 1.2 * (cycle_s or 0))
    best = None
    for hb in highs:
        pairs = []
        for t, lv in list(history[low[0]])[-DUAL_HISTORY:]:
            near = [(abs(t2 - t), lv2) for t2, lv2 in history[hb] if abs(t2 - t) <= window]
            if near:
                pairs.append((lv, min(near)[1]))
        either = [p for p in pairs if p[0] is not None or p[1] is not None]
        both = [p for p in pairs if p[0] is not None and p[1] is not None]
        if len(either) < DUAL_MIN_CYCLES:
            continue
        f7 = len(both) / len(either)
        r = None
        if len(both) >= 5:
            a, b = np.array([p[0] for p in both]), np.array([p[1] for p in both])
            if a.std() > 1.0 and b.std() > 1.0:          # levels must actually move to compare trends
                r = float(np.corrcoef(a, b)[0, 1])
        ev = {"band": hb, "f7": round(f7, 2), "cycles": len(either), "both": len(both),
              "f9": None if r is None else round(r, 2),
              "f7_bonus": next((bon for thr, bon in F7_STEPS if f7 >= thr), 0.0),
              "f9_bonus": next((bon for thr, bon in F9_STEPS if r is not None and r > thr), 0.0)}
        if best is None or ev["f7"] > best["f7"]:
            best = ev
    return best


def dual_band_reasons(ev, low_band="2.4GHz"):
    out = [{"text": f"New activity on both {low_band} and {ev['band']} in {ev['f7']:.0%} of the {ev['cycles']} recent "
                    f"cycles where either had any (F7 - many drone links use both bands at once)",
            "effect": f"+{ev['f7_bonus']:.0%}" if ev["f7_bonus"] else "no change"}]
    if ev["f9"] is not None:
        out.append({"text": f"Their signal levels move together (correlation {ev['f9']:+.2f}, F9 - like one moving "
                            "transmitter)", "effect": f"+{ev['f9_bonus']:.0%}" if ev["f9_bonus"] else "no change"})
    return out


class DetectorPipeline:
    def __init__(self, receiver, bands, signatures=(), learn_sweeps=20, analyzer=None, band_reps=None,
                 baseline=None, baseline_minutes=0):
        self.receiver = receiver
        self.bands = list(bands)
        self.signatures = list(signatures)
        self.analyzer = analyzer
        self.states = {b: BandState(learn_sweeps) for b in self.bands}
        self.band_reps = dict(band_reps or {})
        self.sweeps = 0                 # completed cycles over all bands
        self.schedule = []
        self.cycle_start = time.time()
        self.last_cycle_seconds = None
        self.recent = {}                # band -> (time, detections) for cross-band correlation
        from collections import deque
        self.dual = {b: deque(maxlen=DUAL_HISTORY * 3) for b in self.bands
                     if b.startswith("2.4") or rf.is_5ghz(b)}
        # Site baseline: record one now, or use a saved one.
        self.baseline = baseline
        self.just_recorded = False
        self.baseline_minutes = baseline_minutes
        self.recording_until = time.time() + baseline_minutes * 60 if baseline is not None and baseline_minutes else None
        if baseline is not None and self.recording_until is None and baseline.profile:
            self._use_baseline()

    def _use_baseline(self):
        """A saved baseline replaces the startup background learning."""
        for band, st in self.states.items():
            if self.baseline.seed_background(band, st.background) or band == control_link.CONTROL_BAND:
                st.background.sweeps = max(st.background.sweeps, st.learn_sweeps)

    @property
    def recording_baseline(self):
        return self.recording_until is not None

    def baseline_status(self):
        if self.baseline is None:
            return {"state": "off"}
        if self.recording_baseline:
            total = self.baseline_minutes * 60
            left = max(0.0, self.recording_until - time.time())
            return {"state": "recording", "progress_pct": round(100 * (1 - left / total), 1), "seconds_left": int(left)}
        if self.baseline.profile:
            return {"state": "loaded", "recorded_at": self.baseline.recorded_at}
        return {"state": "none"}

    @property
    def learning(self):
        return self.recording_baseline or any(st.learning for st in self.states.values())

    def _build_schedule(self):
        """One cycle's visit order. Bands with extra visits (manual
        --band-reps, or recent suspicious activity) are interleaved rather
        than visited back to back, so their updates are evenly spaced."""
        reps = {b: max(1, int(self.band_reps.get(b, 1))) + (ACTIVE_EXTRA_VISITS if self.states[b].active else 0)
                for b in self.bands}
        order = []
        for r in range(max(reps.values())):
            order += [b for b in self.bands if reps[b] > r]
        return order

    def step(self):
        """Visit ONE band and return its report straight away (so the
        dashboard updates band by band, not once per full cycle)."""
        if not self.schedule:
            if self.sweeps or self.last_cycle_seconds is not None:
                self.last_cycle_seconds = round(time.time() - self.cycle_start, 2)
            self.cycle_start = time.time()
            self.schedule = self._build_schedule()
        band = self.schedule.pop(0)
        if not self.schedule:
            self.sweeps += 1

        t0 = time.time()
        st = self.states[band]
        if band == control_link.CONTROL_BAND:
            summary, det = self.control_band(band, st)
            found = [det] if det else []
        else:
            result = rf.sweep_band(self.receiver, band)
            summary = rf.spectrum_summary(result)
            dets, clusters = rf.detections_for_band(result, self.signatures, self.analyzer, st.duty,
                                                    None if self.recording_baseline else self.baseline)
            if self.recording_baseline:
                self.baseline.add(band, result, clusters)
                dets = []
            summary["raw"] = rf.raw_view(result, clusters)
            found = fuse_band(band, dets, clusters, st, self.signatures)
            if band in self.dual and not self.recording_baseline and not st.learning:
                self.dual[band].append((time.time(), new_activity_level(band, clusters, st, self.baseline)))
                found = self.apply_dual_band(band, found, clusters)
            summary["background"] = {
                "learning": st.learning,
                "sweeps": min(st.background.sweeps, st.learn_sweeps),
                "learn_sweeps": st.learn_sweeps,
                "busy_channels_mhz": st.background.busy_channels_mhz(),
            }
            st.active = bool(found) or sum(bool(x) for x in st.hop.window) >= 2
        if band == control_link.CONTROL_BAND:
            st.active = bool(found) or sum(bool(x) for x in st.control.window) >= 3

        if self.recording_baseline:
            found = []
            if time.time() >= self.recording_until:
                self.baseline.finish(self.baseline_minutes)
                self.recording_until = None
                self.just_recorded = True
                self._use_baseline()
                print(f"Site baseline recorded ({self.baseline_minutes} min) and saved - detection is now active.")
        now = time.time()
        self.recent[band] = (now, [dict(d) for d in found])
        others = [d for b, (t, ds) in self.recent.items() if b != band and now - t <= CORRELATION_WINDOW_S for d in ds]
        correlate(found, others)
        for det in found:
            sig = next((x for x in self.signatures if x["name"] == det.get("signature")), None)
            det["estimated_distance_m"] = rf.estimate_distance_m(det["above_noise_db"], sig)
        summary["visited_s"] = round(now - t0, 3)
        self.steps = getattr(self, "steps", 0) + 1
        profile = None
        if self.baseline is not None and self.baseline.profile and (self.steps % 60 == 1 or self.just_recorded):
            profile = self.baseline.public()       # the full emitter list now and then, not every step
            self.just_recorded = False
        return {
            "baseline_profile": profile,
            "timestamp": now,
            "band": band,
            "sweep_number": self.sweeps,
            "step_seconds": round(now - t0, 3),
            "sweep_seconds": self.last_cycle_seconds,
            "learning": self.learning,
            "baseline": self.baseline_status(),
            "spectra": {band: summary},
            "detections": found,
        }

    def apply_dual_band(self, band, found, clusters):
        ev = dual_band_evidence(self.dual, self.last_cycle_seconds)
        if not ev:
            return found
        bonus = ev["f7_bonus"] + ev["f9_bonus"]
        for d in found:
            if d["method"] in VIDEO_METHODS and bonus > 0:
                d["confidence"] = round(min(0.95, d["confidence"] + bonus), 3)
                d["threat_level"] = rf.threat_level(d["confidence"])
                d.setdefault("reasons", []).extend(dual_band_reasons(ev))
        has_video = any(d["method"] in VIDEO_METHODS for d in found)
        level = self.dual[band][-1][1]
        if not has_video and level is not None and ev["f7"] >= DUAL_ONLY_MIN_F7:
            strongest = max(rf.wide_strong(clusters), key=lambda c: c["above_noise_db"])
            det = rf.cluster_detection(band, strongest, "Dual-band link activity (2.4 + 5 GHz)",
                                       round(min(0.75, DUAL_ONLY_CONF + ev["f9_bonus"]), 3), "dual-band")
            det["reasons"] = dual_band_reasons(ev) + [{
                "text": "Neither band alone matched a drone rule; reported because new signals keep appearing on "
                        "both bands together. A new dual-band WiFi device could also do this, so it stays medium",
                "effect": f"{det['confidence']:.0%}"}]
            det["track_key"] = "dual-band"
            det["band"] = "2.4+5GHz"          # one entry whichever band reported it
            found.append(det)
        return found

    def sweep(self):
        """One full cycle over every band, merged into one report (used by
        tools that want everything at once)."""
        merged = {"spectra": {}, "detections": []}
        while True:
            r = self.step()
            merged["spectra"].update(r["spectra"])
            merged["detections"] += r["detections"]
            merged.update({k: r[k] for k in ("timestamp", "sweep_number", "sweep_seconds", "learning")})
            if not self.schedule:
                return merged

    def control_band(self, band, st):
        """868MHz: one long capture -> display spectrum + packet analysis."""
        lo, hi = rf.BANDS[band]
        center = (lo + hi) // 2
        samples = self.receiver.capture(center, control_link.CONTROL_SAMPLES)
        f, db = rf.hop_spectrum(samples, center)
        result = rf.build_band_result(band, [f], [db], [float(np.percentile(db, 20))], [(center, samples)])
        summary = rf.spectrum_summary(result)
        packets = control_link.find_packets(samples, center)
        summary["raw"] = rf.raw_view(result, [], {"packets": packets[:60]})
        if self.recording_baseline:
            self.baseline.add(band, result, [])
        link = st.control.update(packets)
        st.background.sweeps += 1          # 868MHz learning period just counts sweeps
        summary["background"] = {"learning": st.learning, "sweeps": min(st.background.sweeps, st.learn_sweeps),
                                 "learn_sweeps": st.learn_sweeps, "busy_channels_mhz": []}
        summary["packets"] = len(packets)
        if not link or st.learning:
            return summary, None
        conf = 0.8
        det = {
            "band": band,
            "drone_type": f"FHSS control link ({band}) - ExpressLRS/Crossfire-like",
            "method": "control-link",
            "signature": None,
            "channel_mhz": None,
            "confidence": conf,
            "threat_level": rf.threat_level(conf),
            "frequency_mhz": link["center_mhz"],
            "power_db": link["level_db"],
            "above_noise_db": link["level_db"],
            "bandwidth_mhz": link["span_mhz"],
            "crest_factor_db": None,
            "edge_drop_db": None,
            "wifi_channel_aligned": False,
            "wifi_channel_mhz": None,
            "fpv_channel_mhz": None,
            "modulation_hint": None,
            "channels_seen": link["channels_mhz"],
            "packets_per_sweep": link["packets_per_sweep"],
            "reasons": [
                {"text": f"Short packets in {link['present']} of the last {link['window']} sweeps "
                         f"(~{link['packets_per_sweep']} per 26 ms look)", "effect": None},
                {"text": f"They jump between {len(link['channels_mhz'])} channels spread over {link['span_mhz']} MHz - "
                         "alarms, meters and LoRaWAN sensors use one or a few fixed channels", "effect": None},
                {"text": "That pattern matches an ExpressLRS/Crossfire control link (not yet tested on a real one)",
                 "effect": "80%"},
            ],
            "track_key": f"control:{band}",
        }
        return summary, det


VIDEO_METHODS = {"hopping", "calibrated", "shape"}


def correlate(found, others=()):
    """A control link and a video link at (nearly) the same time from the
    same sensor is the strongest sign of an FPV drone (the boss's
    'activity correlates with 2.4/5.8GHz' row): mark this step's
    detections and raise confidence. `others` = recent detections from the
    sensor's other bands."""
    pool = list(found) + list(others)
    has_control = any(d["method"] == "control-link" for d in pool)
    has_video = any(d["method"] in VIDEO_METHODS and d["confidence"] >= 0.6 for d in pool)
    if not (has_control and has_video):
        return
    for d in found:
        if d["method"] == "control-link":
            d["drone_type"] += " + video link active: likely FPV drone"
        elif d["method"] in VIDEO_METHODS and d["confidence"] >= 0.6:
            d["drone_type"] += " + control link active"
        else:
            continue
        d["correlated"] = True
        d["confidence"] = max(d["confidence"], 0.92)
        d["threat_level"] = rf.threat_level(d["confidence"])
        d.setdefault("reasons", []).append(
            {"text": f"An 868 MHz control link and a video link are active within {CORRELATION_WINDOW_S:.0f} s of "
                     "each other at this sensor - the strongest sign of an FPV drone", "effect": "raised to 92%"})
