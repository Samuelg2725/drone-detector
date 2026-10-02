#!/usr/bin/env python3
"""
measure_retune.py - measure how long YOUR SDR keeps delivering samples from
the previous frequency after it is retuned, and save it so every program
waits exactly that long instead of a cautious guess.

Why: after each retune the detector throws away the first samples, because
they can still belong to the frequency it was on before. The safe default
(HackRF: 2^19 samples = 26ms per retune, ~80% of each sweep) was a guess.

How: it needs a strong signal that is ON ALL THE TIME - WiFi won't do, it
comes in bursts. FM radio (88-108MHz) is ideal. It
  1. finds the strongest FM station,
  2. retunes between it and a quiet frequency many times, recording
     straight after each retune WITHOUT discarding anything,
  3. finds where the station appears/disappears in the recording - every
     sample before that point is stale,
  4. saves the worst case + a margin to sdr_timing.json.

Usage (stop the dashboard first - only one program can use the SDR):
    python3 measure_retune.py                 # HackRF
    python3 measure_retune.py --sdr pluto     # Pluto
    python3 measure_retune.py --station-mhz 97.7   # if it can't find a station itself
"""
import argparse
import json
import time

import numpy as np

import rf_detector as rf

BLOCK = 4096                       # time resolution of the search: 0.2ms at 20MS/s
STATION_OFFSET_HZ = 3_000_000      # station placed 3MHz off-centre (away from the DC spike)
QUIET_JUMP_HZ = 300_000_000        # "quiet" frequency: 300MHz above the station
PRESENT_DB = 10.0


def station_level(samples, offset_hz):
    """Per-block level (dB above that block's median) of the bins at offset_hz."""
    n = len(samples) // BLOCK
    blocks = samples[:n * BLOCK].reshape(n, BLOCK) * np.hanning(BLOCK)
    p = np.fft.fftshift(np.abs(np.fft.fft(blocks, axis=1)) ** 2, axes=1)
    f = (np.arange(BLOCK) - BLOCK // 2) * rf.SAMPLE_RATE_HZ / BLOCK
    sel = np.abs(f - offset_hz) <= 60_000
    return 10 * np.log10(p[:, sel].max(axis=1) / (np.median(p, axis=1) + 1e-20) + 1e-20)


RUN = 8                            # blocks in a row needed to call a change (noise can poke above the line)


def first_run(mask, value):
    """Index of the first block that starts RUN consecutive blocks equal to value."""
    for i in range(len(mask) - RUN + 1):
        if np.all(mask[i:i + RUN] == value):
            return i
    return None


def find_station(rx, start_mhz=88.0, stop_mhz=108.0):
    best = (0.0, None)
    for c in np.arange(start_mhz * 1e6 + 7e6, stop_mhz * 1e6, 14e6):
        f, db = rf.hop_spectrum(rx.capture(c, rf.NUM_SAMPLES), c)
        rel = db - np.median(db)
        i = int(np.argmax(rel))
        if rel[i] > best[0]:
            best = (float(rel[i]), float(f[i]))
    return best


def raw_capture_hackrf(rx, center_hz, n):
    """Retune and record n samples with NO settling discard."""
    with rx.lock:
        rx.active = False
    rx.sdr.pyhackrf_set_freq(int(center_hz))
    with rx.lock:
        rx.want, rx.idx, rx.skip, rx.active = n, 0, 0, True
    t0 = time.time()
    while rx.active and time.time() - t0 < n / rf.SAMPLE_RATE_HZ + 2:
        time.sleep(0.002)
    with rx.lock:
        rx.active = False
        return rx.buf[:rx.idx].copy()


def measure_hackrf(rx, station_hz, trials):
    a = station_hz - STATION_OFFSET_HZ          # station appears at +3MHz when tuned to a
    b = a + QUIET_JUMP_HZ
    n = rf.MAX_CAPTURE_SAMPLES
    worst = 0
    for t in range(trials):
        rx.capture(a, 2 ** 15)                  # settle on the station (normal, with discard)
        x = raw_capture_hackrf(rx, b, n)        # jump away: leading station blocks are stale
        present = station_level(x, STATION_OFFSET_HZ) > PRESENT_DB
        gone = first_run(present, False)                 # where the old frequency stops for good
        stale_samples = int(gone * BLOCK) if gone is not None else len(x)
        rx.capture(b, 2 ** 15)
        y = raw_capture_hackrf(rx, a, n)        # jump back: blocks before the station appears are stale
        present2 = station_level(y, STATION_OFFSET_HZ) > PRESENT_DB
        arrived = first_run(present2, True)              # where the new frequency starts for good
        stale_back = int(arrived * BLOCK) if arrived is not None else len(y)
        worst = max(worst, stale_samples, stale_back)
        print(f"  trial {t + 1}: away {stale_samples} stale samples, back {stale_back} "
              f"({max(stale_samples, stale_back) / rf.SAMPLE_RATE_HZ * 1e3:.1f} ms)")
    return worst


def measure_pluto(rx, station_hz, trials, reads=4):
    a = station_hz - STATION_OFFSET_HZ
    b = a + QUIET_JUMP_HZ
    worst = 0
    for t in range(trials):
        rx.capture(a, rf.NUM_SAMPLES)
        rx.dev.rx_lo = int(b)
        rx.lo = int(b)
        stale = 0
        for k in range(reads):                  # count reads still showing the station
            x = np.asarray(rx._rx()) / rx.FULL_SCALE
            if np.mean(station_level(x.astype(np.complex64), STATION_OFFSET_HZ) > PRESENT_DB) > 0.5:
                stale = k + 1
        worst = max(worst, stale)
        print(f"  trial {t + 1}: {stale} stale read(s) after retune")
    return worst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    rf.add_sdr_args(ap)
    ap.add_argument("--station-mhz", type=float, help="use this FM station instead of searching")
    ap.add_argument("--trials", type=int, default=10)
    args = ap.parse_args()

    print(f"Connecting to {args.sdr}... (stop the dashboard first)")
    rx = rf.receiver_from_args(args)
    try:
        if args.station_mhz:
            station_hz, strength = args.station_mhz * 1e6, None
        else:
            print("Looking for the strongest FM station (88-108 MHz)...")
            strength, station_hz = find_station(rx)
            if station_hz is None or strength < PRESENT_DB + 5:
                raise SystemExit(f"No FM station strong enough (best +{strength:.0f} dB). Try a different antenna "
                                 "position, or give one with --station-mhz 97.7")
            print(f"Using {station_hz / 1e6:.2f} MHz (+{strength:.0f} dB above noise)")

        print(f"Retuning {args.trials} times each way...")
        existing = {}
        try:
            with open(rf.TIMING_FILE) as fh:
                existing = json.load(fh)
        except (FileNotFoundError, ValueError):
            pass
        if args.sdr == "hackrf":
            worst = measure_hackrf(rx, station_hz, args.trials)
            settle = int(np.ceil((worst + 16384) / 16384) * 16384)   # + ~0.8ms margin
            old = 2 ** 19
            existing["hackrf_settle_samples"] = settle
            print(f"\nWorst case: {worst} stale samples ({worst / rf.SAMPLE_RATE_HZ * 1e3:.1f} ms).")
            print(f"Saved settle = {settle} samples ({settle / rf.SAMPLE_RATE_HZ * 1e3:.1f} ms per retune) "
                  f"instead of {old} ({old / rf.SAMPLE_RATE_HZ * 1e3:.1f} ms).")
            per_hop_old = (old + 2 ** 17) / rf.SAMPLE_RATE_HZ
            per_hop_new = (settle + 2 ** 17) / rf.SAMPLE_RATE_HZ
            print(f"Capture time per slice: {per_hop_old * 1e3:.0f} ms -> {per_hop_new * 1e3:.0f} ms "
                  f"(~{per_hop_old / per_hop_new:.1f}x faster sweeps, before processing time).")
        else:
            worst = measure_pluto(rx, station_hz, args.trials)
            existing["pluto_discard_reads"] = worst
            print(f"\nWorst case: {worst} stale read(s). Saved discard = {worst} read(s) per retune.")
        existing["measured"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(rf.TIMING_FILE, "w") as fh:
            json.dump(existing, fh, indent=2)
        print(f"Written to {rf.TIMING_FILE} - the dashboard, sensor_node and calibration use it automatically.")
    finally:
        rx.close()


if __name__ == "__main__":
    main()
