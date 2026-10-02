"""
drone-detector/domain/algorithms/pattern_matching.py
Pattern Matching Algorithm

Tanggung jawab:
- Mencocokkan PSD & peak terhadap database signature drone

Tidak mengandung:
- I/O file
- Database
- Hardware detail
"""

from typing import List, Optional

import numpy as np

from domain.entities.drone import DroneSignature


def match_signature(
    psd: np.ndarray,
    peaks: List[int],
    signatures: List[DroneSignature] | None = None,
) -> Optional[str]:
    """
    Cocokkan sinyal terhadap drone signature.

    Parameters
    ----------
    psd : np.ndarray
        Power Spectral Density
    peaks : List[int]
        Indeks peak hasil deteksi
    signatures : List[DroneSignature] | None
        Signature database (di-inject dari luar)

    Returns
    -------
    signature_id : Optional[str]
        ID signature drone jika match
    """
    if not peaks or not signatures:
        return None

    # Estimasi bandwidth sinyal
    bandwidth = _estimate_bandwidth(peaks)

    for sig in signatures:
        if not sig.matches_bandwidth(bandwidth):
            continue

        confidence = _calculate_confidence(psd, peaks, sig)

        if sig.is_confident(confidence):
            return sig.id

    return None


def _estimate_bandwidth(peaks: List[int]) -> float:
    """
    Estimasi bandwidth berbasis jarak peak.
    """
    if len(peaks) < 2:
        return 0.0
    return float(max(peaks) - min(peaks))


def _calculate_confidence(
    psd: np.ndarray,
    peaks: List[int],
    signature: DroneSignature,
) -> float:
    """
    Hitung confidence score kecocokan.
    """
    if not peaks:
        return 0.0

    peak_powers = [psd[p] for p in peaks]
    avg_power = float(np.mean(peak_powers))

    # Normalisasi sederhana
    confidence = (avg_power - np.min(psd)) / (
        np.max(psd) - np.min(psd) + 1e-12
    )

    return confidence
