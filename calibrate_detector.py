#!/usr/bin/env python3
"""
calibrate_detector.py - learn what YOUR drone looks like to your HackRF.

It records two phases with the same sweep the dashboard uses:
  1. BASELINE - drone (and its controller/goggles) switched OFF, so
     everything seen is your normal background: WiFi, Bluetooth, etc.
  2. DRONE    - drone powered on and transmitting video (props off is
     fine, video link must be up), placed a few metres from the antenna.

Then it compares them. Frequencies that are busy only while the drone is on
are the drone's signal; their measured shape (bandwidth, crest factor, edge
drop) becomes a signature saved in drone_signatures.json, which the
dashboard backend matches before its generic rules.

It also reports honestly how well it works:
  * how often the signature caught the drone during the DRONE phase,
  * how often it fired on background during BASELINE (false alarms),
  * how the generic shape rules did on the same data, for comparison.

Usage (stop drone_dashboard_backend.py first - only one program can
use the HackRF at a time):
    python3 calibrate_detector.py --name "My drone"
    python3 calibrate_detector.py --name "My drone" --bands 5.8 --seconds 60
    python3 calibrate_detector.py --reanalyze calibration/session_XXXX.json --name "My drone"
"""
import argparse
import json
import os
import time

import numpy as np

import rf_detector as rf

# A frequency is "the drone's" if it's occupied in at least this fraction
# of DRONE sweeps and at least this much more often than in BASELINE.
MIN_DRONE_OCCUPANCY = 0.3
MIN_OCCUPANCY_INCREASE = 0.25
REGION_MERGE_HZ = 1_000_000
MIN_REGION_MHZ = 0.5
MIN_MATCHING_CLUSTERS = 3


# ======================== Recording ======================== #

def record_phase(receiver, bands, seconds, label):
    data = {"sweeps": 0, "bands": {}}
    t_end = time.time() + seconds
    while time.time() < t_end:
        for band in bands:
            res = rf.sweep_band(receiver, band)
            occupied = (res["power_db"] - res["noise_db"]) > rf.OCCUPIED_DB
            clusters = rf.find_clusters(res["freqs_hz"], res["power_db"], res["noise_db"])
            b = data["bands"].setdefault(band, {
                "start_mhz": float(res["freqs_hz"][0]) / 1e6,
                "bin_mhz": rf.BIN_HZ / 1e6,
                "occupancy": [0] * len(occupied),
                "clusters": [],
                "noise_floor_db": [],
            })
            b["occupancy"] = (np.array(b["occupancy"]) + occupied.astype(int)).tolist()
            b["clusters"].append(clusters)
            b["noise_floor_db"].append(round(res["noise_floor_db"], 1))
        data["sweeps"] += 1
        left = max(0, int(t_end - time.time()))
        print(f"\r  {label}: {data['sweeps']} sweeps recorded, {left}s left   ", end="", flush=True)
    print()
    return data


# ======================== Analysis ======================== #

def find_drone_regions(base_b, drone_b, n_base, n_drone):
    occ_b = np.array(base_b["occupancy"]) / max(n_base, 1)
    occ_d = np.array(drone_b["occupancy"]) / max(n_drone, 1)
    n = min(len(occ_b), len(occ_d))
    occ_b, occ_d = occ_b[:n], occ_d[:n]
    mask = (occ_d >= MIN_DRONE_OCCUPANCY) & (occ_d - occ_b >= MIN_OCCUPANCY_INCREASE)
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    gap = int(REGION_MERGE_HZ / rf.BIN_HZ)
    regions = []
    for g in np.split(idx, np.where(np.diff(idx) > gap)[0] + 1):
        lo = drone_b["start_mhz"] + g[0] * drone_b["bin_mhz"]
        hi = drone_b["start_mhz"] + g[-1] * drone_b["bin_mhz"]
        if hi - lo >= MIN_REGION_MHZ:
            regions.append({
                "lo_mhz": round(lo, 2), "hi_mhz": round(hi, 2),
                "drone_occupancy": round(float(occ_d[g].mean()), 2),
                "baseline_occupancy": round(float(occ_b[g].mean()), 2),
            })
    return regions


def pct(values, q):
    return float(np.percentile(values, q))


# Candidate drone signals: at least this wide and this far above noise.
MIN_CANDIDATE_BW_MHZ = 1.0
MIN_CANDIDATE_ABOVE_NOISE_DB = 12.0
# Peaks within this distance of each other are the same channel.
CHANNEL_TOLERANCE_MHZ = 0.6
# Sliding window (in sweeps) used to decide whether a signal hops.
WINDOW_SWEEPS = 5


def learn_channels(peaks):
    """Group peak frequencies into channels: peaks recurring within
    CHANNEL_TOLERANCE_MHZ of each other, often enough to not be chance."""
    peaks = sorted(peaks)
    groups, cur = [], [peaks[0]]
    for p in peaks[1:]:
        if p - cur[-1] <= CHANNEL_TOLERANCE_MHZ:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    min_count = max(3, int(0.05 * len(peaks)))
    return [round(float(np.median(g)), 2) for g in groups if len(g) >= min_count]


def evaluate(sig, sweeps, band):
    """(per-sweep match rate, confirmed rate) - 'confirmed' uses the same
    SignatureTracker logic as the dashboard backend."""
    tracker = rf.SignatureTracker(sig)
    matched = confirmed = 0
    for sw in sweeps:
        chans = {ch for c in sw for ch in [rf.matches_signature(c, sig, band)] if ch is not None}
        ok, _ = tracker.update(chans)
        matched += bool(chans)
        confirmed += ok
    n = max(len(sweeps), 1)
    return matched / n, confirmed / n


def learn_signature(name, band, regions, drone_b, base_b, any_frequency):
    pad = 2.0
    in_regions = lambda f: any(r["lo_mhz"] - pad <= f <= r["hi_mhz"] + pad for r in regions)
    cands = [c for sw in drone_b["clusters"] for c in sw
             if c["bandwidth_mhz"] >= MIN_CANDIDATE_BW_MHZ
             and c["above_noise_db"] >= MIN_CANDIDATE_ABOVE_NOISE_DB
             and in_regions(c["peak_mhz"])]
    if len(cands) < MIN_MATCHING_CLUSTERS:
        print(f"  Only {len(cands)} measurable drone signal(s) - too few to learn from.")
        return None

    channels = learn_channels([c["peak_mhz"] for c in cands])
    if not channels:
        print("  The drone's signal peaks never repeated on the same frequency - can't learn channels.")
        return None

    # Drop channels your background also uses - a channel the baseline
    # hits in 10%+ of sweeps would make the signature fire on it.
    busy = []
    for ch in channels:
        rate = np.mean([any(abs(c["peak_mhz"] - ch) <= CHANNEL_TOLERANCE_MHZ and
                            c["bandwidth_mhz"] >= MIN_CANDIDATE_BW_MHZ for c in sw)
                        for sw in base_b["clusters"]]) if base_b["clusters"] else 0
        if rate >= 0.10:
            busy.append(ch)
    if busy:
        print(f"  Ignoring channel(s) {busy}MHz - also busy with the drone OFF.")
    channels = [ch for ch in channels if ch not in busy]
    if not channels:
        return None

    on_ch = [c for c in cands if min(abs(c["peak_mhz"] - ch) for ch in channels) <= CHANNEL_TOLERANCE_MHZ]
    bw = [c["bandwidth_mhz"] for c in on_ch]
    sig = {
        "format": 2,
        "name": f"{name} ({band})",
        "band": band,
        "any_frequency": any_frequency,
        "channels_mhz": channels,
        "channel_tolerance_mhz": CHANNEL_TOLERANCE_MHZ,
        # One-sided minimums with a margin rather than tight ranges: the
        # drone further away (weaker) measures less peaked than up close.
        "bandwidth_mhz": [round(max(rf.SIGNATURE_MIN_BANDWIDTH_MHZ, pct(bw, 5) * 0.7), 2), round(pct(bw, 95) * 1.3, 2)],
        "min_crest_factor_db": round(pct([c["crest_factor_db"] for c in on_ch], 10) - 2.0, 1),
        "min_edge_drop_db": round(pct([c["edge_drop_db"] for c in on_ch], 10) - 3.0, 1),
        "min_above_noise_db": MIN_CANDIDATE_ABOVE_NOISE_DB,
        "window_sweeps": WINDOW_SWEEPS,
        "min_channels_in_window": 1,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "samples": len(on_ch),
    }

    # Hopping? If, with the drone on, most 5-sweep windows contain 2+
    # different channels, require that before confirming. That is what
    # stops a WiFi router parked on one of those channels from matching.
    if len(channels) >= 2:
        hop_sig = dict(sig, min_channels_in_window=2)
        _, hop_rate = evaluate(hop_sig, drone_b["clusters"], band)
        if hop_rate >= 0.5:
            sig = hop_sig
    sig["hopping"] = sig["min_channels_in_window"] >= 2
    return sig


def analyze(session, name, any_frequency):
    base, drone = session["baseline"], session["drone"]
    print(f"\nBaseline: {base['sweeps']} sweeps   Drone: {drone['sweeps']} sweeps")
    if base["sweeps"] < 5 or drone["sweeps"] < 5:
        print("WARNING: fewer than 5 sweeps in a phase - results will be unreliable. Use a longer --seconds.")

    good, rejected = [], []
    for band, drone_b in drone["bands"].items():
        base_b = base["bands"].get(band)
        if base_b is None:
            continue
        print(f"\n=== {band} ===")
        print(f"Noise floor: baseline {np.median(base_b['noise_floor_db']):.1f}dB, "
              f"drone {np.median(drone_b['noise_floor_db']):.1f}dB")
        generic = lambda sw: any(rf.classify_cluster(c, band) is not None for c in sw)
        g_base = np.mean([generic(sw) for sw in base_b["clusters"]])
        g_drone = np.mean([generic(sw) for sw in drone_b["clusters"]])
        print(f"Generic shape rules: fired in {g_base:.0%} of BASELINE sweeps (false alarms) "
              f"and {g_drone:.0%} of DRONE sweeps")

        regions = find_drone_regions(base_b, drone_b, base["sweeps"], drone["sweeps"])
        if not regions:
            print("No frequencies were consistently busier with the drone on. Either it isn't transmitting "
                  "in this band, or it's too weak (move it closer / try --amp).")
            continue
        for r in regions:
            print(f"Drone-only activity {r['lo_mhz']}-{r['hi_mhz']}MHz "
                  f"(busy {r['drone_occupancy']:.0%} of drone sweeps vs {r['baseline_occupancy']:.0%} baseline)")

        sig = learn_signature(name, band, regions, drone_b, base_b, any_frequency)
        if sig is None:
            continue
        d_match, d_conf = evaluate(sig, drone_b["clusters"], band)
        b_match, b_conf = evaluate(sig, base_b["clusters"], band)
        sig["detection_rate"] = round(d_conf, 3)
        sig["baseline_false_alarm_rate"] = round(b_conf, 3)
        sig["confidence"] = 0.9 if b_conf == 0 and d_conf >= 0.8 else 0.75

        print(f"Learned: channels {', '.join(f'{c:g}' for c in sig['channels_mhz'])}MHz"
              + (" - FREQUENCY HOPPING (must be seen on 2+ channels within "
                 f"{sig['window_sweeps']} sweeps to confirm)" if sig["hopping"] else " - fixed channel"))
        print(f"  Shape: {sig['bandwidth_mhz'][0]}-{sig['bandwidth_mhz'][1]}MHz wide, "
              f"crest >= {sig['min_crest_factor_db']}dB, edge drop >= {sig['min_edge_drop_db']}dB, "
              f">= {sig['min_above_noise_db']}dB above noise")
        print(f"  Drone ON : matched {d_match:.0%} of sweeps, confirmed {d_conf:.0%}")
        print(f"  Drone OFF: matched {b_match:.0%} of sweeps, confirmed {b_conf:.0%} (false alarms)")
        if b_conf >= 0.05:
            print("  NOT SAVED: it also confirms on your background - would cause false alarms.")
            rejected.append(sig)
        elif d_conf < 0.5:
            print("  NOT SAVED: it only confirmed the drone in under half the sweeps - too unreliable.")
            rejected.append(sig)
        else:
            good.append(sig)
    return good


def save_signatures(new_sigs, name):
    existing = rf.load_signatures()
    kept = [s for s in existing if not s["name"].startswith(f"{name} (") and "channels_mhz" in s]
    if len(kept) != len(existing):
        print(f"Replacing {len(existing) - len(kept)} earlier/old-format signature(s).")
    with open(rf.SIGNATURES_FILE, "w") as fh:
        json.dump({"signatures": kept + new_sigs}, fh, indent=2)
    print(f"Saved {len(new_sigs)} signature(s) to {rf.SIGNATURES_FILE}. "
          f"Restart drone_dashboard_backend.py to use them.")


# ======================== Main ======================== #

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="My drone", help="name for the learned signature(s)")
    ap.add_argument("--bands", nargs="+", choices=["2.4", "5.8"], default=["2.4", "5.8"])
    ap.add_argument("--seconds", type=int, default=45, help="recording time per phase (default 45)")
    ap.add_argument("--any-frequency", action="store_true",
                    help="match the learned shape anywhere in the band (use if your drone changes channel)")
    ap.add_argument("--lna", type=int, default=16)
    ap.add_argument("--vga", type=int, default=20)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--reanalyze", metavar="SESSION_JSON", help="re-run the analysis on a saved session")
    ap.add_argument("--no-save", action="store_true", help="analyse only, don't write drone_signatures.json")
    args = ap.parse_args()

    if args.reanalyze:
        with open(args.reanalyze) as fh:
            session = json.load(fh)
    else:
        from python_hackrf import pyhackrf
        bands = [b + "GHz" for b in args.bands]
        print("Connecting to HackRF... (make sure drone_dashboard_backend.py is NOT running)")
        receiver = rf.HackRFReceiver.open(pyhackrf, lna_gain=args.lna, vga_gain=args.vga, amp=args.amp)
        try:
            input("\nSTEP 1/2: switch the drone, its controller and any goggles OFF, then press Enter...")
            baseline = record_phase(receiver, bands, args.seconds, "BASELINE (drone off)")
            input("\nSTEP 2/2: power the drone ON with its video link running, a few metres from the "
                  "antenna, then press Enter...")
            drone = record_phase(receiver, bands, args.seconds, "DRONE (drone on)")
        finally:
            receiver.close(pyhackrf)
        session = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "name": args.name,
                   "gains": {"lna": args.lna, "vga": args.vga, "amp": args.amp},
                   "baseline": baseline, "drone": drone}
        os.makedirs("calibration", exist_ok=True)
        path = os.path.join("calibration", f"session_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as fh:
            json.dump(session, fh)
        print(f"Raw recording saved to {path} (re-analyse any time with --reanalyze)")

    new_sigs = analyze(session, args.name, args.any_frequency)
    print()
    if not new_sigs:
        print("Nothing learned - drone_signatures.json left unchanged.")
    elif args.no_save:
        print(json.dumps(new_sigs, indent=2))
    else:
        save_signatures(new_sigs, args.name)


if __name__ == "__main__":
    main()
