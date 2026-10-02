"""
drone-detector/scripts/replay_iq.py
IQ Replay Tool
==============

Tujuan:
- Memutar ulang dataset IQ (.iq + .json)
- Digunakan untuk demo, debug, dan validasi pipeline
- TIDAK dipanggil oleh app runtime

Fitur:
- Real-time atau accelerated replay
- Statistik dasar (frame count, rate)
- Aman untuk LIVE / REPLAY workflow

Dataset format:
data/iq/<category>/<session>/
├── frame_000000.iq
├── frame_000000.json
├── frame_000001.iq
└── ...
"""

import json
import time
import argparse
from pathlib import Path

import numpy as np

from infrastructure.signal_io.playback import IQPlayback


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def load_metadata(meta_path: Path) -> dict:
    with open(meta_path, "r") as f:
        return json.load(f)


def print_session_info(session_dir: Path):
    meta_files = sorted(session_dir.glob("*.json"))
    if not meta_files:
        print("[WARN] No metadata found")
        return

    meta = load_metadata(meta_files[0])

    print("=== Replay Session Info ===")
    print(f"Session        : {session_dir.name}")
    print(f"Center Freq    : {meta.get('center_frequency')} Hz")
    print(f"Sample Rate    : {meta.get('sample_rate')} Hz")
    print(f"Frame Size     : {meta.get('num_samples')}")
    print(f"Signal Type    : {meta.get('signal_type', 'unknown')}")
    print("============================")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Replay IQ Dataset")
    parser.add_argument(
        "--session",
        required=True,
        help="Path to IQ session directory",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed (1.0 = real-time, 2.0 = 2x faster)",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        help="Limit number of frames (optional)",
    )

    args = parser.parse_args()

    session_dir = Path(args.session)
    if not session_dir.exists():
        raise FileNotFoundError(f"Session not found: {session_dir}")

    print_session_info(session_dir)

    print("[*] Initializing IQPlayback...")
    playback = IQPlayback(
        session_dir=session_dir,
        realtime=(args.speed == 1.0),
        speed=args.speed,
    )

    frame_count = 0
    start_time = time.time()

    print("[*] Starting replay...")
    playback.start()

    try:
        for iq_frame in playback:
            frame_count += 1

            # Placeholder hook:
            # Di sistem nyata, frame ini dikirim ke pipeline
            # Di sini hanya simulasi konsumsi
            _ = np.abs(iq_frame).mean()

            if args.frames and frame_count >= args.frames:
                break

    except KeyboardInterrupt:
        print("\n[!] Replay interrupted by user")

    finally:
        playback.stop()

    elapsed = time.time() - start_time

    print("[OK] Replay finished")
    print(f"Frames played  : {frame_count}")
    print(f"Elapsed time  : {elapsed:.2f} sec")
    if elapsed > 0:
        print(f"Effective FPS : {frame_count / elapsed:.2f}")


if __name__ == "__main__":
    main()
