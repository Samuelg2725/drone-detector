#!/usr/bin/env python3
"""
rf_detector.py - the HackRF sweep + signal-shape detection used by both
drone_dashboard_backend.py (live dashboard) and calibrate_detector.py
(learning your own drone's signal).

How a sweep works:
  * The HackRF captures 20MHz at a time, so each band is covered by
    retuning ("hopping") across it. Only the central ~14MHz of every hop
    is kept - the outer edges sit in the baseband filter's roll-off and
    alias region - and hops are spaced exactly that far apart, so the
    kept slices tile the band on one seamless, uniform frequency grid.
  * Each hop's spectrum is an averaged (Welch) PSD: ~128 x 1024-point
    FFTs, 19.5kHz bins, noise smooth to ~0.5dB.
  * The DC/LO-leakage spike at each hop's tuned centre is interpolated
    over, so it can never be reported as a signal.
  * Noise floor is estimated per hop (gain/frequency response differs
    across a 280MHz band), then every bin is expressed as dB above it.

Then every cluster of bins clearly above the noise floor is measured
(bandwidth, crest factor, edge drop) and classified - first against any
calibrated signatures in drone_signatures.json, then against the generic
video-link shape rules.
"""
import json
import os
import threading
import time

import numpy as np

# ======================== Configuration ======================== #

SAMPLE_RATE_HZ = 20_000_000
FFT_SIZE = 1024                      # 19.53125kHz bins at 20MS/s
BIN_HZ = SAMPLE_RATE_HZ / FFT_SIZE
NUM_SAMPLES = 2 ** 17                # per hop: ~6.5ms -> 128 averaged FFTs
BASEBAND_FILTER_HZ = 15_000_000      # passband ~ +/-7.5MHz

# Keep 716 bins (~13.98MHz) of every hop: +/-358 bins around DC. Hop step
# is exactly the same width, so stitched hops form one uniform grid.
KEEP_HALF_BINS = 358
HOP_STEP_HZ = 2 * KEEP_HALF_BINS * BIN_HZ

# Samples thrown away after every retune. libhackrf keeps several USB
# transfers in flight, so the first buffers after set_freq can still
# hold the PREVIOUS frequency. 2^19 samples = 26ms covers all of them.
SETTLE_SAMPLES = 2 ** 19

DC_EXCLUSION_HZ = 50_000

# Frequency ranges swept, in Hz. 5.8GHz covers every common analog/digital
# FPV video channel (bands A/B/E/F/R and DJI's 5.725-5.850 range).
BANDS = {
    "2.4GHz": (2_400_000_000, 2_485_000_000),
    "5.8GHz": (5_645_000_000, 5_925_000_000),
}

# Bins this far above the local noise floor count as "occupied".
OCCUPIED_DB = 6.0
# Signals listed as generic "RF activity" on the dashboard.
ACTIVITY_DB = 10.0
# Bits of one signal separated by less than this are merged into one
# cluster (FM sidebands dip and recover within a single real signal).
GAP_TOLERANCE_HZ = 300_000
MIN_CLUSTER_BINS = 3
MIN_CLUSTER_DENSITY = 0.5

ANALOG_MIN_BANDWIDTH_MHZ = 2.0

SIGNATURES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone_signatures.json")

# Standard WiFi channel centres (20MHz channels). A cluster centred within
# 3MHz of one is more likely WiFi than a drone - corroborating, not proof.
WIFI_CHANNELS_MHZ = [2412, 2417, 2422, 2427, 2432, 2437, 2442, 2447, 2452, 2457, 2462, 2467, 2472, 2484,
                     5745, 5765, 5785, 5805, 5825, 5845, 5865, 5885]
WIFI_CHANNEL_TOLERANCE_MHZ = 3.0

# Common 5.8GHz analog FPV video channels (bands A, B, E, F, R). Reported
# as information only - plenty of non-drone kit uses them too.
FPV_CHANNELS_MHZ = sorted({
    5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725,   # A
    5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866,   # B
    5705, 5685, 5665, 5645, 5885, 5905, 5925,         # E
    5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880,   # F (Fatshark)
    5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917,   # R (Raceband)
})
FPV_CHANNEL_TOLERANCE_MHZ = 3.0


def plan_hops(lo_hz, hi_hz):
    """Hop centre frequencies whose kept slices cover [lo_hz, hi_hz)."""
    centers = []
    c = lo_hz + KEEP_HALF_BINS * BIN_HZ
    while c - KEEP_HALF_BINS * BIN_HZ < hi_hz:
        centers.append(int(round(c)))
        c += HOP_STEP_HZ
    return centers


# ======================== HackRF receiver ======================== #

class HackRFReceiver:
    """RX is started ONCE and left streaming; retuning happens on the fly.
    The callback drops buffers unless a capture is in progress."""

    def __init__(self, sdr, lna_gain=16, vga_gain=20, amp=False):
        self.sdr = sdr
        self.lock = threading.Lock()
        self.buf = np.zeros(NUM_SAMPLES, dtype=np.complex64)
        self.idx = 0
        self.skip = 0
        self.active = False
        self.last_callback = 0.0
        self.lna_gain, self.vga_gain, self.amp = lna_gain, vga_gain, amp

    @classmethod
    def open(cls, pyhackrf, **gains):
        pyhackrf.pyhackrf_init()
        sdr = pyhackrf.pyhackrf_open()
        rx = cls(sdr, **gains)
        sdr.pyhackrf_set_sample_rate(SAMPLE_RATE_HZ)
        sdr.pyhackrf_set_freq(BANDS["2.4GHz"][0])
        sdr.pyhackrf_set_lna_gain(rx.lna_gain)
        sdr.pyhackrf_set_vga_gain(rx.vga_gain)
        sdr.pyhackrf_set_amp_enable(rx.amp)
        sdr.pyhackrf_set_antenna_enable(False)
        bw = pyhackrf.pyhackrf_compute_baseband_filter_bw_round_down_lt(BASEBAND_FILTER_HZ + 1)
        sdr.pyhackrf_set_baseband_filter_bandwidth(bw)
        rx.start()
        return rx

    def _callback(self, device, buffer, buffer_length, valid_length):
        self.last_callback = time.time()
        with self.lock:
            if not self.active:
                return 0
            raw = np.asarray(buffer[:valid_length]).astype(np.int8).astype(np.float32)
            iq = (raw[0::2] + 1j * raw[1::2]) / 128.0
            if self.skip > 0:
                drop = min(self.skip, len(iq))
                self.skip -= drop
                iq = iq[drop:]
            to_copy = min(len(iq), NUM_SAMPLES - self.idx)
            self.buf[self.idx:self.idx + to_copy] = iq[:to_copy]
            self.idx += to_copy
            if self.idx >= NUM_SAMPLES:
                self.active = False
        return 0

    def start(self):
        self.sdr.set_rx_callback(self._callback)
        self.sdr.pyhackrf_start_rx()
        self.last_callback = time.time()

    def restart(self):
        print("HackRF stopped delivering samples - restarting RX stream...")
        try:
            self.sdr.pyhackrf_stop_rx()
        except Exception as e:
            print(f"  (stop_rx during restart failed: {e})")
        time.sleep(0.2)
        self.start()

    def close(self, pyhackrf):
        try:
            self.sdr.pyhackrf_stop_rx()
            self.sdr.pyhackrf_close()
            pyhackrf.pyhackrf_exit()
        except Exception:
            pass

    def capture(self, center_hz):
        """Retune, discard the settling samples, return NUM_SAMPLES IQ."""
        with self.lock:
            self.active = False
        self.sdr.pyhackrf_set_freq(int(center_hz))
        with self.lock:
            self.idx = 0
            self.skip = SETTLE_SAMPLES
            self.active = True

        timeout = (NUM_SAMPLES + SETTLE_SAMPLES) / SAMPLE_RATE_HZ + 1.0
        start = time.time()
        while self.active and (time.time() - start) < timeout:
            time.sleep(0.002)

        with self.lock:
            self.active = False
            got = self.idx
            samples = self.buf[:got].copy()

        if got < NUM_SAMPLES // 2:
            # Never FFT a mostly-empty buffer - surface it as a real error.
            if time.time() - self.last_callback > 2.0:
                self.restart()
            raise RuntimeError(f"HackRF delivered only {got}/{NUM_SAMPLES} samples at "
                               f"{center_hz / 1e6:.1f}MHz in {timeout:.1f}s")
        return samples


# ======================== Spectrum ======================== #

def hop_spectrum(samples, center_hz):
    """Averaged PSD of one hop, trimmed to the kept slice, DC interpolated.
    Returns (freqs_hz, power_db)."""
    n_seg = len(samples) // FFT_SIZE
    seg = samples[:n_seg * FFT_SIZE].reshape(n_seg, FFT_SIZE) * np.hanning(FFT_SIZE)
    power = np.fft.fftshift(np.mean(np.abs(np.fft.fft(seg, axis=1)) ** 2, axis=0))
    db = 10 * np.log10(power + 1e-12)
    offsets = (np.arange(FFT_SIZE) - FFT_SIZE // 2) * BIN_HZ

    dc = np.abs(offsets) < DC_EXCLUSION_HZ
    lo, hi = np.where(dc)[0][[0, -1]]
    db[dc] = np.linspace(db[lo - 1], db[hi + 1], dc.sum() + 2)[1:-1]

    keep = slice(FFT_SIZE // 2 - KEEP_HALF_BINS, FFT_SIZE // 2 + KEEP_HALF_BINS)
    return center_hz + offsets[keep], db[keep]


def sweep_band(receiver, band):
    """Hop across one band. Returns a dict with the stitched spectrum, the
    per-bin noise floor and every hop's raw samples."""
    lo_hz, hi_hz = BANDS[band]
    freqs, dbs, floors, hops = [], [], [], []
    for center in plan_hops(lo_hz, hi_hz):
        samples = receiver.capture(center)
        f, db = hop_spectrum(samples, center)
        freqs.append(f)
        dbs.append(db)
        floors.append(float(np.percentile(db, 20)))
        hops.append((center, samples))
    return build_band_result(band, freqs, dbs, floors, hops)


def build_band_result(band, freqs, dbs, floors, hops):
    # Per-hop noise floor (20th percentile - robust to a signal filling
    # most of a hop), clamped to the band-wide floor + 3dB so a hop that's
    # entirely covered by one wide signal (e.g. 20MHz WiFi in a 14MHz
    # hop) doesn't swallow that signal into its own "noise floor".
    band_floor = float(np.median(floors))
    hop_floor = [min(fl, band_floor + 3.0) for fl in floors]
    lo_hz, hi_hz = BANDS[band]
    f = np.concatenate(freqs)
    db = np.concatenate(dbs)
    nf = np.concatenate([np.full(len(x), fl) for x, fl in zip(freqs, hop_floor)])
    inside = (f >= lo_hz) & (f < hi_hz)
    return {
        "band": band,
        "freqs_hz": f[inside],
        "power_db": db[inside],
        "noise_db": nf[inside],
        "noise_floor_db": band_floor,
        "hops": hops,
    }


# ======================== Clusters & classification ======================== #

def find_clusters(freqs_hz, power_db, noise_db):
    """Every distinct signal clearly above the noise floor, with shape
    measurements. Sorted widest first."""
    rel = power_db - noise_db
    idx = np.where(rel > OCCUPIED_DB)[0]
    if len(idx) == 0:
        return []
    gap_bins = max(1, int(round(GAP_TOLERANCE_HZ / BIN_HZ)))
    groups = np.split(idx, np.where(np.diff(idx) > gap_bins)[0] + 1)

    clusters = []
    for g in groups:
        if len(g) < MIN_CLUSTER_BINS:
            continue
        start, end = g[0], g[-1]
        # Random noise hits merged by the gap tolerance are sparse; a real
        # signal stays mostly elevated across its own span.
        if len(g) / (end - start + 1) < MIN_CLUSTER_DENSITY:
            continue
        seg = power_db[start:end + 1]
        peak_rel = int(np.argmax(seg))
        peak_db = float(seg[peak_rel])
        mean_db = float(np.mean(seg))
        edge_bins = max(1, len(seg) // 10)
        edge_drop = min(peak_db - float(np.mean(seg[:edge_bins])),
                        peak_db - float(np.mean(seg[-edge_bins:])))
        bw_mhz = float(freqs_hz[end] - freqs_hz[start]) / 1e6
        clusters.append({
            "center_mhz": round(float(freqs_hz[start] + freqs_hz[end]) / 2e6, 3),
            "peak_mhz": round(float(freqs_hz[start + peak_rel]) / 1e6, 3),
            "peak_db": round(peak_db, 1),
            "above_noise_db": round(float(np.max(rel[start:end + 1])), 1),
            "crest_factor_db": round(peak_db - mean_db, 1),
            "edge_drop_db": round(edge_drop, 1),
            "bandwidth_mhz": round(bw_mhz, 2),
        })
    clusters.sort(key=lambda c: c["bandwidth_mhz"], reverse=True)
    return clusters


def load_signatures(path=SIGNATURES_FILE):
    try:
        with open(path) as fh:
            return json.load(fh).get("signatures", [])
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Couldn't read {path}: {e} - continuing without calibrated signatures")
        return []


def _in(value, rng):
    return rng[0] <= value <= rng[1]


def matches_signature(cluster, sig, band):
    if sig.get("band") and sig["band"] != band:
        return False
    if not sig.get("any_frequency") and not _in(cluster["center_mhz"], sig["center_mhz"]):
        return False
    return (_in(cluster["bandwidth_mhz"], sig["bandwidth_mhz"])
            and _in(cluster["crest_factor_db"], sig["crest_factor_db"])
            and _in(cluster["edge_drop_db"], sig["edge_drop_db"]))


def classify_cluster(cluster, band, signatures=()):
    """(label, confidence, method) or None.

    1. Calibrated signatures (learned from YOUR drone by
       calibrate_detector.py) - checked first, highest confidence.
    2. Generic shape rules:
       - Analog video (FM): peaked in the middle, tapering edges.
       - Digital video (OFDM): flat top, steep edges, 10-40MHz wide -
         which ordinary WiFi also is; see the WiFi-channel penalty.
    """
    for sig in signatures:
        if matches_signature(cluster, sig, band):
            return f"Calibrated match: {sig['name']}", float(sig.get("confidence", 0.85)), "calibrated"

    cf = cluster["crest_factor_db"]
    edge = cluster["edge_drop_db"]
    bw = cluster["bandwidth_mhz"]
    if cf >= 7.0 and edge >= 10.0 and bw >= ANALOG_MIN_BANDWIDTH_MHZ:
        conf = min(0.95, 0.5 + (cf - 7.0) / 20.0 + (edge - 10.0) / 40.0)
        return "Analog Video Link (unverified - shape match only)", round(conf, 3), "shape"
    if cf < 5.0 and edge < 8.0 and 10.0 <= bw <= 40.0:
        conf = min(0.90, 0.5 + (5.0 - cf) / 20.0 + (8.0 - edge) / 40.0)
        return "Digital Video Link (unverified - shape match only)", round(conf, 3), "shape"
    return None


def nearest_channel(center_mhz, channels, tol):
    for ch in channels:
        if abs(center_mhz - ch) <= tol:
            return ch
    return None


def isolate_signal(samples, hop_center_hz, sig_center_hz, bw_hz):
    """Shift a cluster to baseband and brick-wall filter it, so the
    modulation classifier sees just that signal, not the whole 20MHz."""
    n = len(samples)
    t = np.arange(n) / SAMPLE_RATE_HZ
    shifted = samples * np.exp(-2j * np.pi * (sig_center_hz - hop_center_hz) * t)
    spec = np.fft.fft(shifted)
    f = np.fft.fftfreq(n, 1 / SAMPLE_RATE_HZ)
    spec[np.abs(f) > max(bw_hz, 200e3) / 2] = 0
    return np.fft.ifft(spec).astype(np.complex64)


def detections_for_band(result, signatures=(), modulation_analyzer=None):
    """Classify every cluster in a swept band. Returns (detections, clusters)."""
    clusters = find_clusters(result["freqs_hz"], result["power_db"], result["noise_db"])
    detections = []
    for c in clusters:
        cls = classify_cluster(c, result["band"], signatures)
        if cls is None:
            continue
        label, conf, method = cls
        wifi_ch = nearest_channel(c["center_mhz"], WIFI_CHANNELS_MHZ, WIFI_CHANNEL_TOLERANCE_MHZ)
        if wifi_ch is not None and method == "shape":
            conf = round(conf * 0.5, 3)
        fpv_ch = nearest_channel(c["center_mhz"], FPV_CHANNELS_MHZ, FPV_CHANNEL_TOLERANCE_MHZ) \
            if result["band"] == "5.8GHz" else None

        modulation_hint = None
        if modulation_analyzer is not None and result.get("hops"):
            try:
                hop_center, samples = min(result["hops"], key=lambda h: abs(h[0] - c["center_mhz"] * 1e6))
                iq = isolate_signal(samples, hop_center, c["center_mhz"] * 1e6, c["bandwidth_mhz"] * 1e6)
                feats = modulation_analyzer.estimate_modulation(iq)
                modulation_hint = {"type": feats.modulation_type.name,
                                   "confidence": round(float(feats.confidence), 3)}
            except Exception as e:
                modulation_hint = {"error": str(e)}

        detections.append({
            "band": result["band"],
            "drone_type": label,
            "method": method,
            "confidence": conf,
            "threat_level": "high" if conf > 0.8 else ("medium" if conf > 0.6 else "low"),
            "frequency_mhz": c["center_mhz"],
            "power_db": c["peak_db"],
            "above_noise_db": c["above_noise_db"],
            "bandwidth_mhz": c["bandwidth_mhz"],
            "crest_factor_db": c["crest_factor_db"],
            "edge_drop_db": c["edge_drop_db"],
            "wifi_channel_aligned": wifi_ch is not None,
            "wifi_channel_mhz": wifi_ch,
            "fpv_channel_mhz": fpv_ch,
            "modulation_hint": modulation_hint,
        })
    return detections, clusters


def spectrum_summary(result, display_bins=1024):
    """Downsampled (max-pooled, so narrow peaks survive) spectrum + the
    strongest generic RF activity, for the dashboard."""
    f, db, nf = result["freqs_hz"], result["power_db"], result["noise_db"]
    bins = min(display_bins, len(db))
    n = len(db) // bins * bins
    disp_db = db[:n].reshape(bins, -1).max(axis=1)
    disp_nf = nf[:n].reshape(bins, -1).mean(axis=1)
    disp_mhz = f[:n].reshape(bins, -1).mean(axis=1) / 1e6

    rel = np.where(db - nf > ACTIVITY_DB, db - nf, -np.inf)
    peaks = []
    for i in np.argsort(rel)[::-1]:
        if len(peaks) >= 5 or not np.isfinite(rel[i]):
            break
        if all(abs(f[i] - p[0]) >= 1e6 for p in peaks):
            peaks.append((float(f[i]), float(db[i]), float(rel[i])))
    lo, hi = BANDS[result["band"]]
    return {
        "band": result["band"],
        "range_mhz": [lo / 1e6, hi / 1e6],
        "noise_floor_db": round(result["noise_floor_db"], 1),
        "freqs_mhz": [round(float(x), 3) for x in disp_mhz],
        "power_db": [round(float(x), 1) for x in disp_db],
        "noise_db": [round(float(x), 1) for x in disp_nf],
        "peaks": [{"frequency_mhz": round(p[0] / 1e6, 3), "power_db": round(p[1], 1),
                   "above_noise_db": round(p[2], 1)} for p in peaks],
    }
