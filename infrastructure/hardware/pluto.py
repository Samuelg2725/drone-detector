"""
drone-detector/infrastructure/hardware/pluto.py
ADALM-Pluto SDR Implementation

Concrete implementation of SDRBase for Analog Devices ADALM-Pluto.
Menggunakan pyadi-iio (ADI IIO bindings).

Catatan:
- Pluto memakai jaringan (USB/Ethernet)
- Sample rate & bandwidth configurable
- Cocok untuk research & deployment stabil
"""

from typing import Any, Dict
import numpy as np

from infrastructure.hardware.sdr_base import SDRBase


class PlutoSDR(SDRBase):
    """
    ADALM-Pluto SDR implementation.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.sample_rate: float = config.get("sample_rate", 10e6)
        self.center_frequency: float = config.get("center_frequency", 2.45e9)
        self.rx_gain: float = config.get("rx_gain", 30.0)  # dB
        self.bandwidth: float = config.get("bandwidth", self.sample_rate)

        # Optional: URI (usb:, ip:192.168.2.1, etc)
        self.uri: str | None = config.get("uri")

        self._device = None

    # ---------- Lifecycle ----------

    def open(self) -> None:
        """
        Open Pluto SDR and apply configuration.
        """
        try:
            import adi
        except ImportError as exc:
            raise RuntimeError(
                "Pluto SDR library not installed. Install pyadi-iio."
            ) from exc

        if self.uri:
            self._device = adi.ad9361(uri=self.uri)
        else:
            self._device = adi.ad9361()

        # Configuration
        self._device.sample_rate = int(self.sample_rate)
        self._device.rx_lo = int(self.center_frequency)
        self._device.rx_rf_bandwidth = int(self.bandwidth)

        # Gain control
        self._device.rx_hardwaregain_ctrl_en = True
        self._device.rx_hardwaregain = float(self.rx_gain)

        self._running = False

    def close(self) -> None:
        """
        Close Pluto SDR.
        """
        self._device = None
        self._running = False

    # ---------- Streaming ----------

    def start(self) -> None:
        if not self._device:
            raise RuntimeError("Pluto SDR not opened")
        super().start()

    def stop(self) -> None:
        super().stop()

    def read_samples(self, num_samples: int) -> np.ndarray:
        """
        Read complex IQ samples from Pluto SDR.

        Returns
        -------
        samples : np.ndarray (complex64)
        """
        if not self._running:
            raise RuntimeError("Pluto SDR streaming not started")

        # pyadi-iio returns complex numpy array
        samples = self._device.rx(num_samples)

        return np.asarray(samples, dtype=np.complex64)

    # ---------- Status ----------

    def status(self) -> Dict[str, Any]:
        return {
            "device": "ADALM-Pluto",
            "running": self._running,
            "sample_rate": self.sample_rate,
            "center_frequency": self.center_frequency,
            "bandwidth": self.bandwidth,
            "rx_gain": self.rx_gain,
            "uri": self.uri,
        }
