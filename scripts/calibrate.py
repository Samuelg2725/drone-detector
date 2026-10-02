"""
drone-detector/scripts/calibrate.py
RF Calibration Tool
===================

Tujuan:
- Mengukur noise floor
- Menentukan threshold deteksi yang realistis
- Kalibrasi gain SDR (manual assisted)

Catatan penting:
- Script ini TIDAK dipanggil oleh app runtime
- Aman dijalankan terpisah (maintenance / setup)
- Hasil kalibrasi disimpan sebagai file JSON

Output:
- data/exports/calibration/calibration_YYYYMMDD_HHMMSS.json
"""

import json
import time
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime

from infrastructure.hardware.sdr_base import SDRBase
from infrastructure.hardware.hackrf import HackRF
from infrastructure.hardware.rtl_sdr import RTLSDR
from infrastructure.hardware.pluto import PlutoSDR


# ------------------------------------------------------------
# Config
# ------------------------------------------------------------

FRAME_SIZE = 2048
NUM_FRAMES = 200


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def compute_psd(samples: np.ndarray) -> np.ndarray:
    window = np.hanning(len(samples))
    fft = np.fft.fftshift(np.fft.fft(samples * window))
    psd = 20 * np.log10(np.abs(fft) + 1e-12)
    return psd


def measure_noise_floor(sdr: SDRBase) -> dict:
    """
    Measure noise statistics.
    """
    psd_acc = []

    for _ in range(NUM_FRAMES):
        iq = sdr.read_samples(FRAME_SIZE)
        psd = compute_psd(iq)
        psd_acc.append(psd)

    psd_stack = np.vstack(psd_acc)

    return {
        "noise_floor_db": float(np.mean(psd_stack)),
        "noise_std_db": float(np.std(psd_stack)),
        "noise_min_db": float(np.min(psd_stack)),
        "noise_max_db": float(np.max(psd_stack)),
    }


def suggest_threshold(noise_floor_db: float, margin_db: float = 6.0) -> float:
    """
    Threshold sederhana: noise + margin.
    """
    return noise_floor_db + margin_db


# ------------------------------------------------------------
# SDR Factory
# ------------------------------------------------------------

def create_sdr(sdr_type: str, cfg: dict) -> SDRBase:
    if sdr_type == "hackrf":
        return HackRF(cfg)
    if sdr_type == "rtl_sdr":
        return RTLSDR(cfg)
    if sdr_type == "pluto":
        return PlutoSDR(cfg)
    raise ValueError(f"Unsupported SDR type: {sdr_type}")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RF Calibration Tool")
    parser.add_argument("--sdr", required=True,
                        choices=["hackrf", "rtl_sdr", "pluto"])
    parser.add_argument("--center-frequency", type=float, required=True)
    parser.add_argument("--sample-rate", type=float, default=10_000_000)
    parser.add_argument("--gain", type=float, default=None)

    args = parser.parse_args()

    sdr_cfg = {
        "center_frequency": args.center_frequency,
        "sample_rate": args.sample_rate,
    }

    if args.gain is not None:
        sdr_cfg["gain"] = args.gain

    print("[*] Initializing SDR...")
    sdr = create_sdr(args.sdr, sdr_cfg)
    sdr.start()

    print("[*] Measuring noise floor...")
    noise_stats = measure_noise_floor(sdr)

    threshold = suggest_threshold(noise_stats["noise_floor_db"])

    sdr.stop()

    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "sdr_type": args.sdr,
        "center_frequency": args.center_frequency,
        "sample_rate": args.sample_rate,
        "gain": args.gain,
        "noise": noise_stats,
        "suggested_threshold_db": threshold,
    }

    out_dir = Path("data/exports/calibration")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"calibration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[OK] Calibration saved → {out_file}")
    print(f"[INFO] Suggested detection threshold: {threshold:.2f} dB")


if __name__ == "__main__":
    main()
