#!/usr/bin/env python3
"""
control_link.py - detect a drone's radio CONTROL link in the 868MHz band
(ExpressLRS 868, TBS Crossfire - the usual long-range control links on FPV
drones in the UK/EU).

Those links send short packets (a few ms) tens to hundreds of times a
second and hop to a different channel for almost every packet, for as long
as the drone is flying. Other 868MHz devices behave differently:

  * alarms, doorbells, key fobs - one channel, occasional bursts
  * smart meters (wM-Bus), LoRaWAN sensors - one or a few fixed channels,
    a packet every few seconds to minutes
  * continuous carriers - never "burst" at all

So instead of looking at an averaged spectrum, each sweep records ~26ms at
868MHz and slices it into ~0.4ms time steps, finding every individual
packet (time, frequency, width, strength). A control link is flagged only
when packets keep arriving sweep after sweep, on many different channels
spread over at least 2MHz.

NOT YET VALIDATED ON A REAL ExpressLRS/Crossfire LINK - tuned on simulated
packets (see simulate notes in the test). Record a real one with
calibrate_detector.py --bands 868 before relying on it.
"""
from collections import deque

import numpy as np

from rf_detector import BIN_HZ, FFT_SIZE

CONTROL_BAND = "868MHz"
CONTROL_SAMPLES = 2 ** 19       # ~26ms at 20MS/s per sweep
FRAMES_PER_SLOT = 8             # 8 x 51us FFT frames averaged -> ~0.41ms time steps
BURST_THRESHOLD_DB = 8.0        # above that bin's own median level over the capture
MIN_BURST_BINS = 3              # >= ~60kHz wide
MAX_OFFSET_HZ = 6_800_000       # stay inside the baseband filter
DC_GUARD_HZ = 80_000
CHANNEL_SPACING_MHZ = 0.2       # packets closer than this = same channel

# Link decision over a sliding window of sweeps (~1s each).
WINDOW_SWEEPS = 10
MIN_PRESENT_SWEEPS = 5          # packets in >= 5 of the last 10 sweeps...
MIN_CHANNELS = 6                # ...on >= 6 different channels...
MIN_SPAN_MHZ = 2.0              # ...spread over >= 2MHz


def find_packets(samples, center_hz):
    """Every packet in one capture: list of dicts with frequency_mhz,
    bandwidth_khz, above_noise_db, duration_ms."""
    n_frames = len(samples) // FFT_SIZE
    n_slots = n_frames // FRAMES_PER_SLOT
    if n_slots < 4:
        return []
    frames = samples[:n_slots * FRAMES_PER_SLOT * FFT_SIZE].reshape(n_slots * FRAMES_PER_SLOT, FFT_SIZE)
    p = np.abs(np.fft.fft(frames * np.hanning(FFT_SIZE), axis=1)) ** 2
    p = np.fft.fftshift(p, axes=1).reshape(n_slots, FRAMES_PER_SLOT, FFT_SIZE).mean(axis=1)

    offsets = (np.arange(FFT_SIZE) - FFT_SIZE // 2) * BIN_HZ
    usable = (np.abs(offsets) >= DC_GUARD_HZ) & (np.abs(offsets) <= MAX_OFFSET_HZ)
    # Each bin compared with ITS OWN typical level over the capture: flattens
    # the filter shape, and anything always on (carriers) never counts.
    floor = np.median(p, axis=0) + 1e-12
    excess = 10 * np.log10(p / floor + 1e-12)
    hot = (excess > BURST_THRESHOLD_DB) & usable

    # Contiguous runs of hot bins in each time step = a piece of a packet.
    pieces = []
    for slot in range(n_slots):
        idx = np.where(hot[slot])[0]
        if len(idx) == 0:
            continue
        for run in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
            if len(run) < MIN_BURST_BINS:
                continue
            w = p[slot, run]
            pieces.append((slot, run[0], run[-1], float(np.sum(offsets[run] * w) / np.sum(w)),
                           float(np.max(excess[slot, run]))))

    # Join pieces in consecutive time steps that overlap in frequency.
    packets = []
    open_pk = []
    for slot, lo, hi, f, lvl in pieces:
        for pk in open_pk:
            if pk["last"] == slot - 1 and lo <= pk["hi"] + 2 and hi >= pk["lo"] - 2:
                pk.update(last=slot, lo=min(lo, pk["lo"]), hi=max(hi, pk["hi"]), lvl=max(lvl, pk["lvl"]))
                pk["f"].append(f)
                break
        else:
            pk = {"first": slot, "last": slot, "lo": lo, "hi": hi, "lvl": lvl, "f": [f]}
            open_pk.append(pk)
            packets.append(pk)
        open_pk = [q for q in open_pk if q["last"] >= slot - 1]

    slot_ms = FRAMES_PER_SLOT * FFT_SIZE / (BIN_HZ * FFT_SIZE) * 1000
    return [{
        "frequency_mhz": round((center_hz + float(np.median(pk["f"]))) / 1e6, 3),
        "bandwidth_khz": round((pk["hi"] - pk["lo"] + 1) * BIN_HZ / 1e3, 1),
        "above_noise_db": round(pk["lvl"], 1),
        "duration_ms": round((pk["last"] - pk["first"] + 1) * slot_ms, 2),
    } for pk in packets]


def distinct_channels(freqs, spacing=CHANNEL_SPACING_MHZ):
    out = []
    for f in sorted(freqs):
        if not out or f - out[-1] >= spacing:
            out.append(f)
    return out


class ControlLinkDetector:
    """Decides, sweep by sweep, whether an FHSS control link is present."""

    def __init__(self):
        self.window = deque(maxlen=WINDOW_SWEEPS)

    def update(self, packets):
        """Call once per sweep with find_packets() output. Returns a summary
        dict while a control link is present, else None."""
        self.window.append(packets)
        recent = list(self.window)
        present = sum(bool(x) for x in recent)
        all_pk = [p for x in recent for p in x]
        chans = distinct_channels([p["frequency_mhz"] for p in all_pk])
        span = (chans[-1] - chans[0]) if chans else 0.0
        if present < MIN_PRESENT_SWEEPS or len(chans) < MIN_CHANNELS or span < MIN_SPAN_MHZ:
            return None
        levels = sorted(p["above_noise_db"] for p in all_pk)
        return {
            "channels_mhz": chans,
            "span_mhz": round(span, 2),
            "packets_per_sweep": round(len(all_pk) / len(recent), 1),
            "present": present,
            "window": len(recent),
            "level_db": levels[len(levels) // 2],
            "center_mhz": round((chans[0] + chans[-1]) / 2, 3),
            "median_bandwidth_khz": float(np.median([p["bandwidth_khz"] for p in all_pk])),
        }
