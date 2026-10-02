"""Routes module for the Drone Detector API."""
from . import spectrum
from . import detection
from . import hardware
from . import system
from . import map
from . import analytics
from . import config
from . import auth

__all__ = [
    'spectrum',
    'detection',
    'hardware',
    'system',
    'map',
    'analytics',
    'config',
    'auth'
]
