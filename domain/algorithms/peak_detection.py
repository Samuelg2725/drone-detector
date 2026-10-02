"""
drone-detector/domain/algorithms/peak_detection.py
Peak Detection Algorithm

Tanggung jawab:
- Mendeteksi puncak sinyal signifikan pada PSD

Tidak mengandung:
- Hardware detail
- Plotting / UI
- Framework dependency
"""

from typing import List
import numpy as np


def detect_peaks(
    psd: np.ndarray,
    threshold_db: float = -60.0,
    min_distance: int = 5,
) -> List[int]:
    """
    Deteksi peak pada PSD.

    Parameters
    ----------
    psd : np.ndarray
        Power Spectral Density (dB)
    threshold_db : float
        Ambang batas minimum peak (dB)
    min_distance : int
        Jarak minimum antar peak (bin)

    Returns
    -------
    peaks : List[int]
        Indeks bin yang terdeteksi sebagai peak
    """
    if psd.size == 0:
        return []

    peaks: List[int] = []

    for i in range(1, len(psd) - 1):
        if (
            psd[i] > threshold_db
            and psd[i] > psd[i - 1]
            and psd[i] > psd[i + 1]
        ):
            # Enforce minimum distance
            if peaks and i - peaks[-1] < min_distance:
                if psd[i] > psd[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)

    return peaks
