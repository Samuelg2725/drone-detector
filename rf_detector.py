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
MAX_CAPTURE_SAMPLES = 2 ** 20        # longest single capture (868MHz dwell, retune test)
BASEBAND_FILTER_HZ = 15_000_000      # passband ~ +/-7.5MHz

# Keep 716 bins (~13.98MHz) of every hop: +/-358 bins around DC. Hop step
# is exactly the same width, so stitched hops form one uniform grid.
KEEP_HALF_BINS = 358
HOP_STEP_HZ = 2 * KEEP_HALF_BINS * BIN_HZ

# Samples thrown away after every retune. libhackrf keeps several USB
# transfers in flight, so the first buffers after set_freq can still
# hold the PREVIOUS frequency. 2^19 samples = 26ms covers all of them.
SETTLE_SAMPLES = 2 ** 19
# Pluto: buffers read and thrown away after each retune (same reason).
PLUTO_DISCARD_READS = 1

# Measured values (measure_retune.py) override the safe defaults above.
TIMING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdr_timing.json")


def load_timing():
    """Apply measured retune timings, if measure_retune.py has saved any."""
    global SETTLE_SAMPLES, PLUTO_DISCARD_READS
    try:
        with open(TIMING_FILE) as fh:
            t = json.load(fh)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Couldn't read {TIMING_FILE}: {e} - using safe default retune timing")
        return None
    if "hackrf_settle_samples" in t:
        SETTLE_SAMPLES = int(t["hackrf_settle_samples"])
    if "pluto_discard_reads" in t:
        PLUTO_DISCARD_READS = int(t["pluto_discard_reads"])
    return t


def set_samples_per_hop(n):
    """--samples: listening time per 14MHz slice. Fewer = faster sweeps but
    a rougher noise floor (n/1024 FFTs averaged: 2^17 -> 128, 2^16 -> 64)."""
    global NUM_SAMPLES
    if n < 2 ** 14 or n > MAX_CAPTURE_SAMPLES or n & (n - 1):
        raise ValueError(f"--samples must be a power of two between 16384 and {MAX_CAPTURE_SAMPLES}")
    NUM_SAMPLES = n

DC_EXCLUSION_HZ = 50_000

# Frequency ranges swept, in Hz.
#   868MHz  - EU/UK long-range control links (ExpressLRS, TBS Crossfire),
#             the usual radio control link on FPV drones in the UK
#   2.4GHz  - toy/consumer drone video + control, ExpressLRS 2.4, DJI
#   5.2GHz  - 5.165-5.255GHz, used by DJI's newer video links
#   5.8GHz  - 5.72-5.855GHz, most FPV video (analog and digital)
#   5.8GHz-wide - 5.645-5.925GHz: also catches analog FPV set to channels
#             outside 5.72-5.855 (e.g. Raceband 5658/5695/5880/5917MHz)
BANDS = {
    "868MHz": (860_000_000, 872_000_000),
    "2.4GHz": (2_400_000_000, 2_485_000_000),
    "5.2GHz": (5_165_000_000, 5_255_000_000),
    "5.8GHz": (5_720_000_000, 5_855_000_000),
    "5.8GHz-wide": (5_645_000_000, 5_925_000_000),
}
BAND_ARGS = {"868": "868MHz", "2.4": "2.4GHz", "5.2": "5.2GHz", "5.8": "5.8GHz", "5.8wide": "5.8GHz-wide"}
DEFAULT_BAND_ARGS = ["868", "2.4", "5.2", "5.8"]


def bands_from_args(codes):
    bands = [BAND_ARGS[c] for c in codes]
    if "5.8GHz" in bands and "5.8GHz-wide" in bands:
        bands.remove("5.8GHz")   # the wide range already contains it
    return bands


def is_5ghz(band):
    return band.startswith("5.")


# Bins this far above the local noise floor count as "occupied".
OCCUPIED_DB = 6.0
# Signals listed as generic "RF activity" on the dashboard.
ACTIVITY_DB = 10.0
# Bits of one signal separated by less than this are merged into one
# cluster (FM sidebands dip and recover within a single real signal).
GAP_TOLERANCE_HZ = 300_000
MIN_CLUSTER_BINS = 3
MIN_CLUSTER_DENSITY = 0.5

# Real analog video is ~8-20MHz wide. At 2MHz, strong Bluetooth LE
# advertising (2402/2426/2480MHz, ~2MHz wide when close to the antenna)
# was being reported as "Analog video link" at 95% - seen live, and 7 of
# 8 drone-off false matches in a real recording were these.
ANALOG_MIN_BANDWIDTH_MHZ = 5.0
# Calibrated matches must be at least this wide too (same Bluetooth issue).
SIGNATURE_MIN_BANDWIDTH_MHZ = 3.0

SIGNATURES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone_signatures.json")

# Standard WiFi channel centres (20MHz channels). A cluster centred within
# 3MHz of one is more likely WiFi than a drone - corroborating, not proof.
WIFI_CHANNELS_MHZ = [2412, 2417, 2422, 2427, 2432, 2437, 2442, 2447, 2452, 2457, 2462, 2467, 2472, 2484,
                     5180, 5200, 5220, 5240,
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
        self.buf = np.zeros(MAX_CAPTURE_SAMPLES, dtype=np.complex64)
        self.want = NUM_SAMPLES
        self.idx = 0
        self.skip = 0
        self.active = False
        self.last_callback = 0.0
        self.lna_gain, self.vga_gain, self.amp = lna_gain, vga_gain, amp

    kind = "hackrf"

    @classmethod
    def open(cls, pyhackrf, serial=None, **gains):
        pyhackrf.pyhackrf_init()
        if serial:
            # Several HackRFs on one machine: pick one by serial number
            # (`hackrf_info` lists them).
            open_by_serial = getattr(pyhackrf, "pyhackrf_open_by_serial", None)
            if open_by_serial is None:
                raise RuntimeError("this python_hackrf version can't open by serial - update it")
            sdr = open_by_serial(serial)
        else:
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
            to_copy = min(len(iq), self.want - self.idx)
            self.buf[self.idx:self.idx + to_copy] = iq[:to_copy]
            self.idx += to_copy
            if self.idx >= self.want:
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

    def close(self, pyhackrf=None):
        try:
            self.sdr.pyhackrf_stop_rx()
            self.sdr.pyhackrf_close()
            if pyhackrf is not None:
                pyhackrf.pyhackrf_exit()
        except Exception:
            pass

    def capture(self, center_hz, num_samples=NUM_SAMPLES):
        """Retune, discard the settling samples, return num_samples IQ."""
        num_samples = min(num_samples, MAX_CAPTURE_SAMPLES)
        with self.lock:
            self.active = False
        self.sdr.pyhackrf_set_freq(int(center_hz))
        with self.lock:
            self.want = num_samples
            self.idx = 0
            self.skip = SETTLE_SAMPLES
            self.active = True

        timeout = (num_samples + SETTLE_SAMPLES) / SAMPLE_RATE_HZ + 1.0
        start = time.time()
        while self.active and (time.time() - start) < timeout:
            time.sleep(0.002)

        with self.lock:
            self.active = False
            got = self.idx
            samples = self.buf[:got].copy()

        if got < num_samples // 2:
            # Never FFT a mostly-empty buffer - surface it as a real error.
            if time.time() - self.last_callback > 2.0:
                self.restart()
            raise RuntimeError(f"HackRF delivered only {got}/{num_samples} samples at "
                               f"{center_hz / 1e6:.1f}MHz in {timeout:.1f}s")
        return samples


class PlutoReceiver:
    """ADALM-Pluto / Pluto+ / "Pluto Sky" via pyadi-iio, with the same
    capture(center_hz, num_samples) interface as HackRFReceiver.

    Lessons kept from the earlier plutosky.py, which were found the hard way:
      * a dead USB-network link can make rx() hang forever instead of
        raising, so every read runs on a worker thread with a timeout
      * a "broken pipe" (libiio READ LINE -32) means that connection object
        is dead - reconnect at once rather than retrying it
      * don't soft-reset USB; it can leave the Pluto's network stack dead
    Improvements over it: ~128 averaged FFTs per hop instead of one raw
    FFT, only the flat middle ~14MHz of each 20MHz capture is used, and
    the first buffer after every retune is thrown away (it can still hold
    samples from the previous frequency)."""

    kind = "pluto"
    FULL_SCALE = 2048.0          # AD936x 12-bit samples -> +/-1.0
    RF_BANDWIDTH_HZ = 16_000_000  # analog filter; we use the middle +/-7MHz

    def __init__(self, uri="ip:192.168.2.1", gain_db=40, rx_timeout_s=5.0, reconnect_delay_s=3.0):
        self.uri = uri
        self.gain_db = gain_db
        self.rx_timeout_s = rx_timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.dev = None
        self.buffer_size = None
        self.lo = None
        self.last_attempt = 0.0
        self.connect()

    @classmethod
    def open(cls, **kw):
        return cls(**kw)

    def connect(self):
        import adi
        self.last_attempt = time.time()
        self.close()
        dev = adi.Pluto(self.uri)
        dev.sample_rate = int(SAMPLE_RATE_HZ)
        dev.rx_rf_bandwidth = int(self.RF_BANDWIDTH_HZ)
        dev.gain_control_mode_chan0 = "manual"
        dev.rx_hardwaregain_chan0 = int(self.gain_db)
        try:
            dev._rxadc.set_kernel_buffers_count(1)   # fewer stale buffers queued
        except Exception:
            pass
        self.dev, self.buffer_size, self.lo = dev, None, None

    def close(self, *_):
        if self.dev is not None:
            try:
                self.dev.rx_destroy_buffer()
            except Exception:
                pass
        self.dev = None

    def _rx(self):
        result = {}

        def worker():
            try:
                result["iq"] = self.dev.rx()
            except Exception as e:
                result["error"] = e
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(self.rx_timeout_s)
        if t.is_alive():
            raise TimeoutError(f"Pluto rx() hung for {self.rx_timeout_s}s - connection treated as dead")
        if "error" in result:
            raise result["error"]
        return result["iq"]

    def capture(self, center_hz, num_samples=NUM_SAMPLES):
        num_samples = min(num_samples, MAX_CAPTURE_SAMPLES)
        try:
            if self.dev is None:
                if time.time() - self.last_attempt < self.reconnect_delay_s:
                    raise RuntimeError(f"Pluto at {self.uri} not connected - retrying shortly")
                self.connect()
            if self.buffer_size != num_samples:
                self.dev.rx_destroy_buffer()
                self.dev.rx_buffer_size = int(num_samples)
                self.buffer_size = num_samples
            if self.lo != int(center_hz):
                self.dev.rx_lo = int(center_hz)
                self.lo = int(center_hz)
                for _ in range(PLUTO_DISCARD_READS):
                    self._rx()                 # discard: may predate the retune
            iq = np.asarray(self._rx())
        except Exception as e:
            self.dev = None                    # next capture reconnects
            raise RuntimeError(f"Pluto read failed at {center_hz / 1e6:.1f}MHz: {e}")
        if len(iq) < num_samples // 2:
            raise RuntimeError(f"Pluto returned only {len(iq)}/{num_samples} samples")
        return (iq / self.FULL_SCALE).astype(np.complex64)


def open_receiver(sdr="hackrf", lna=16, vga=20, amp=False, hackrf_serial=None,
                  pluto_uri="ip:192.168.2.1", pluto_gain=40):
    """Open a HackRF or a Pluto - everything after this is the same."""
    t = load_timing()
    if t:
        print(f"Using measured retune timing from {os.path.basename(TIMING_FILE)}: "
              f"HackRF settle {SETTLE_SAMPLES} samples, Pluto discard {PLUTO_DISCARD_READS} read(s)")
    if sdr == "hackrf":
        from python_hackrf import pyhackrf
        return HackRFReceiver.open(pyhackrf, serial=hackrf_serial, lna_gain=lna, vga_gain=vga, amp=amp)
    if sdr == "pluto":
        return PlutoReceiver.open(uri=pluto_uri, gain_db=pluto_gain)
    raise ValueError(f"unknown SDR type {sdr!r} (use hackrf or pluto)")


def add_sdr_args(ap):
    """Command-line options shared by every program that opens an SDR."""
    ap.add_argument("--sdr", choices=["hackrf", "pluto"], default="hackrf", help="receiver type (default hackrf)")
    ap.add_argument("--hackrf-serial", help="HackRF serial number, if several are plugged in (see hackrf_info)")
    ap.add_argument("--lna", type=int, default=16, help="HackRF LNA gain 0-40 dB, steps of 8 (default 16)")
    ap.add_argument("--vga", type=int, default=20, help="HackRF VGA gain 0-62 dB, steps of 2 (default 20)")
    ap.add_argument("--amp", action="store_true", help="HackRF +14dB front-end amp (weak 5.8GHz; can overload)")
    ap.add_argument("--pluto-uri", default="ip:192.168.2.1",
                    help="Pluto address: ip:192.168.2.1 (default), ip:192.168.3.1 for a second one, or usb:x.y.z")
    ap.add_argument("--pluto-gain", type=int, default=40, help="Pluto RX gain 0-70 dB (default 40)")
    ap.add_argument("--samples", type=int, default=2 ** 17,
                    help="samples per 14MHz slice: 131072 (default, ~6.5ms, smoothest), 65536 (2x faster), 32768 ...")
    ap.add_argument("--band-reps", nargs="+", default=[], metavar="BAND=N",
                    help="visit a band N times per cycle, e.g. 2.4=2 (bands with suspicious activity already "
                         "get an extra visit automatically)")
    ap.add_argument("--level-offset-db", type=float, default=0.0,
                    help="added to this sensor's signal levels so different SDRs/antennas compare fairly "
                         "for positioning (see docs/SENSOR_NETWORK.md)")


def band_reps_from_args(args):
    reps = {}
    for item in args.band_reps:
        code, _, n = item.partition("=")
        if code not in BAND_ARGS or not n.isdigit():
            raise SystemExit(f"--band-reps: expected e.g. 2.4=2, got {item!r}")
        reps[BAND_ARGS[code]] = int(n)
    return reps


def receiver_from_args(args):
    set_samples_per_hop(args.samples)
    return open_receiver(args.sdr, lna=args.lna, vga=args.vga, amp=args.amp, hackrf_serial=args.hackrf_serial,
                         pluto_uri=args.pluto_uri, pluto_gain=args.pluto_gain)


# ======================== Spectrum ======================== #

def hop_spectrum(samples, center_hz, with_segments=False):
    """Averaged PSD of one hop, trimmed to the kept slice, DC interpolated.
    Returns (freqs_hz, power_db), plus - if with_segments - the per-segment
    power (n_segments x kept bins, linear) used to measure airtime: how
    much of the ~6.5ms capture each signal was actually transmitting."""
    n_seg = len(samples) // FFT_SIZE
    seg = samples[:n_seg * FFT_SIZE].reshape(n_seg, FFT_SIZE) * np.hanning(FFT_SIZE)
    seg_power = np.fft.fftshift(np.abs(np.fft.fft(seg, axis=1)) ** 2, axes=1)
    power = np.mean(seg_power, axis=0)
    db = 10 * np.log10(power + 1e-12)
    offsets = (np.arange(FFT_SIZE) - FFT_SIZE // 2) * BIN_HZ

    dc = np.abs(offsets) < DC_EXCLUSION_HZ
    lo, hi = np.where(dc)[0][[0, -1]]
    db[dc] = np.linspace(db[lo - 1], db[hi + 1], dc.sum() + 2)[1:-1]

    keep = slice(FFT_SIZE // 2 - KEEP_HALF_BINS, FFT_SIZE // 2 + KEEP_HALF_BINS)
    if with_segments:
        return center_hz + offsets[keep], db[keep], seg_power[:, keep].astype(np.float32)
    return center_hz + offsets[keep], db[keep]


def sweep_band(receiver, band):
    """Hop across one band. Returns a dict with the stitched spectrum, the
    per-bin noise floor and every hop's raw samples."""
    lo_hz, hi_hz = BANDS[band]
    freqs, dbs, floors, hops, segs = [], [], [], [], []
    for center in plan_hops(lo_hz, hi_hz):
        samples = receiver.capture(center, NUM_SAMPLES)
        f, db, sp = hop_spectrum(samples, center, with_segments=True)
        freqs.append(f)
        dbs.append(db)
        segs.append(sp)
        floors.append(float(np.percentile(db, 20)))
        hops.append((center, samples))
    result = build_band_result(band, freqs, dbs, floors, hops)
    seg = np.concatenate(segs, axis=1)
    result["seg_power"] = seg[:, result["_inside"]]
    return result


RAW_IQ_POINTS = 256


def raw_view(result, clusters, extra=None):
    """What the dashboard's Raw Data page shows for one band: every signal
    found (before any filtering), each hop's noise floor and ADC health,
    and a short slice of actual I/Q samples from the busiest hop."""
    hops = []
    for center, samples in result.get("hops", []):
        mag = np.abs(np.concatenate([samples.real, samples.imag]))
        hops.append({
            "center_mhz": round(center / 1e6, 3),
            "samples": int(len(samples)),
            "rms": round(float(np.sqrt(np.mean(np.abs(samples) ** 2))), 4),
            # 8-bit ADC full scale is +/-1.0 here; lots of samples at the
            # rail means the gain is too high (overload -> fake signals).
            "clipping_pct": round(100.0 * float(np.mean(mag >= 0.99)), 3),
        })
    floors = result.get("hop_floors", [])
    for h, fl in zip(hops, floors):
        h["floor_db"] = round(fl, 1)

    iq = None
    if result.get("hops"):
        if clusters:
            target = max(clusters, key=lambda c: c["above_noise_db"])["peak_mhz"] * 1e6
            center, samples = min(result["hops"], key=lambda h: abs(h[0] - target))
        else:
            center, samples = result["hops"][len(result["hops"]) // 2]
        mid = len(samples) // 2
        seg = samples[mid:mid + RAW_IQ_POINTS]
        iq = {"center_mhz": round(center / 1e6, 3), "sample_rate_hz": SAMPLE_RATE_HZ,
              "i": [round(float(v), 4) for v in seg.real], "q": [round(float(v), 4) for v in seg.imag]}

    public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in clusters]
    out = {"clusters": sorted(public, key=lambda c: -c["above_noise_db"])[:40], "hops": hops, "iq": iq}
    if extra:
        out.update(extra)
    return out


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
        "_inside": inside,
        "band": band,
        "hop_floors": floors,
        "freqs_hz": f[inside],
        "power_db": db[inside],
        "noise_db": nf[inside],
        "noise_floor_db": band_floor,
        "hops": hops,
    }


# ======================== Duty cycle & airtime ======================== #

# Two separate questions, because neither alone separates a video link
# from busy WiFi:
#   duty cycle - over the last DUTY_WINDOW_S, in what % of sweeps was this
#                frequency busy? (a video link: ~every sweep)
#   airtime    - within this sweep's ~6.5ms capture, what % of the time was
#                it actually transmitting? (a video link: ~100%; WiFi data
#                comes in packets with gaps)
# "Busy" uses the same test as signal detection (>= OCCUPIED_DB above the
# local noise floor), not a separate fixed +35dB bar - the earlier
# client.py's 35dB bar meant most real signals never counted as active.
DUTY_WINDOW_S = 30.0
DUTY_BIN_HZ = 500_000
DUTY_MIN_SWEEPS = 8            # below this, report "collecting" rather than a %
CONTINUOUS_PCT = 80.0          # duty AND airtime at least this -> continuous
BURSTY_PCT = 40.0              # duty OR airtime below this -> bursty


class DutyTracker:
    """Per band: which 500kHz slices were busy in each recent sweep."""

    def __init__(self):
        from collections import deque
        self.history = deque()      # (time, start_hz, busy bool array)

    def update(self, result, now=None):
        now = now if now is not None else time.time()
        f, rel = result["freqs_hz"], result["power_db"] - result["noise_db"]
        per = max(1, int(round(DUTY_BIN_HZ / BIN_HZ)))
        n = len(rel) // per * per
        busy = (rel[:n].reshape(-1, per).max(axis=1) > OCCUPIED_DB)
        self.history.append((now, float(f[0]), busy))
        while self.history and now - self.history[0][0] > DUTY_WINDOW_S:
            self.history.popleft()

    def duty(self, lo_hz, hi_hz):
        """(percent or None, sweeps in window) for the core of a signal.

        Per sweep, the signal counts as present if its core (middle half)
        is busy: any core slice for a narrow signal, at least half of them
        for a wide one. (Taking a median ACROSS slices, as the earlier
        client.py's averaging effectively did, reads a constant tone that
        sits on a slice boundary as 50% - found in testing.)"""
        if not self.history:
            return None, 0
        width = hi_hz - lo_hz
        core_lo, core_hi = lo_hz + width * 0.25, hi_hz - width * 0.25   # middle half
        start = self.history[-1][1]
        i0 = int((core_lo - start) // DUTY_BIN_HZ)
        i1 = int((core_hi - start) // DUTY_BIN_HZ)
        present = []
        for _, st, busy in self.history:
            if st != start:
                continue
            core = busy[max(i0, 0):min(i1, len(busy) - 1) + 1]
            if len(core) == 0:
                continue
            present.append(core.any() if len(core) <= 2 else core.mean() >= 0.5)
        n = len(present)
        if n < DUTY_MIN_SWEEPS:
            return None, n
        return round(100.0 * sum(present) / n, 1), n


def airtime_pct(result, lo_idx, hi_idx):
    """% of this capture's ~0.05ms time slices in which the signal's core
    was >= OCCUPIED_DB above the noise floor."""
    seg = result.get("seg_power")
    if seg is None or hi_idx < lo_idx:
        return None
    width = hi_idx - lo_idx + 1
    a = lo_idx + width // 4
    b = max(a, hi_idx - width // 4)
    core = seg[:, a:b + 1].mean(axis=1)
    floor_lin = 10 ** (float(np.mean(result["noise_db"][a:b + 1])) / 10)
    return round(100.0 * float(np.mean(core > floor_lin * 10 ** (OCCUPIED_DB / 10))), 1)


def persistence_label(duty, air):
    if duty is None or air is None:
        return "collecting"
    if duty >= CONTINUOUS_PCT and air >= CONTINUOUS_PCT:
        return "continuous"
    if duty < BURSTY_PCT or air < BURSTY_PCT:
        return "bursty"
    return "intermittent"


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
            "_lo_idx": int(start), "_hi_idx": int(end),
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
    """Returns the matched channel (MHz) if the cluster fits the signature,
    else None.

    Signatures learned by calibrate_detector.py list the exact channels
    the drone transmits on; a cluster matches if its PEAK sits on one of
    them and its shape clears the learned minimums. (A hopping drone's
    clusters get merged/smeared by the sweep, so the peak is far more
    stable than the cluster's centre or width - measured on a real
    recording: peaks landed within 0.2MHz of the same 5 channels.)"""
    if sig.get("band") and sig["band"] != band:
        return None
    if "channels_mhz" not in sig:
        return None  # old signature format - re-run calibrate_detector.py
    tol = sig.get("channel_tolerance_mhz", 0.6)
    ch = min(sig["channels_mhz"], key=lambda x: abs(cluster["peak_mhz"] - x))
    on_channel = abs(cluster["peak_mhz"] - ch) <= tol
    if not on_channel and not sig.get("any_frequency"):
        return None
    bw_lo = max(sig["bandwidth_mhz"][0], SIGNATURE_MIN_BANDWIDTH_MHZ)
    ok = (bw_lo <= cluster["bandwidth_mhz"] <= sig["bandwidth_mhz"][1]
          and cluster["crest_factor_db"] >= sig["min_crest_factor_db"]
          and cluster["edge_drop_db"] >= sig["min_edge_drop_db"]
          and cluster["above_noise_db"] >= sig["min_above_noise_db"])
    if not ok:
        return None
    return ch if on_channel else round(cluster["peak_mhz"], 1)


class SignatureTracker:
    """Remembers which of a signature's channels matched in each of the
    last N sweeps. A hopping signature is only CONFIRMED once it has been
    seen on >= min_channels_in_window different channels inside that
    window - a WiFi router sits on one channel, a hopping video link
    doesn't."""

    def __init__(self, sig):
        from collections import deque
        self.sig = sig
        self.window = deque(maxlen=int(sig.get("window_sweeps", 5)))

    def update(self, channels_this_sweep):
        """Call once per sweep. Returns (confirmed, channels seen in window)."""
        self.window.append(set(channels_this_sweep))
        seen = set().union(*self.window)
        need = int(self.sig.get("min_channels_in_window", 1))
        return bool(channels_this_sweep) and len(seen) >= need, sorted(seen)


def classify_cluster(cluster, band, signatures=()):
    """(label, confidence, method, signature, channel) or None.

    1. Calibrated signatures (learned from YOUR drone by
       calibrate_detector.py) - checked first, highest confidence.
    2. Generic shape rules:
       - Analog video (FM): peaked in the middle, tapering edges.
       - Digital video (OFDM): flat top, steep edges, 10-40MHz wide -
         which ordinary WiFi also is; see the WiFi-channel penalty.
    """
    for sig in signatures:
        ch = matches_signature(cluster, sig, band)
        if ch is not None:
            return "Matches a calibrated hopping pattern", float(sig.get("confidence", 0.85)), "calibrated", sig, ch

    cf = cluster["crest_factor_db"]
    edge = cluster["edge_drop_db"]
    bw = cluster["bandwidth_mhz"]
    if cf >= 7.0 and edge >= 10.0 and bw >= ANALOG_MIN_BANDWIDTH_MHZ:
        conf = min(0.95, 0.5 + (cf - 7.0) / 20.0 + (edge - 10.0) / 40.0)
        label = "Analog FPV video link" if is_5ghz(band) else "Analog video link"
        return label + " (shape match)", round(conf, 3), "shape", None, None
    if cf < 5.0 and edge < 8.0 and 10.0 <= bw <= 40.0:
        conf = min(0.90, 0.5 + (5.0 - cf) / 20.0 + (8.0 - edge) / 40.0)
        return "Wideband digital link (OFDM - may be WiFi)", round(conf, 3), "shape", None, None
    return None


# ======================== Calibration-free hopping detection ======================== #

# Validated on a real recording of a 2.4GHz hopping-video drone: with the
# background learned from drone-off sweeps, 0% of drone-off sweeps and
# ~90% of drone-on sweeps were flagged.
HOP_MIN_BW_MHZ = 3.0          # wider than Bluetooth/BLE hops (~1-2MHz)
HOP_MIN_ABOVE_NOISE_DB = 15.0
HOP_MIN_CREST_DB = 6.0
HOP_WINDOW_SWEEPS = 5
HOP_MIN_PRESENT = 4           # strong signal in >= 4 of the last 5 sweeps
HOP_MIN_CHANNELS = 3          # ...peaking on >= 3 frequencies...
HOP_CHANNEL_SPACING_MHZ = 3.0 # ...at least this far apart
HOP_MIN_NEW_CHANNELS = 2      # >= 2 of which aren't normal background
BACKGROUND_BIN_MHZ = 3.0
BACKGROUND_BUSY_FRACTION = 0.10


def wide_strong(clusters):
    """Any strong, wide signal - whatever its shape (what the background
    learns, and what counts as 'new activity' for dual-band correlation)."""
    return [c for c in clusters if c["bandwidth_mhz"] >= HOP_MIN_BW_MHZ
            and c["above_noise_db"] >= HOP_MIN_ABOVE_NOISE_DB]


def hop_candidates(clusters):
    return [c for c in clusters if c["bandwidth_mhz"] >= HOP_MIN_BW_MHZ
            and c["above_noise_db"] >= HOP_MIN_ABOVE_NOISE_DB
            and c["crest_factor_db"] >= HOP_MIN_CREST_DB]


def distinct_channels(peaks, spacing=HOP_CHANNEL_SPACING_MHZ):
    out = []
    for p in sorted(peaks):
        if not out or p - out[-1] >= spacing:
            out.append(p)
    return out


class BackgroundModel:
    """Where strong wide signals normally peak in this band (WiFi routers
    and the like). Learned at startup, then updated slowly - but only
    from sweeps where nothing is being detected, so a drone hovering
    nearby never gets absorbed into the 'normal' background."""

    def __init__(self, alpha=0.01):
        self.busy = {}      # 3MHz bin -> fraction of sweeps with a peak there
        self.sweeps = 0
        self.alpha = alpha

    def update(self, clusters):
        # Learns where ANY strong wide signal normally sits (flat WiFi too,
        # not just peaked ones), so 'new' really means new.
        bins = {int(c["peak_mhz"] // BACKGROUND_BIN_MHZ) for c in wide_strong(clusters)}
        self.sweeps += 1
        a = max(self.alpha, 1.0 / self.sweeps)   # plain average while learning
        for b in set(self.busy) | bins:
            self.busy[b] = (1 - a) * self.busy.get(b, 0.0) + a * (b in bins)

    def is_background(self, peak_mhz):
        b = int(peak_mhz // BACKGROUND_BIN_MHZ)
        return max(self.busy.get(b + d, 0.0) for d in (-1, 0, 1)) >= BACKGROUND_BUSY_FRACTION

    def busy_channels_mhz(self):
        return sorted(round((b + 0.5) * BACKGROUND_BIN_MHZ, 1) for b, f in self.busy.items()
                      if f >= BACKGROUND_BUSY_FRACTION)


class HopDetector:
    """Flags a transmitter that keeps jumping between frequencies: a strong,
    wide signal present in most recent sweeps, peaking on several
    different channels, at least two of them new compared with the
    background. Needs no calibration."""

    def __init__(self, background):
        from collections import deque
        self.background = background
        self.window = deque(maxlen=HOP_WINDOW_SWEEPS)

    def update(self, clusters):
        """Call once per sweep. Returns a summary dict when hopping is seen, else None."""
        self.window.append(hop_candidates(clusters))
        recent = list(self.window)
        present = sum(bool(x) for x in recent)
        peaks = [c["peak_mhz"] for x in recent for c in x]
        chans = distinct_channels(peaks)
        new = [ch for ch in chans if not self.background.is_background(ch)]
        if present < HOP_MIN_PRESENT or len(chans) < HOP_MIN_CHANNELS or len(new) < HOP_MIN_NEW_CHANNELS:
            return None
        latest = [c for c in recent[-1] if not self.background.is_background(c["peak_mhz"])]
        best = max(latest or recent[-1] or [c for x in recent for c in x], key=lambda c: c["above_noise_db"])
        return {"channels_mhz": [round(c, 1) for c in new], "present": present,
                "window": len(recent), "cluster": best}


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


# ======================== Rough distance from signal strength ======================== #

# Reference point: in a real calibration recording, a 2.4GHz drone "a few
# metres" away measured a median of ~36dB above the noise floor (LNA 16,
# VGA 20, amp off). Signatures made by calibrate_detector.py store their
# own reference. Path-loss exponent 2.5 sits between open air (2) and
# indoors/cluttered (3+). This is a ROUGH estimate: the drone's transmit
# power, antenna orientation, walls and gain settings all move it a lot.
DEFAULT_REFERENCE_ABOVE_NOISE_DB = 36.0
DEFAULT_REFERENCE_DISTANCE_M = 3.0
PATH_LOSS_EXPONENT = 2.5


def estimate_distance_m(above_noise_db, sig=None):
    ref_db = (sig or {}).get("reference_above_noise_db", DEFAULT_REFERENCE_ABOVE_NOISE_DB)
    ref_m = (sig or {}).get("reference_distance_m", DEFAULT_REFERENCE_DISTANCE_M)
    d = ref_m * 10 ** ((ref_db - above_noise_db) / (10 * PATH_LOSS_EXPONENT))
    return round(float(min(max(d, 1.0), 5000.0)), 1)


def threat_level(conf):
    return "high" if conf > 0.8 else ("medium" if conf > 0.6 else "low")


def cluster_detection(band, c, label, conf, method, sig=None, channel=None,
                      modulation_hint=None, wifi_ch=None, fpv_ch=None):
    return {
        "band": band,
        "drone_type": label,
        "method": method,
        "signature": sig["name"] if sig else None,
        "channel_mhz": channel,
        "confidence": conf,
        "threat_level": threat_level(conf),
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
    }


VIDEO_MIN_BANDWIDTH_MHZ = 5.0
# A flat (OFDM-like) shape is weak evidence on its own - WiFi has it too -
# so it can't reach "high" without the duty cycle showing a continuous
# transmitter. (Seen in testing: bursty WiFi scored 85% on shape alone.)
DIGITAL_SHAPE_MAX_CONF = 0.6
# Site baseline (site_baseline.py): how busy a signal's frequency normally is.
BASELINE_KNOWN_PCT = 80.0      # normally busy -> a known fixed emitter
BASELINE_COMMON_PCT = 20.0
BASELINE_QUIET_PCT = 2.0


def video_class(c):
    """What the Video Detections tab files a wide signal under (shape only)."""
    if c["bandwidth_mhz"] < VIDEO_MIN_BANDWIDTH_MHZ:
        return None
    if c["crest_factor_db"] >= 7.0 and c["edge_drop_db"] >= 10.0:
        return "Analog video"
    if c["crest_factor_db"] < 5.0 and c["edge_drop_db"] < 8.0 and 10.0 <= c["bandwidth_mhz"] <= 40.0:
        return "Digital video"
    return "Wideband data"


def _pct(x):
    return f"{x:.0%}"


def detections_for_band(result, signatures=(), modulation_analyzer=None, duty_tracker=None, baseline=None):
    """Measure and classify every cluster in a swept band.
    Returns (detections, clusters). Every cluster gets duty cycle, airtime,
    WiFi-channel and video-type annotations (shown on the Raw Data and
    Video Detections pages); clusters that match a rule also become
    detections with a confidence % and the list of reasons behind it."""
    clusters = find_clusters(result["freqs_hz"], result["power_db"], result["noise_db"])
    band = result["band"]
    if duty_tracker is not None:
        duty_tracker.update(result)
    for c in clusters:
        lo_hz, hi_hz = result["freqs_hz"][c["_lo_idx"]], result["freqs_hz"][c["_hi_idx"]]
        duty, n = duty_tracker.duty(lo_hz, hi_hz) if duty_tracker is not None else (None, 0)
        air = airtime_pct(result, c["_lo_idx"], c["_hi_idx"])
        base_occ = baseline.occupancy(band, lo_hz / 1e6, hi_hz / 1e6) if baseline is not None else None
        c.update(duty_cycle_pct=duty, duty_sweeps=n, airtime_pct=air, persistence=persistence_label(duty, air),
                 baseline_occupancy_pct=base_occ,
                 video_class=video_class(c),
                 wifi_channel_mhz=nearest_channel(c["center_mhz"], WIFI_CHANNELS_MHZ, WIFI_CHANNEL_TOLERANCE_MHZ))

    detections = []
    for c in clusters:
        cls = classify_cluster(c, band, signatures)
        if cls is None:
            continue
        label, conf, method, sig, channel = cls
        c["classified_as"] = label
        reasons = []
        if method == "calibrated":
            reasons.append({"text": f"Peak on a channel ({channel} MHz) from a calibrated hopping pattern, shape "
                                    "inside its learned ranges - only used to support a confirmed hopping link",
                            "effect": None})
        elif label.startswith("Analog"):
            reasons.append({"text": f"Shaped like analog (FM) video: peaked in the middle (crest "
                                    f"{c['crest_factor_db']} dB, needs >= 7), tapering edges (edge drop "
                                    f"{c['edge_drop_db']} dB, needs >= 10), {c['bandwidth_mhz']} MHz wide (needs >= 5)",
                            "effect": f"start at {_pct(conf)} (stronger shape = higher)"})
        else:
            reasons.append({"text": f"Flat-topped like digital (OFDM) video: crest {c['crest_factor_db']} dB "
                                    f"(needs < 5), edge drop {c['edge_drop_db']} dB (needs < 8), "
                                    f"{c['bandwidth_mhz']} MHz wide (needs 10-40) - WiFi has this shape too",
                            "effect": f"start at {_pct(conf)}"})

        wifi_ch = c["wifi_channel_mhz"]
        fpv_ch = nearest_channel(c["center_mhz"], FPV_CHANNELS_MHZ, FPV_CHANNEL_TOLERANCE_MHZ) if is_5ghz(band) else None
        if method == "shape":
            digital = not label.startswith("Analog")
            p = c["persistence"]
            if digital and conf > DIGITAL_SHAPE_MAX_CONF:
                conf = DIGITAL_SHAPE_MAX_CONF
                reasons.append({"text": "A flat shape alone is weak evidence (WiFi looks the same), so it is capped "
                                        "until the duty cycle shows a continuous transmitter",
                                "effect": f"capped at {_pct(DIGITAL_SHAPE_MAX_CONF)}"})
            if fpv_ch is not None and not digital:
                conf = min(0.95, conf + 0.1)
                reasons.append({"text": f"Centred on a standard FPV video channel ({fpv_ch} MHz)", "effect": "+10%"})
            if p == "continuous":
                boost = 0.25 if digital else 0.1
                conf = min(0.95, conf + boost)
                reasons.append({"text": f"Continuous transmitter: busy in {c['duty_cycle_pct']}% of sweeps over 30 s and "
                                        f"transmitting {c['airtime_pct']}% of the time - like a video link, unlike WiFi",
                                "effect": f"+{boost:.0%}"})
            elif p == "bursty":
                conf *= 0.5
                reasons.append({"text": f"Bursty: busy in {c['duty_cycle_pct']}% of sweeps, transmitting "
                                        f"{c['airtime_pct']}% of the time - typical of WiFi data, not a video link",
                                "effect": "halved"})
            elif p == "intermittent":
                if digital:
                    conf *= 0.8
                reasons.append({"text": f"Only partly continuous: busy in {c['duty_cycle_pct']}% of sweeps, "
                                        f"{c['airtime_pct']}% airtime", "effect": "x0.8" if digital else "no change"})
            else:
                reasons.append({"text": f"Duty cycle still being measured ({c['duty_sweeps']}/{DUTY_MIN_SWEEPS} sweeps)",
                                "effect": "no change yet"})
            bo = c.get("baseline_occupancy_pct")
            if bo is not None:
                if bo >= BASELINE_KNOWN_PCT:
                    conf *= 0.3
                    reasons.append({"text": f"This frequency was busy {bo:.0f}% of the time in the site baseline - "
                                            "a known fixed emitter here, not something new", "effect": "x0.3"})
                elif bo >= BASELINE_COMMON_PCT:
                    conf *= 0.7
                    reasons.append({"text": f"Busy {bo:.0f}% of the time in the site baseline - common here",
                                    "effect": "x0.7"})
                elif bo <= BASELINE_QUIET_PCT:
                    conf = min(0.95, conf + 0.05)
                    reasons.append({"text": f"This frequency was quiet in the site baseline (busy {bo:.0f}%) - "
                                            "new activity", "effect": "+5%"})
            if wifi_ch is not None:
                if p == "continuous":
                    reasons.append({"text": f"Sits on WiFi channel {wifi_ch} MHz, but it is continuous and WiFi "
                                            "isn't - so not treated as WiFi", "effect": "no penalty"})
                else:
                    conf *= 0.5
                    reasons.append({"text": f"Centred on WiFi channel {wifi_ch} MHz - quite likely just WiFi",
                                    "effect": "halved"})
        conf = round(conf, 3)

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

        det = cluster_detection(band, c, label, conf, method, sig, channel, modulation_hint, wifi_ch, fpv_ch)
        det.update(reasons=reasons, duty_cycle_pct=c["duty_cycle_pct"], airtime_pct=c["airtime_pct"],
                   persistence=c["persistence"])
        detections.append(det)
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
