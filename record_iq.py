#!/usr/bin/env python3
"""
record_iq.py - bank a labelled raw-IQ recording for training data.

This is step 1 of building a dataset for drone-vs-everything-else RF
fingerprinting: you tell it WHAT it is looking at (the label) and roughly
WHERE (a centre frequency), it records raw IQ from one Pluto for a few
seconds, and files it under datasets/<label>/ with all the details saved
alongside. Do a few of each over time and you have a dataset.

You are not synthesising anything here - you point it at the REAL signal
(your real Wi-Fi, your real Bluetooth, your real drone) and it captures
what is actually on the air. That realness is the whole point.

Examples (run on the Pi, one Pluto free):
    # the quiet background, nothing transmitting
    python3 record_iq.py --label background --mhz 2440 --pluto-uri ip:10.67.0.11

    # your Wi-Fi (channel 6 sits at 2437 MHz) while something streams
    python3 record_iq.py --label wifi --mhz 2437 --pluto-uri ip:10.67.0.11

    # Bluetooth busy (play music to AirPods etc.) - it hops, so centre mid-band
    python3 record_iq.py --label bluetooth --mhz 2440 --pluto-uri ip:10.67.0.11

    # your drone, video link running, a few metres away
    python3 record_iq.py --label drone_fpv --mhz 2440 --pluto-uri ip:10.67.0.11

Tips:
  * Free up a Pluto first (stop the sensor using it, or use a spare URI).
  * --mhz is where to listen; the Pluto captures ~20 MHz around it. If you
    don't know the drone's exact channel, look at the dashboard spectrum,
    see where its signal sits, and use that number.
  * Each run saves ONE clip. Record several of each label, on different days
    and conditions, for a dataset worth training on.
"""
import argparse
import json
import os
import time

import numpy as np

try:
    import adi
except ImportError:
    adi = None

RATE_HZ = 20_000_000          # 20 MS/s - matches the detector
FRAME = 32768                 # samples per read
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")


def record(uri, mhz, gain, frames_n):
    if adi is None:
        raise SystemExit("pyadi-iio is not installed. Run:  pip install pyadi-iio --break-system-packages")
    print(f"Connecting to Pluto at {uri} ...")
    sdr = adi.Pluto(uri)
    sdr.sample_rate = int(RATE_HZ)
    sdr.rx_rf_bandwidth = int(RATE_HZ)
    sdr.rx_lo = int(mhz * 1e6)
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0 = int(gain)
    sdr.rx_buffer_size = FRAME
    try:
        sdr._rxadc.set_kernel_buffers_count(1)
    except Exception:
        pass
    sdr.rx()                                   # throw away the first (stale) buffer
    secs = frames_n * FRAME / RATE_HZ
    print(f"Recording {frames_n} frames (~{secs:.2f}s of air) at {mhz:.1f} MHz ...")
    frames = [np.asarray(sdr.rx(), dtype=np.complex64) for _ in range(frames_n)]
    del sdr
    return np.concatenate(frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True,
                    help="what this recording IS, e.g. background / wifi / bluetooth / drone_fpv / drone_dji")
    ap.add_argument("--mhz", type=float, required=True, help="centre frequency to listen at, in MHz")
    ap.add_argument("--pluto-uri", default="ip:192.168.2.1", help="which Pluto to use")
    ap.add_argument("--gain", type=int, default=40, help="Pluto RX gain 0-70 dB (default 40 - same for every clip!)")
    ap.add_argument("--frames", type=int, default=200, help="how many 32768-sample frames to grab (default 200 ~= 0.33s of air, ~52 MB)")
    ap.add_argument("--note", default="", help="free-text note, e.g. 'drone 3m away, office'")
    args = ap.parse_args()

    iq = record(args.pluto_uri, args.mhz, args.gain, args.frames)

    folder = os.path.join(DATASET_DIR, args.label)
    os.makedirs(folder, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.join(folder, f"{args.label}_{args.mhz:.0f}MHz_{stamp}")
    np.save(base + ".npy", iq)
    meta = {"label": args.label, "center_mhz": args.mhz, "sample_rate_hz": RATE_HZ,
            "gain_db": args.gain, "seconds": round(len(iq) / RATE_HZ, 3), "samples": int(len(iq)),
            "pluto_uri": args.pluto_uri, "recorded_at": stamp, "note": args.note}
    with open(base + ".json", "w") as fh:
        json.dump(meta, fh, indent=2)

    mb = len(iq) * 8 / 1e6
    print(f"\nSaved {len(iq):,} samples ({mb:.0f} MB) -> {base}.npy")
    print(f"Label '{args.label}' now has {len([f for f in os.listdir(folder) if f.endswith('.npy')])} clip(s).")
    print("Record more of each label (different times/conditions) to build the dataset.")


if __name__ == "__main__":
    main()
