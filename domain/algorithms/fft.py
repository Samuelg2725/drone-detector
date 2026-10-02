"""
drone-detector/domain/algorithms/fft.py
FFT Algorithm (Domain Layer)

Tanggung jawab:
- Mengubah IQSignal (time-domain) menjadi Spectrum (frequency-domain)

Tidak mengandung:
- Hardware detail
- Window management eksternal
- Plotting / I/O
"""

import numpy as np

from domain.entities.signal import IQSignal, Spectrum


def compute_fft(
    iq_signal: IQSignal,
    fft_size: int | None = None,
    window: str = "hann",
    scale: str = "db",
) -> Spectrum:
    """
    Compute FFT dari IQSignal.

    Parameters
    ----------
    iq_signal : IQSignal
        Frame IQ kompleks
    fft_size : int | None
        Ukuran FFT (default: panjang samples)
    window : str
        Jenis window ("hann", "hamming", "blackman", "rect")
    scale : str
        "linear" atau "db"

    Returns
    -------
    Spectrum
    """
    samples = iq_signal.samples
    n = fft_size or len(samples)

    if n <= 0:
        raise ValueError("fft_size must be positive")

    # 1. Windowing
    win = _get_window(window, n)
    samples = samples[:n] * win

    # 2. FFT & shift
    fft_result = np.fft.fftshift(np.fft.fft(samples, n=n))

    # 3. Magnitude
    magnitude = np.abs(fft_result)

    if scale == "db":
        magnitude = 20 * np.log10(magnitude + 1e-12)

    # 4. Frequency axis
    freqs = np.fft.fftshift(
        np.fft.fftfreq(n, d=1.0 / iq_signal.sample_rate)
    ) + iq_signal.center_frequency

    return Spectrum(
        frequencies=freqs,
        magnitude=magnitude,
        center_frequency=iq_signal.center_frequency,
        timestamp=iq_signal.timestamp,
    )


def _get_window(name: str, n: int) -> np.ndarray:
    """
    Return window function.
    """
    name = name.lower()

    if name in ("hann", "hanning"):
        return np.hanning(n)
    if name == "hamming":
        return np.hamming(n)
    if name == "blackman":
        return np.blackman(n)
    if name in ("rect", "rectangular", "none"):
        return np.ones(n)

    raise ValueError(f"Unsupported window type: {name}")
