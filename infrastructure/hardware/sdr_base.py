# infrastructure/hardware/sdr_base.py
from abc import ABC, abstractmethod
import numpy as np

class SDRBase(ABC):
    """Abstract base class for SDR hardware interface"""
    
    @abstractmethod
    def initialize(self, config: dict):
        """Initialize SDR device with configuration"""
        pass
    
    @abstractmethod
    def tune(self, frequency: float):
        """Tune to specific frequency"""
        pass
    
    @abstractmethod
    def set_gain(self, gain_type: str, value: float):
        """Set gain for specific stage"""
        pass
    
    @abstractmethod
    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read IQ samples from device"""
        pass
    
    @abstractmethod
    def start_streaming(self):
        """Start continuous streaming mode"""
        pass
    
    @abstractmethod
    def stop_streaming(self):
        """Stop continuous streaming"""
        pass
    
    @abstractmethod
    def close(self):
        """Close device connection"""
        pass