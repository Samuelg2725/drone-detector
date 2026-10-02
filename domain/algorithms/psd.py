"""
drone-detector/domain/algorithms/psd.py
Power Spectral Density (PSD) Algorithm

Tanggung jawab:
- Menghitung PSD dari Spectrum (FFT magnitude)

Tidak mengandung:
- Hardware detail
- Plotting / UI
- File I/O
"""

import numpy as np

from domain.entities.signal import Spectrum


def compute_psd(
    spectrum: Spectrum,
    reference: float = 1.0,
    scale: str = "db",
) -> np.ndarray:
    """
    Compute Power Spectral Density (PSD).

    Parameters
    ----------
    spectrum : Spectrum
        Hasil FFT
    reference : float
        Reference power (default 1.0)
    scale : str
        "linear" atau "db"

    Returns
    -------
    psd : np.ndarray
        PSD array (same length as spectrum)
    """
    # 1. Power calculation
    power = np.square(spectrum.magnitude)

    if scale == "db":
        power = 10 * np.log10(power / reference + 1e-12)

    return power
