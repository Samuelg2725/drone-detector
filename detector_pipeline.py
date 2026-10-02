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


class DetectorPipeline:
    def __init__(self, receiver, bands, signatures=(), learn_sweeps=20, analyzer=None):
        self.receiver = receiver
        self.bands = list(bands)
        self.signatures = list(signatures)
        self.analyzer = analyzer
        self.states = {b: BandState(learn_sweeps) for b in self.bands}
        self.sweeps = 0

    @property
    def learning(self):
        return any(st.learning for st in self.states.values())

    def sweep(self):
        """One pass over every band. Returns a report dict:
        {"spectra": {band: summary}, "detections": [...], "sweep_seconds": s, "learning": bool}"""
        t0 = time.time()
        spectra, found = {}, []
        for band in self.bands:
            st = self.states[band]
            if band == control_link.CONTROL_BAND:
                spectra[band], det = self.control_band(band, st)
                if det:
                    found.append(det)
                continue
            result = rf.sweep_band(self.receiver, band)
            spectra[band] = rf.spectrum_summary(result)
            dets, clusters = rf.detections_for_band(result, self.signatures, self.analyzer)
            found.extend(fuse_band(band, dets, clusters, st, self.signatures))
            spectra[band]["background"] = {
                "learning": st.learning,
                "sweeps": min(st.background.sweeps, st.learn_sweeps),
                "learn_sweeps": st.learn_sweeps,
                "busy_channels_mhz": st.background.busy_channels_mhz(),
            }
        correlate(found)
        for det in found:
            sig = next((x for x in self.signatures if x["name"] == det.get("signature")), None)
            det["estimated_distance_m"] = rf.estimate_distance_m(det["above_noise_db"], sig)
        self.sweeps += 1
        return {
            "timestamp": time.time(),
            "sweep_number": self.sweeps,
            "sweep_seconds": round(time.time() - t0, 2),
            "learning": self.learning,
            "spectra": spectra,
            "detections": found,
        }

    def control_band(self, band, st):
        """868MHz: one long capture -> display spectrum + packet analysis."""
        lo, hi = rf.BANDS[band]
        center = (lo + hi) // 2
        samples = self.receiver.capture(center, control_link.CONTROL_SAMPLES)
        f, db = rf.hop_spectrum(samples, center)
        result = rf.build_band_result(band, [f], [db], [float(np.percentile(db, 20))], [])
        summary = rf.spectrum_summary(result)
        packets = control_link.find_packets(samples, center)
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
            "track_key": f"control:{band}",
        }
        return summary, det


VIDEO_METHODS = {"hopping", "calibrated", "shape"}


def correlate(found):
    """A control link and a video link at the same time from the same
    sensor is the strongest sign of an FPV drone (the boss's 'activity
    correlates with 2.4/5.8GHz' row): mark both and raise confidence."""
    control = [d for d in found if d["method"] == "control-link"]
    video = [d for d in found if d["method"] in VIDEO_METHODS and d["confidence"] >= 0.6]
    if not control or not video:
        return
    for d in control + video:
        d["correlated"] = True
        d["confidence"] = max(d["confidence"], 0.92)
        d["threat_level"] = rf.threat_level(d["confidence"])
    for d in control:
        d["drone_type"] += " + video link active: likely FPV drone"
    for d in video:
        d["drone_type"] += " + control link active"

