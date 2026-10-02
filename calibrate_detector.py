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


def pct(values, lo=5, hi=95):
    return float(np.percentile(values, lo)), float(np.percentile(values, hi))


def build_signature(name, band, region, drone_clusters, any_frequency):
    pad = 2.0
    in_region = [c for sweep in drone_clusters for c in sweep
                 if region["lo_mhz"] - pad <= c["center_mhz"] <= region["hi_mhz"] + pad]
    if len(in_region) < MIN_MATCHING_CLUSTERS:
        return None, len(in_region)
    cen = pct([c["center_mhz"] for c in in_region])
    bw = pct([c["bandwidth_mhz"] for c in in_region])
    cf = pct([c["crest_factor_db"] for c in in_region])
    ed = pct([c["edge_drop_db"] for c in in_region])
    sig = {
        "name": f"{name} ({band} {round((region['lo_mhz'] + region['hi_mhz']) / 2)}MHz)",
        "band": band,
        "any_frequency": any_frequency,
        "center_mhz": [round(cen[0] - 1.0, 2), round(cen[1] + 1.0, 2)],
        "bandwidth_mhz": [round(bw[0] * 0.8, 2), round(bw[1] * 1.2, 2)],
        "crest_factor_db": [round(cf[0] - 1.5, 1), round(cf[1] + 1.5, 1)],
        "edge_drop_db": [round(ed[0] - 2.0, 1), round(ed[1] + 2.0, 1)],
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "samples": len(in_region),
    }
    return sig, len(in_region)


def sweep_hit_rate(sweeps, band, test):
    if not sweeps:
        return 0.0
    return sum(any(test(c) for c in s) for s in sweeps) / len(sweeps)


def analyze(session, name, any_frequency):
    base, drone = session["baseline"], session["drone"]
    print(f"\nBaseline: {base['sweeps']} sweeps   Drone: {drone['sweeps']} sweeps")
    if base["sweeps"] < 5 or drone["sweeps"] < 5:
        print("WARNING: fewer than 5 sweeps in a phase - results will be unreliable. Use a longer --seconds.")

    new_sigs = []
    for band, drone_b in drone["bands"].items():
        base_b = base["bands"].get(band)
        if base_b is None:
            continue
        print(f"\n=== {band} ===")
        print(f"Noise floor: baseline {np.median(base_b['noise_floor_db']):.1f}dB, "
              f"drone {np.median(drone_b['noise_floor_db']):.1f}dB")

        # Generic rules on the same data, for comparison.
        generic = lambda c: rf.classify_cluster(c, band) is not None
        print(f"Generic shape rules: fired in {sweep_hit_rate(base_b['clusters'], band, generic):.0%} of "
              f"BASELINE sweeps (false alarms) and {sweep_hit_rate(drone_b['clusters'], band, generic):.0%} "
              f"of DRONE sweeps")

        regions = find_drone_regions(base_b, drone_b, base["sweeps"], drone["sweeps"])
        if not regions:
            print("No frequencies were consistently busier with the drone on. Either it isn't transmitting "
                  "in this band, it's too weak (move it closer / try --amp), or it frequency-hops "
                  "(hopping control links can't be learned this way).")
            continue

        for r in regions:
            print(f"\nDrone-only activity {r['lo_mhz']}-{r['hi_mhz']}MHz "
                  f"(busy {r['drone_occupancy']:.0%} of drone sweeps vs {r['baseline_occupancy']:.0%} baseline)")
            sig, n = build_signature(name, band, r, drone_b["clusters"], any_frequency)
            if sig is None:
                print(f"  Only {n} measurable signal(s) there - too few/inconsistent to learn a signature.")
                continue
            m = lambda c, s=sig: rf.matches_signature(c, s, band)
            recall = sweep_hit_rate(drone_b["clusters"], band, m)
            false_rate = sweep_hit_rate(base_b["clusters"], band, m)
            in_region = lambda c, r=r: r["lo_mhz"] - 2 <= c["center_mhz"] <= r["hi_mhz"] + 2
            generic_recall = sweep_hit_rate(drone_b["clusters"], band, lambda c: in_region(c) and generic(c))
            sig["detection_rate"] = round(recall, 3)
            sig["baseline_false_alarm_rate"] = round(false_rate, 3)
            sig["confidence"] = 0.9 if false_rate == 0 and recall >= 0.8 else (0.75 if false_rate < 0.05 else 0.6)
            print(f"  Learned shape: {sig['bandwidth_mhz'][0]}-{sig['bandwidth_mhz'][1]}MHz wide, "
                  f"crest {sig['crest_factor_db'][0]}-{sig['crest_factor_db'][1]}dB, "
                  f"edge drop {sig['edge_drop_db'][0]}-{sig['edge_drop_db'][1]}dB")
            print(f"  Signature caught the drone in {recall:.0%} of drone sweeps; "
                  f"false alarms in {false_rate:.0%} of baseline sweeps")
            print(f"  (Generic rules caught it in {generic_recall:.0%} of drone sweeps)")
            if false_rate >= 0.05:
                print("  WARNING: this signature also matches your background - it will cause false alarms.")
            new_sigs.append(sig)
    return new_sigs


def save_signatures(new_sigs, name):
    existing = rf.load_signatures()
    kept = [s for s in existing if not s["name"].startswith(f"{name} (")]
    if len(kept) != len(existing):
        print(f"Replacing {len(existing) - len(kept)} earlier signature(s) named '{name}'.")
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
