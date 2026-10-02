"""
drone-detector/infrastructure/hardware/rtl_sdr.py
RTL-SDR Implementation

Concrete implementation of SDRBase for RTL-SDR dongles.
Menggunakan pyrtlsdr (librtlsdr wrapper).

Catatan:
- Sample rate & bandwidth lebih terbatas dibanding HackRF
- Cocok untuk monitoring & low-cost deployment
"""

from typing import Any, Dict
import numpy as np

from infrastructure.hardware.sdr_base import SDRBase


class RTLSDR(SDRBase):
    """
    RTL-SDR implementation.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.sample_rate: float = config.get("sample_rate", 2.4e6)
        self.center_frequency: float = config.get("center_frequency", 2.45e9)
        self.gain: Any = config.get("gain", "auto")  # dB or "auto"

        self._device = None

    # ---------- Lifecycle ----------

    def open(self) -> None:
        """
        Open RTL-SDR device and apply configuration.
        """
        try:
            from rtlsdr import RtlSdr
        except ImportError as exc:
            raise RuntimeError(
                "RTL-SDR library not installed. Install pyrtlsdr."
            ) from exc

        self._device = RtlSdr()

        self._device.sample_rate = self.sample_rate
        self._device.center_freq = self.center_frequency

        if self.gain == "auto":
            self._device.gain = "auto"
        else:
            self._device.gain = float(self.gain)

        self._running = False

    def close(self) -> None:
        """
        Close RTL-SDR device.
        """
        if self._device:
            self._device.close()
            self._device = None
        self._running = False

    # ---------- Streaming ----------

    def start(self) -> None:
        if not self._device:
            raise RuntimeError("RTL-SDR device not opened")
        super().start()

    def stop(self) -> None:
        super().stop()

    def read_samples(self, num_samples: int) -> np.ndarray:
        """
        Read complex IQ samples from RTL-SDR.

        Returns
        -------
        samples : np.ndarray (complex64)
        """
        if not self._running:
            raise RuntimeError("RTL-SDR streaming not started")

        samples = self._device.read_samples(num_samples)

        # pyrtlsdr already returns complex64 normalized samples
        return np.asarray(samples, dtype=np.complex64)

    # ---------- Status ----------

    def status(self) -> Dict[str, Any]:
        return {
            "device": "RTL-SDR",
            "running": self._running,
            "sample_rate": self.sample_rate,
            "center_frequency": self.center_frequency,
            "gain": self.gain,
        }
