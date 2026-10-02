"""
domain/entities/signal.py

This file was never included in the purchased package, but fft.py and
psd.py both import IQSignal and Spectrum from here, with no fallback -
their import chain breaks without it. The fields below are exactly
what those two files actually use, inferred directly from reading
their code (iq_signal.samples, .sample_rate, .center_frequency,
.timestamp in fft.py; spectrum.magnitude in psd.py, plus the same four
fields fft.py constructs a Spectrum with).
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class IQSignal:
    """A captured block of complex IQ samples."""
    samples: np.ndarray          # complex64/complex128 array
    sample_rate: float           # Hz
    center_frequency: float = 0.0  # Hz - the tuned frequency when these samples were captured
    timestamp: Optional[float] = None  # unix time; defaults to capture time if not given

    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


@dataclass
class Spectrum:
    """The frequency-domain result of running FFT on an IQSignal."""
    frequencies: np.ndarray      # Hz, one per bin
    magnitude: np.ndarray        # same length as frequencies, dB or linear depending on how it was computed
    center_frequency: float = 0.0
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()
