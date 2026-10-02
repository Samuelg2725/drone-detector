"""
drone-detector/scripts/benchmark.py
Pipeline Benchmark Tool
=======================

Tujuan:
- Mengukur performa komputasi (FFT / PSD)
- Mengukur throughput pipeline (frames/sec)
- Tidak menyentuh hardware / API

Benchmark fokus:
- FFT execution time
- PSD computation time
- End-to-end loop time

Output:
- Console summary
- data/exports/benchmark/benchmark_YYYYMMDD_HHMMSS.json
"""

import json
import time
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime


# ------------------------------------------------------------
# Config Defaults
# ------------------------------------------------------------

DEFAULT_FRAMES = 2000
FRAME_SIZE = 2048
FFT_SIZE = 2048
WARMUP_FRAMES = 100


# ------------------------------------------------------------
# DSP Functions
# ------------------------------------------------------------

def compute_fft(samples: np.ndarray) -> np.ndarray:
    return np.fft.fftshift(np.fft.fft(samples, n=FFT_SIZE))


def compute_psd(fft: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.abs(fft) + 1e-12)


# ------------------------------------------------------------
# Benchmark Routines
# ------------------------------------------------------------

def benchmark_fft(frames: int) -> dict:
    samples = (
        np.random.randn(FRAME_SIZE)
        + 1j * np.random.randn(FRAME_SIZE)
    ).astype(np.complex64)

    # Warm-up
    for _ in range(WARMUP_FRAMES):
        compute_fft(samples)

    start = time.perf_counter()

    for _ in range(frames):
        compute_fft(samples)

    elapsed = time.perf_counter() - start

    return {
        "frames": frames,
        "total_time_sec": elapsed,
        "fps": frames / elapsed,
        "avg_ms_per_frame": (elapsed / frames) * 1000,
    }


def benchmark_psd(frames: int) -> dict:
    samples = (
        np.random.randn(FRAME_SIZE)
        + 1j * np.random.randn(FRAME_SIZE)
    ).astype(np.complex64)

    fft = compute_fft(samples)

    # Warm-up
    for _ in range(WARMUP_FRAMES):
        compute_psd(fft)

    start = time.perf_counter()

    for _ in range(frames):
        compute_psd(fft)

    elapsed = time.perf_counter() - start

    return {
        "frames": frames,
        "total_time_sec": elapsed,
        "fps": frames / elapsed,
        "avg_ms_per_frame": (elapsed / frames) * 1000,
    }


def benchmark_end_to_end(frames: int) -> dict:
    samples = (
        np.random.randn(FRAME_SIZE)
        + 1j * np.random.randn(FRAME_SIZE)
    ).astype(np.complex64)

    # Warm-up
    for _ in range(WARMUP_FRAMES):
        fft = compute_fft(samples)
        compute_psd(fft)

    start = time.perf_counter()

    for _ in range(frames):
        fft = compute_fft(samples)
        compute_psd(fft)

    elapsed = time.perf_counter() - start

    return {
        "frames": frames,
        "total_time_sec": elapsed,
        "fps": frames / elapsed,
        "avg_ms_per_frame": (elapsed / frames) * 1000,
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DSP Benchmark Tool")
    parser.add_argument(
        "--frames",
        type=int,
        default=DEFAULT_FRAMES,
        help="Number of frames to benchmark",
    )
    args = parser.parse_args()

    print("=== Drone Detector Benchmark ===")
    print(f"Frames           : {args.frames}")
    print(f"Frame size       : {FRAME_SIZE}")
    print(f"FFT size         : {FFT_SIZE}")
    print("================================")

    print("[*] Benchmark FFT...")
    fft_stats = benchmark_fft(args.frames)

    print("[*] Benchmark PSD...")
    psd_stats = benchmark_psd(args.frames)

    print("[*] Benchmark End-to-End...")
    e2e_stats = benchmark_end_to_end(args.frames)

    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "frame_size": FRAME_SIZE,
        "fft_size": FFT_SIZE,
        "results": {
            "fft": fft_stats,
            "psd": psd_stats,
            "end_to_end": e2e_stats,
        },
    }

    print("\n=== Results ===")
    for k, v in result["results"].items():
        print(
            f"{k:>12}: "
            f"{v['fps']:.1f} FPS | "
            f"{v['avg_ms_per_frame']:.3f} ms/frame"
        )

    out_dir = Path("data/exports/benchmark")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"benchmark_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n[OK] Benchmark saved → {out_file}")


if __name__ == "__main__":
    main()
