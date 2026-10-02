"""Hardware adapters for SDR devices."""

import os
import logging

logger = logging.getLogger(__name__)

# Try to import hardware modules, but don't fail if they're missing
try:
    from .mock_hardware import MockSDR
except ImportError:
    logger.warning("MockSDR not available")
    MockSDR = None

try:
    from .hackrf import HackRFDevice
except ImportError:
    logger.debug("HackRF support not available (pyhackrf not installed)")
    HackRFDevice = None

try:
    from .rtl_sdr import RTLSDRDevice
except ImportError:
    logger.debug("RTL-SDR support not available (pyrtlsdr not installed)")
    RTLSDRDevice = None

__all__ = ['MockSDR', 'HackRFDevice', 'RTLSDRDevice']
