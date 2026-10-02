#!/usr/bin/env python3
"""
hackrf_spectrum_test.py - a self-contained test: grab real IQ samples
from your HackRF and show the spectrum, completely bypassing this
package's app/api/infrastructure layers - which, as of this test
session, have had broken imports at every single layer we opened
(infrastructure/__init__.py, app/__init__.py, api/routes/spectrum.py),
strongly suggesting this package was never actually run end-to-end
before being sold.

This reuses only the real, demonstrably-correct low-level pyhackrf
calls already shown working inside infrastructure/hardware/hackrf.py's
HackRFDevice class - not that class itself, or anything it depends on.

Usage:
    python3 hackrf_spectrum_test.py
"""
import time

import numpy as np
from python_hackrf import pyhackrf

CENTER_FREQ_HZ = 2_440_000_000  # 2.45GHz - this package's own default
SAMPLE_RATE_HZ = 10_000_000  # 10MS/s
NUM_SAMPLES = 2 ** 18  # ~262k samples


def main():
    print("Connecting to HackRF...")
    pyhackrf.pyhackrf_init()
    sdr = pyhackrf.pyhackrf_open()

    sdr.pyhackrf_set_sample_rate(SAMPLE_RATE_HZ)
    sdr.pyhackrf_set_freq(CENTER_FREQ_HZ)
    sdr.pyhackrf_set_lna_gain(16)
    sdr.pyhackrf_set_vga_gain(20)
    sdr.pyhackrf_set_amp_enable(False)
    sdr.pyhackrf_set_antenna_enable(False)

    baseband_filter = min(SAMPLE_RATE_HZ * 0.8, 10e6)
    allowed_filter = pyhackrf.pyhackrf_compute_baseband_filter_bw_round_down_lt(baseband_filter)
    sdr.pyhackrf_set_baseband_filter_bandwidth(allowed_filter)

    print(f"Reading {NUM_SAMPLES} samples at {CENTER_FREQ_HZ / 1e6:.1f}MHz, {SAMPLE_RATE_HZ / 1e6:.0f}MS/s...")

    samples = np.zeros(NUM_SAMPLES, dtype=np.complex64)
    state = {"idx": 0}

    def callback(device, buffer, buffer_length, valid_length):
        accepted = valid_length // 2
        raw = buffer[:valid_length].astype(np.int8)
        iq = (raw[0::2] + 1j * raw[1::2]) / 128.0
        remaining = NUM_SAMPLES - state["idx"]
        to_copy = min(accepted, remaining)
        samples[state["idx"]:state["idx"] + to_copy] = iq[:to_copy]
        state["idx"] += to_copy
        return 0

    sdr.set_rx_callback(callback)
    sdr.pyhackrf_start_rx()

    timeout = NUM_SAMPLES / SAMPLE_RATE_HZ + 1.0
    start = time.time()
    while state["idx"] < NUM_SAMPLES and (time.time() - start) < timeout:
        time.sleep(0.01)

    sdr.pyhackrf_stop_rx()
    sdr.pyhackrf_close()
    pyhackrf.pyhackrf_exit()

    if state["idx"] < NUM_SAMPLES:
        print(f"Warning: only got {state['idx']}/{NUM_SAMPLES} samples before timing out - still usable, just fewer points.")

    print("Computing spectrum...")
    window = np.hanning(len(samples))
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    magnitude_db = 20 * np.log10(np.abs(spectrum) + 1e-12)
    freqs_mhz = (np.fft.fftshift(np.fft.fftfreq(len(samples), d=1 / SAMPLE_RATE_HZ)) + CENTER_FREQ_HZ) / 1e6

    peak_idx = int(np.argmax(magnitude_db))
    print(f"\nPeak: {magnitude_db[peak_idx]:.1f}dB at {freqs_mhz[peak_idx]:.3f}MHz")
    print(f"Average level: {np.mean(magnitude_db):.1f}dB")
    print("(If this peak and average move around sensibly as you point the antenna at different things,")
    print(" the HackRF link itself is genuinely working - independent of anything else in this package.)")

    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.plot(freqs_mhz, magnitude_db)
        plt.xlabel("Frequency (MHz)")
        plt.ylabel("Power (dB)")
        plt.title(f"HackRF spectrum around {CENTER_FREQ_HZ / 1e6:.1f}MHz")
        plt.grid(True)
        plt.savefig("hackrf_spectrum.png")
        print("\nSaved a plot to hackrf_spectrum.png")
    except ImportError:
        print("\n(matplotlib not installed, skipping the plot - the numbers above are the real result either way)")


if __name__ == "__main__":
    main()
