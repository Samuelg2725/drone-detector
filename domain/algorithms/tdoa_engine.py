#!/usr/bin/env python3
# drone-detector/domain/algorithms/tdoa_engine.py
"""
TDOA (Time Difference of Arrival) Multilateration Engine

This module implements Time Difference of Arrival positioning for drone detection
using multiple synchronized receivers. TDOA allows geolocation of RF signals
by measuring the time difference of the same signal arriving at different
receivers.

Key features:
- 2D and 3D position estimation
- Hyperbolic multilateration
- Chan's algorithm for closed-form solution
- Taylor series iterative refinement
- Cramer-Rao lower bound calculation
- GDOP (Geometric Dilution of Precision) analysis
- Kalman filtering for trajectory smoothing
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import warnings
from scipy.optimize import minimize, least_squares
from scipy.linalg import lstsq, pinv, svd
from scipy.spatial.distance import cdist

# For Kalman filter
from dataclasses import dataclass


# ============================================================================
# Enums and Data Classes
# ============================================================================

class TDOAMethod(Enum):
    """TDOA solution methods"""
    CHAN_2D = "chan_2d"           # Chan's method for 2D
    CHAN_3D = "chan_3d"           # Chan's method for 3D
    FANG = "fang"                 # Fang's method
    FRIEDLANDER = "friedlander"   # Friedlander's method
    TAYLOR = "taylor"             # Taylor series iteration
    LEAST_SQUARES = "least_squares"  # Non-linear least squares
    HYPERTRIL = "hypertril"       # Hyperbolic trilateration


class TDOADimension(Enum):
    """Position dimension"""
    D2 = 2  # 2D position (latitude, longitude)
    D3 = 3  # 3D position (latitude, longitude, altitude)


@dataclass
class Receiver:
    """Receiver/Sensor position and timing parameters"""
    id: str
    name: str
    position: np.ndarray  # [x, y, z] in meters (ECEF or local coordinates)
    clock_offset: float = 0.0  # Clock offset in seconds
    clock_drift: float = 0.0  # Clock drift (ppm)
    position_error: float = 0.0  # Position uncertainty in meters
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position.tolist(),
            'clock_offset': self.clock_offset,
            'clock_drift': self.clock_drift,
            'position_error': self.position_error
        }


@dataclass
class TDOAMeasurement:
    """TDOA measurement from a pair of receivers"""
    receiver1_id: str
    receiver2_id: str
    tdoa: float  # Time difference in seconds (positive means signal arrived at receiver1 first)
    tdoa_error: float = 0.0  # Measurement uncertainty in seconds
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    correlation_quality: float = 1.0  # Cross-correlation quality (0-1)
    snr_db: float = 0.0  # Signal-to-noise ratio at receivers
    
    @property
    def distance_difference(self) -> float:
        """Convert TDOA to distance difference"""
        return self.tdoa * 299792458.0  # Speed of light in m/s
    
    @property
    def distance_difference_error(self) -> float:
        """Distance difference error in meters"""
        return self.tdoa_error * 299792458.0


@dataclass
class PositionEstimate:
    """Estimated position with uncertainty"""
    position: np.ndarray  # [x, y, z] in meters
    position_geodetic: Tuple[float, float, float]  # (lat, lon, alt) in degrees and meters
    covariance: np.ndarray  # Covariance matrix
    gdop: float  # Geometric Dilution of Precision
    pdop: float  # Position Dilution of Precision
    hdop: float  # Horizontal Dilution of Precision
    vdop: float  # Vertical Dilution of Precision
    residuals: np.ndarray  # Measurement residuals
    num_iterations: int = 0
    convergence: bool = True
    method_used: TDOAMethod = TDOAMethod.CHAN_2D
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'position': self.position.tolist(),
            'latitude': self.position_geodetic[0],
            'longitude': self.position_geodetic[1],
            'altitude': self.position_geodetic[2],
            'covariance': self.covariance.tolist() if self.covariance is not None else None,
            'gdop': self.gdop,
            'pdop': self.pdop,
            'hdop': self.hdop,
            'vdop': self.vdop,
            'residuals': self.residuals.tolist() if self.residuals is not None else None,
            'convergence': self.convergence,
            'method': self.method_used.value,
            'timestamp': self.timestamp
        }


@dataclass
class TDOAConfig:
    """Configuration for TDOA engine"""
    # Solution method
    default_method: TDOAMethod = TDOAMethod.CHAN_2D
    dimension: TDOADimension = TDOADimension.D2
    
    # Taylor series parameters
    taylor_max_iterations: int = 10
    taylor_convergence_threshold: float = 1e-6  # meters
    
    # Least squares parameters
    ls_method: str = 'trf'  # 'trf', 'dogbox', 'lm'
    ls_max_iterations: int = 100
    ls_tolerance: float = 1e-8
    
    # Kalman filter
    enable_kalman: bool = True
    kalman_process_noise: float = 1.0  # m/s^2
    kalman_measurement_noise: float = 10.0  # meters
    
    # Validation
    min_receivers: int = 3  # Minimum receivers for 2D, 4 for 3D
    max_residual_threshold: float = 100.0  # meters
    max_gdop_threshold: float = 10.0
    
    # Reference
    reference_receiver_id: Optional[str] = None  # If None, uses receiver with best SNR
    
    # Environmental
    speed_of_light: float = 299792458.0  # m/s


# ============================================================================
# Coordinate Conversion Utilities
# ============================================================================

class CoordinateConverter:
    """Coordinate system conversions for TDOA"""
    
    # WGS84 ellipsoid constants
    WGS84_A = 6378137.0  # Semi-major axis (meters)
    WGS84_B = 6356752.314245  # Semi-minor axis (meters)
    WGS84_E2 = 1 - (WGS84_B**2 / WGS84_A**2)  # Eccentricity squared
    WGS84_F = 1 / 298.257223563  # Flattening
    
    @staticmethod
    def ecef_to_geodetic(x: float, y: float, z: float) -> Tuple[float, float, float]:
        """
        Convert ECEF coordinates to geodetic (latitude, longitude, altitude)
        
        Args:
            x, y, z: ECEF coordinates in meters
            
        Returns:
            (latitude in degrees, longitude in degrees, altitude in meters)
        """
        # Longitude
        lon = np.arctan2(y, x)
        
        # Latitude (iterative)
        p = np.sqrt(x**2 + y**2)
        lat = np.arctan2(z, p * (1 - CoordinateConverter.WGS84_E2))
        
        for _ in range(10):
            N = CoordinateConverter.WGS84_A / np.sqrt(1 - CoordinateConverter.WGS84_E2 * np.sin(lat)**2)
            h = p / np.cos(lat) - N
            lat_new = np.arctan2(z, p * (1 - CoordinateConverter.WGS84_E2 * N / (N + h)))
            
            if abs(lat_new - lat) < 1e-12:
                lat = lat_new
                break
            lat = lat_new
        
        # Altitude
        N = CoordinateConverter.WGS84_A / np.sqrt(1 - CoordinateConverter.WGS84_E2 * np.sin(lat)**2)
        alt = p / np.cos(lat) - N
        
        return (np.degrees(lat), np.degrees(lon), alt)
    
    @staticmethod
    def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[float, float, float]:
        """
        Convert geodetic coordinates to ECEF
        
        Args:
            lat_deg: Latitude in degrees
            lon_deg: Longitude in degrees
            alt_m: Altitude in meters
            
        Returns:
            (x, y, z) ECEF coordinates in meters
        """
        lat = np.radians(lat_deg)
        lon = np.radians(lon_deg)
        
        N = CoordinateConverter.WGS84_A / np.sqrt(1 - CoordinateConverter.WGS84_E2 * np.sin(lat)**2)
        
        x = (N + alt_m) * np.cos(lat) * np.cos(lon)
        y = (N + alt_m) * np.cos(lat) * np.sin(lon)
        z = (N * (1 - CoordinateConverter.WGS84_E2) + alt_m) * np.sin(lat)
        
        return (x, y, z)
    
    @staticmethod
    def local_to_ecef(origin_lat_deg: float, origin_lon_deg: float, 
                      origin_alt_m: float, local_x: float, 
                      local_y: float, local_z: float) -> Tuple[float, float, float]:
        """
        Convert local ENU coordinates to ECEF
        
        Args:
            origin_lat_deg, origin_lon_deg, origin_alt_m: Reference point
            local_x, local_y, local_z: East, North, Up coordinates
            
        Returns:
            (x, y, z) ECEF coordinates
        """
        # Get ECEF of origin
        xe, ye, ze = CoordinateConverter.geodetic_to_ecef(
            origin_lat_deg, origin_lon_deg, origin_alt_m
        )
        
        # Rotation matrix from ENU to ECEF
        lat = np.radians(origin_lat_deg)
        lon = np.radians(origin_lon_deg)
        
        R = np.array([
            [-np.sin(lon), -np.sin(lat) * np.cos(lon), np.cos(lat) * np.cos(lon)],
            [np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat) * np.sin(lon)],
            [0, np.cos(lat), np.sin(lat)]
        ])
        
        enu = np.array([local_x, local_y, local_z])
        delta = R @ enu
        
        return (xe + delta[0], ye + delta[1], ze + delta[2])


# ============================================================================
# TDOA Algorithms
# ============================================================================

class ChanMethod:
    """
    Chan's method for TDOA localization.
    Closed-form solution that is efficient and accurate for moderate noise.
    """
    
    @staticmethod
    def solve_2d(receiver_positions: np.ndarray, distance_differences: np.ndarray,
                 reference_idx: int = 0) -> Optional[np.ndarray]:
        """
        Chan's method for 2D positioning (x, y)
        
        Args:
            receiver_positions: (N, 2) array of receiver positions [x, y]
            distance_differences: (N-1,) array of distance differences relative to reference
            reference_idx: Index of reference receiver
            
        Returns:
            (2,) array of estimated position [x, y] or None if failed
        """
        try:
            N = len(receiver_positions)
            M = N - 1
            
            # Reference position
            x_ref, y_ref = receiver_positions[reference_idx]
            
            # Build matrix
            K = np.zeros((M, M))
            h = np.zeros(M)
            
            for i in range(M):
                idx = i if i < reference_idx else i + 1
                xi, yi = receiver_positions[idx]
                
                # Distance from reference
                ri1 = distance_differences[i]
                
                # Equation: xi^2 + yi^2 - x_ref^2 - y_ref^2
                Ki = xi**2 + yi**2 - x_ref**2 - y_ref**2
                
                h[i] = 0.5 * (ri1**2 - Ki)
                
                for j in range(M):
                    jdx = j if j < reference_idx else j + 1
                    xj, yj = receiver_positions[jdx]
                    
                    K[i, j] = (xi - x_ref) * (xj - x_ref) + (yi - y_ref) * (yj - y_ref)
            
            # First estimation
            pos1 = np.linalg.solve(K, h)
            
            # Second step using weighted least squares
            # Calculate distances from first estimate
            dist1 = np.sqrt((pos1[0] - x_ref)**2 + (pos1[1] - y_ref)**2)
            
            # Construct B matrix
            B = np.diag(distance_differences)
            
            # Covariance matrix (simplified - assuming equal variance)
            Q = np.eye(M)
            
            # Weighted least squares solution
            K2 = K.T @ np.linalg.inv(B @ Q @ B) @ K
            h2 = K.T @ np.linalg.inv(B @ Q @ B) @ h
            
            pos2 = np.linalg.solve(K2, h2)
            
            # Quadratic correction
            x_est, y_est = pos2[0] + x_ref, pos2[1] + y_ref
            
            return np.array([x_est, y_est])
            
        except np.linalg.LinAlgError:
            return None
    
    @staticmethod
    def solve_3d(receiver_positions: np.ndarray, distance_differences: np.ndarray,
                 reference_idx: int = 0) -> Optional[np.ndarray]:
        """
        Chan's method for 3D positioning (x, y, z)
        
        Args:
            receiver_positions: (N, 3) array of receiver positions [x, y, z]
            distance_differences: (N-1,) array of distance differences relative to reference
            reference_idx: Index of reference receiver
            
        Returns:
            (3,) array of estimated position [x, y, z] or None if failed
        """
        try:
            N = len(receiver_positions)
            M = N - 1
            
            if M < 3:
                return None
            
            # Reference position
            pos_ref = receiver_positions[reference_idx]
            x_ref, y_ref, z_ref = pos_ref
            
            # Build matrices
            Ga = np.zeros((M, 3))
            h = np.zeros(M)
            
            for i in range(M):
                idx = i if i < reference_idx else i + 1
                xi, yi, zi = receiver_positions[idx]
                ri1 = distance_differences[i]
                
                Ga[i] = [xi - x_ref, yi - y_ref, zi - z_ref]
                h[i] = 0.5 * (ri1**2 - (xi**2 + yi**2 + zi**2) + (x_ref**2 + y_ref**2 + z_ref**2))
            
            # Least squares solution
            pos1 = np.linalg.lstsq(Ga, h, rcond=None)[0]
            
            # Second step with weighting
            dist1 = np.sqrt(np.sum((pos1)**2))
            B = np.diag(distance_differences)
            Q = np.eye(M)
            
            # Weighted least squares
            W = np.linalg.inv(B @ Q @ B)
            pos2 = np.linalg.solve(Ga.T @ W @ Ga, Ga.T @ W @ h)
            
            x_est, y_est, z_est = pos2[0] + x_ref, pos2[1] + y_ref, pos2[2] + z_ref
            
            return np.array([x_est, y_est, z_est])
            
        except np.linalg.LinAlgError:
            return None


class TaylorSeriesMethod:
    """
    Taylor series iteration method for TDOA localization.
    Iterative refinement that provides higher accuracy but requires initial guess.
    """
    
    @staticmethod
    def solve(receiver_positions: np.ndarray, distance_differences: np.ndarray,
              initial_guess: np.ndarray, reference_idx: int = 0,
              max_iterations: int = 10, convergence_threshold: float = 1e-6) -> Tuple[Optional[np.ndarray], int]:
        """
        Taylor series iteration method
        
        Returns:
            (estimated_position, num_iterations) or (None, iterations)
        """
        N = len(receiver_positions)
        M = N - 1
        
        pos = initial_guess.copy()
        
        for iteration in range(max_iterations):
            # Build matrices
            H = np.zeros((M, len(pos)))
            delta_d = np.zeros(M)
            
            for i in range(M):
                idx = i if i < reference_idx else i + 1
                receiver_pos = receiver_positions[idx]
                
                # Calculated distances
                dist_src = np.linalg.norm(receiver_pos - pos)
                dist_ref = np.linalg.norm(receiver_positions[reference_idx] - pos)
                calc_diff = dist_src - dist_ref
                
                # Residual
                delta_d[i] = distance_differences[i] - calc_diff
                
                # Derivatives
                for j in range(len(pos)):
                    H[i, j] = (receiver_pos[j] - pos[j]) / dist_src - \
                              (receiver_positions[reference_idx][j] - pos[j]) / dist_ref
            
            # Solve for delta
            try:
                delta = np.linalg.lstsq(H, delta_d, rcond=None)[0]
            except np.linalg.LinAlgError:
                return None, iteration
            
            # Update position
            pos = pos + delta
            
            # Check convergence
            if np.linalg.norm(delta) < convergence_threshold:
                return pos, iteration + 1
        
        return pos, max_iterations


class LeastSquaresMethod:
    """
    Non-linear least squares optimization for TDOA.
    Most accurate but computationally intensive.
    """
    
    @staticmethod
    def solve(receiver_positions: np.ndarray, distance_differences: np.ndarray,
              initial_guess: np.ndarray, reference_idx: int = 0,
              method: str = 'trf', max_iterations: int = 100,
              tolerance: float = 1e-8) -> Optional[np.ndarray]:
        """
        Non-linear least squares solution
        
        Args:
            receiver_positions: (N, D) array of receiver positions
            distance_differences: (N-1,) array of distance differences
            initial_guess: (D,) initial position estimate
            reference_idx: Index of reference receiver
            method: Optimization method ('trf', 'dogbox', 'lm')
            max_iterations: Maximum iterations
            tolerance: Convergence tolerance
            
        Returns:
            Estimated position or None
        """
        
        def residuals(pos, *args):
            """Residual function for optimization"""
            receivers, ref_idx, measured_diffs = args
            ref_pos = receivers[ref_idx]
            
            residuals_list = []
            for i, receiver in enumerate(receivers):
                if i == ref_idx:
                    continue
                
                # Calculated distance difference
                dist_src = np.linalg.norm(receiver - pos)
                dist_ref = np.linalg.norm(ref_pos - pos)
                calc_diff = dist_src - dist_ref
                
                # Index in measured_diffs
                idx = i if i < ref_idx else i - 1
                residuals_list.append(measured_diffs[idx] - calc_diff)
            
            return np.array(residuals_list)
        
        try:
            result = least_squares(
                residuals, initial_guess,
                args=(receiver_positions, reference_idx, distance_differences),
                method=method,
                max_nfev=max_iterations,
                ftol=tolerance,
                xtol=tolerance,
                gtol=tolerance,
                verbose=0
            )
            
            if result.success:
                return result.x
            else:
                return None
                
        except Exception:
            return None


# ============================================================================
# GDOP and Dilution of Precision
# ============================================================================

class DOPCalculator:
    """Calculate Dilution of Precision metrics"""
    
    @staticmethod
    def compute_gdop(receiver_positions: np.ndarray, source_position: np.ndarray) -> float:
        """
        Compute Geometric Dilution of Precision
        
        Args:
            receiver_positions: (N, 3) array of receiver positions
            source_position: (3,) estimated source position
            
        Returns:
            GDOP value (lower is better)
        """
        N = len(receiver_positions)
        H = np.zeros((N, 3))
        
        for i, rec_pos in enumerate(receiver_positions):
            dist = np.linalg.norm(rec_pos - source_position)
            if dist > 0:
                H[i] = (source_position - rec_pos) / dist
        
        try:
            Q = np.linalg.inv(H.T @ H)
            gdop = np.sqrt(np.trace(Q))
            return gdop
        except np.linalg.LinAlgError:
            return float('inf')
    
    @staticmethod
    def compute_all_dops(receiver_positions: np.ndarray, source_position: np.ndarray) -> Tuple[float, float, float, float]:
        """
        Compute all DOP metrics
        
        Returns:
            (GDOP, PDOP, HDOP, VDOP)
        """
        N = len(receiver_positions)
        H = np.zeros((N, 3))
        
        for i, rec_pos in enumerate(receiver_positions):
            dist = np.linalg.norm(rec_pos - source_position)
            if dist > 0:
                H[i] = (source_position - rec_pos) / dist
        
        try:
            Q = np.linalg.inv(H.T @ H)
            gdop = np.sqrt(np.trace(Q))
            pdop = np.sqrt(Q[0, 0] + Q[1, 1] + Q[2, 2])
            hdop = np.sqrt(Q[0, 0] + Q[1, 1])
            vdop = np.sqrt(Q[2, 2])
            
            return (gdop, pdop, hdop, vdop)
        except np.linalg.LinAlgError:
            return (float('inf'), float('inf'), float('inf'), float('inf'))
    
    @staticmethod
    def compute_cramer_rao_bound(receiver_positions: np.ndarray, source_position: np.ndarray,
                                  tdoa_error_std: float) -> np.ndarray:
        """
        Compute Cramer-Rao Lower Bound for position estimate
        
        Args:
            receiver_positions: (N, 3) receiver positions
            source_position: (3,) source position
            tdoa_error_std: Standard deviation of TDOA measurements (meters)
            
        Returns:
            (3, 3) covariance lower bound matrix
        """
        c = 299792458.0  # Speed of light
        N = len(receiver_positions)
        
        # Build Jacobian matrix
        H = np.zeros((N - 1, 3))
        ref_pos = receiver_positions[0]
        
        for i in range(1, N):
            dist_src = np.linalg.norm(receiver_positions[i] - source_position)
            dist_ref = np.linalg.norm(ref_pos - source_position)
            
            if dist_src > 0 and dist_ref > 0:
                H[i-1] = (receiver_positions[i] - source_position) / dist_src - \
                         (ref_pos - source_position) / dist_ref
        
        # FIM (Fisher Information Matrix)
        FIM = H.T @ H / (tdoa_error_std**2)
        
        try:
            crlb = np.linalg.inv(FIM)
            return crlb
        except np.linalg.LinAlgError:
            return np.eye(3) * float('inf')


# ============================================================================
# Kalman Filter for Trajectory Smoothing
# ============================================================================

class TDOAKalmanFilter:
    """
    Kalman filter for smoothing TDOA position estimates over time
    """
    
    def __init__(self, dt: float = 0.1, process_noise: float = 1.0,
                 measurement_noise: float = 10.0, dimension: int = 2):
        """
        Initialize Kalman filter
        
        Args:
            dt: Time step in seconds
            process_noise: Process noise covariance scaling (m/s^2)
            measurement_noise: Measurement noise covariance (meters)
            dimension: 2 or 3 for position dimension
        """
        self.dt = dt
        self.dim = dimension
        self.state_size = dimension * 2  # position + velocity
        self.measurement_size = dimension
        
        # State vector [x, y, z, vx, vy, vz]
        self.x = np.zeros(self.state_size)
        
        # State covariance
        self.P = np.eye(self.state_size) * 100.0
        
        # State transition matrix
        self.F = np.eye(self.state_size)
        for i in range(dimension):
            self.F[i, i + dimension] = dt
        
        # Process noise covariance
        q_pos = process_noise * dt**4 / 4
        q_vel = process_noise * dt**2 / 2
        self.Q = np.zeros((self.state_size, self.state_size))
        for i in range(dimension):
            self.Q[i, i] = q_pos
            self.Q[i + dimension, i + dimension] = q_vel
        
        # Measurement matrix
        self.H = np.zeros((self.measurement_size, self.state_size))
        for i in range(dimension):
            self.H[i, i] = 1
        
        # Measurement noise covariance
        self.R = np.eye(self.measurement_size) * measurement_noise
        
        self.initialized = False
    
    def predict(self) -> np.ndarray:
        """Prediction step"""
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.get_position()
    
    def update(self, measurement: np.ndarray) -> np.ndarray:
        """Update step with measurement"""
        # Innovation
        y = measurement - self.H @ self.x
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # State update
        self.x = self.x + K @ y
        
        # Covariance update
        self.P = (np.eye(self.state_size) - K @ self.H) @ self.P
        
        return self.get_position()
    
    def filter_measurement(self, measurement: np.ndarray) -> np.ndarray:
        """Apply Kalman filter to a single measurement"""
        if not self.initialized:
            # Initialize state from first measurement
            self.x[:self.dim] = measurement
            self.x[self.dim:] = 0  # Initial velocity = 0
            self.initialized = True
            return measurement
        
        self.predict()
        return self.update(measurement)
    
    def get_position(self) -> np.ndarray:
        """Get current position estimate"""
        return self.x[:self.dim]
    
    def get_velocity(self) -> np.ndarray:
        """Get current velocity estimate"""
        return self.x[self.dim:]
    
    def get_covariance(self) -> np.ndarray:
        """Get position covariance"""
        return self.P[:self.dim, :self.dim]
    
    def reset(self):
        """Reset filter state"""
        self.x = np.zeros(self.state_size)
        self.P = np.eye(self.state_size) * 100.0
        self.initialized = False


# ============================================================================
# Main TDOA Engine
# ============================================================================

class TDOAEngine:
    """
    Main TDOA Multilateration Engine
    
    This class orchestrates TDOA positioning using multiple receivers.
    It supports various algorithms, provides uncertainty metrics, and
    includes Kalman filtering for trajectory smoothing.
    """
    
    def __init__(self, config: Optional[TDOAConfig] = None):
        """
        Initialize TDOA engine
        
        Args:
            config: Configuration object (uses defaults if None)
        """
        self.config = config or TDOAConfig()
        self.receivers: Dict[str, Receiver] = {}
        self.measurements: List[TDOAMeasurement] = []
        self.last_estimate: Optional[PositionEstimate] = None
        self.kalman_filter: Optional[TDOAKalmanFilter] = None
        
        # Coordinate converter
        self.coord_converter = CoordinateConverter()
        
        # Statistics
        self.stats = {
            'total_estimates': 0,
            'converged_estimates': 0,
            'failed_estimates': 0,
            'avg_gdop': 0.0,
            'avg_residual': 0.0
        }
    
    def add_receiver(self, receiver: Receiver) -> None:
        """Add or update a receiver"""
        self.receivers[receiver.id] = receiver
        
        # Sort receivers by name for consistent ordering
        self._sorted_receivers = None
    
    def remove_receiver(self, receiver_id: str) -> None:
        """Remove a receiver"""
        if receiver_id in self.receivers:
            del self.receivers[receiver_id]
            self._sorted_receivers = None
    
    def get_receiver(self, receiver_id: str) -> Optional[Receiver]:
        """Get receiver by ID"""
        return self.receivers.get(receiver_id)
    
    def get_all_receivers(self) -> List[Receiver]:
        """Get all receivers"""
        return list(self.receivers.values())
    
    def set_measurements(self, measurements: List[TDOAMeasurement]) -> None:
        """Set TDOA measurements"""
        self.measurements = measurements
    
    def add_measurement(self, measurement: TDOAMeasurement) -> None:
        """Add a single TDOA measurement"""
        self.measurements.append(measurement)
    
    def compute_position(self, initial_guess: Optional[np.ndarray] = None,
                        method: Optional[TDOAMethod] = None,
                        reference_receiver_id: Optional[str] = None) -> Optional[PositionEstimate]:
        """
        Compute position from TDOA measurements
        
        Args:
            initial_guess: Initial position guess (optional, uses centroid if None)
            method: Solution method override
            reference_receiver_id: Reference receiver override
            
        Returns:
            PositionEstimate object or None if failed
        """
        # Validate we have enough measurements
        if len(self.measurements) < self.config.min_receivers - 1:
            return None
        
        # Get receivers involved
        receiver_ids = set()
        for m in self.measurements:
            receiver_ids.add(m.receiver1_id)
            receiver_ids.add(m.receiver2_id)
        
        # Ensure we have all receivers
        for rid in receiver_ids:
            if rid not in self.receivers:
                return None
        
        # Select reference receiver
        ref_id = reference_receiver_id or self.config.reference_receiver_id
        if ref_id is None or ref_id not in receiver_ids:
            # Use receiver with best SNR (highest average)
            ref_id = self._select_best_reference(receiver_ids)
        
        # Build receiver position array and distance differences
        receiver_list = sorted(receiver_ids)
        ref_idx = receiver_list.index(ref_id)
        
        # Get dimension from config
        dim = 2 if self.config.dimension == TDOADimension.D2 else 3
        
        # Build position array
        positions = np.zeros((len(receiver_list), dim))
        for i, rid in enumerate(receiver_list):
            receiver = self.receivers[rid]
            positions[i, :dim] = receiver.position[:dim]
        
        # Build distance differences
        M = len(receiver_list) - 1
        distance_diffs = np.zeros(M)
        quality_weights = np.ones(M)
        
        for i, rid in enumerate(receiver_list):
            if rid == ref_id:
                continue
            
            # Find measurement between rid and ref_id
            for m in self.measurements:
                if (m.receiver1_id == rid and m.receiver2_id == ref_id):
                    idx = i if i < ref_idx else i - 1
                    distance_diffs[idx] = m.distance_difference
                    quality_weights[idx] = m.correlation_quality
                    break
                elif (m.receiver1_id == ref_id and m.receiver2_id == rid):
                    idx = i if i < ref_idx else i - 1
                    distance_diffs[idx] = -m.distance_difference
                    quality_weights[idx] = m.correlation_quality
                    break
        
        # Apply quality weighting
        distance_diffs = distance_diffs * quality_weights
        
        # Determine which method to use
        if method is None:
            method = self.config.default_method
        
        # Compute position
        position = None
        iterations = 0
        
        if method == TDOAMethod.CHAN_2D and dim == 2:
            position = ChanMethod.solve_2d(positions, distance_diffs, ref_idx)
            
        elif method == TDOAMethod.CHAN_3D and dim == 3:
            position = ChanMethod.solve_3d(positions, distance_diffs, ref_idx)
            
        elif method == TDOAMethod.TAYLOR:
            if initial_guess is None:
                # Use Chan's method as initial guess
                if dim == 2:
                    initial_guess = ChanMethod.solve_2d(positions, distance_diffs, ref_idx)
                else:
                    initial_guess = ChanMethod.solve_3d(positions, distance_diffs, ref_idx)
            
            if initial_guess is not None:
                position, iterations = TaylorSeriesMethod.solve(
                    positions, distance_diffs, initial_guess, ref_idx,
                    self.config.taylor_max_iterations,
                    self.config.taylor_convergence_threshold
                )
                
        elif method == TDOAMethod.LEAST_SQUARES:
            if initial_guess is None:
                if dim == 2:
                    initial_guess = ChanMethod.solve_2d(positions, distance_diffs, ref_idx)
                else:
                    initial_guess = ChanMethod.solve_3d(positions, distance_diffs, ref_idx)
            
            if initial_guess is not None:
                position = LeastSquaresMethod.solve(
                    positions, distance_diffs, initial_guess, ref_idx,
                    self.config.ls_method, self.config.ls_max_iterations,
                    self.config.ls_tolerance
                )
        
        if position is None:
            self.stats['failed_estimates'] += 1
            return None
        
        # Convert to full 3D if needed
        if dim == 2:
            position_3d = np.array([position[0], position[1], 0.0])
        else:
            position_3d = position
        
        # Convert to geodetic
        lat, lon, alt = self.coord_converter.ecef_to_geodetic(
            position_3d[0], position_3d[1], position_3d[2]
        )
        
        # Compute DOPs
        gdop, pdop, hdop, vdop = DOPCalculator.compute_all_dops(
            positions, position_3d[:3] if dim == 2 else position_3d
        )
        
        # Compute residuals
        residuals = self._compute_residuals(position_3d, receiver_list, ref_id)
        
        # Compute covariance
        if dim == 2:
            cov = np.eye(2) * (residuals.std() if len(residuals) > 0 else 100.0)
        else:
            cov = np.eye(3) * (residuals.std() if len(residuals) > 0 else 100.0)
        
        # Create position estimate
        estimate = PositionEstimate(
            position=position_3d,
            position_geodetic=(lat, lon, alt),
            covariance=cov,
            gdop=gdop,
            pdop=pdop,
            hdop=hdop,
            vdop=vdop,
            residuals=residuals,
            num_iterations=iterations,
            convergence=not np.any(np.isnan(position)),
            method_used=method
        )
        
        # Apply Kalman filter if enabled
        if self.config.enable_kalman:
            estimate = self._apply_kalman_filter(estimate)
        
        # Update statistics
        self.stats['total_estimates'] += 1
        if estimate.convergence:
            self.stats['converged_estimates'] += 1
        self.stats['avg_gdop'] = (self.stats['avg_gdop'] * (self.stats['total_estimates'] - 1) + gdop) / self.stats['total_estimates']
        self.stats['avg_residual'] = (self.stats['avg_residual'] * (self.stats['total_estimates'] - 1) + np.mean(residuals)) / self.stats['total_estimates']
        
        self.last_estimate = estimate
        
        return estimate
    
    def _compute_residuals(self, position: np.ndarray, receiver_ids: List[str],
                          reference_id: str) -> np.ndarray:
        """Compute measurement residuals"""
        residuals = []
        ref_pos = self.receivers[reference_id].position
        
        for rid in receiver_ids:
            if rid == reference_id:
                continue
            
            rec_pos = self.receivers[rid].position
            calc_diff = np.linalg.norm(rec_pos - position) - np.linalg.norm(ref_pos - position)
            
            # Find measured difference
            measured_diff = None
            for m in self.measurements:
                if (m.receiver1_id == rid and m.receiver2_id == reference_id):
                    measured_diff = m.distance_difference
                    break
                elif (m.receiver1_id == reference_id and m.receiver2_id == rid):
                    measured_diff = -m.distance_difference
                    break
            
            if measured_diff is not None:
                residual = measured_diff - calc_diff
                residuals.append(residual)
        
        return np.array(residuals)
    
    def _select_best_reference(self, receiver_ids: set) -> str:
        """Select best reference receiver based on SNR"""
        best_id = None
        best_snr = -float('inf')
        
        for rid in receiver_ids:
            # Calculate average SNR for measurements involving this receiver
            snr_sum = 0
            count = 0
            for m in self.measurements:
                if m.receiver1_id == rid or m.receiver2_id == rid:
                    snr_sum += m.snr_db
                    count += 1
            
            if count > 0:
                avg_snr = snr_sum / count
                if avg_snr > best_snr:
                    best_snr = avg_snr
                    best_id = rid
        
        return best_id if best_id else next(iter(receiver_ids))
    
    def _apply_kalman_filter(self, estimate: PositionEstimate) -> PositionEstimate:
        """Apply Kalman filter to smooth position estimates"""
        # Initialize Kalman filter on first use
        if self.kalman_filter is None:
            dim = 2 if self.config.dimension == TDOADimension.D2 else 3
            self.kalman_filter = TDOAKalmanFilter(
                dt=0.1,  # Time step - should be configurable
                process_noise=self.config.kalman_process_noise,
                measurement_noise=self.config.kalman_measurement_noise,
                dimension=dim
            )
        
        # Apply filter
        measurement = estimate.position[:self.kalman_filter.dim]
        filtered_pos = self.kalman_filter.filter_measurement(measurement)
        
        # Create new position with filtered coordinates
        if self.kalman_filter.dim == 2:
            filtered_pos_3d = np.array([filtered_pos[0], filtered_pos[1], estimate.position[2]])
        else:
            filtered_pos_3d = filtered_pos
        
        # Update geodetic coordinates
        lat, lon, alt = self.coord_converter.ecef_to_geodetic(
            filtered_pos_3d[0], filtered_pos_3d[1], filtered_pos_3d[2]
        )
        
        estimate.position = filtered_pos_3d
        estimate.position_geodetic = (lat, lon, alt)
        
        return estimate
    
    def get_covariance_ellipse(self, confidence: float = 0.95) -> Dict[str, Any]:
        """Get error ellipse parameters for 2D position"""
        if self.last_estimate is None:
            return {}
        
        if self.last_estimate.covariance.shape[0] < 2:
            return {}
        
        # Extract 2x2 covariance
        cov_2d = self.last_estimate.covariance[:2, :2]
        
        # Eigen decomposition
        eigvals, eigvecs = np.linalg.eigh(cov_2d)
        
        # Sort eigenvalues
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]
        
        # Chi-squared quantile for confidence
        from scipy.stats import chi2
        chi2_val = chi2.ppf(confidence, df=2)
        
        # Semi-major and semi-minor axes
        major_axis = np.sqrt(eigvals[0] * chi2_val)
        minor_axis = np.sqrt(eigvals[1] * chi2_val)
        
        # Orientation angle
        orientation = np.arctan2(eigvecs[1, 0], eigvecs[0, 0])
        
        return {
            'center': self.last_estimate.position[:2].tolist(),
            'major_axis': major_axis,
            'minor_axis': minor_axis,
            'orientation_deg': np.degrees(orientation),
            'area': np.pi * major_axis * minor_axis,
            'confidence': confidence
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            'success_rate': self.stats['converged_estimates'] / max(1, self.stats['total_estimates']) * 100,
            'num_receivers': len(self.receivers),
            'num_measurements': len(self.measurements),
            'enabled_filters': {
                'kalman': self.config.enable_kalman
            }
        }
    
    def reset(self) -> None:
        """Reset engine state"""
        self.measurements.clear()
        self.last_estimate = None
        self.kalman_filter = None
        self.stats = {
            'total_estimates': 0,
            'converged_estimates': 0,
            'failed_estimates': 0,
            'avg_gdop': 0.0,
            'avg_residual': 0.0
        }
    
    def validate_geometry(self) -> Dict[str, Any]:
        """Validate receiver geometry for TDOA"""
        if len(self.receivers) < 3:
            return {'valid': False, 'reason': 'Need at least 3 receivers'}
        
        # Get positions
        positions = np.array([r.position[:2] for r in self.receivers.values()])
        
        # Check if receivers are collinear
        if len(positions) >= 3:
            # Compute area of triangle
            area = 0.5 * abs(
                positions[0, 0] * (positions[1, 1] - positions[2, 1]) +
                positions[1, 0] * (positions[2, 1] - positions[0, 1]) +
                positions[2, 0] * (positions[0, 1] - positions[1, 1])
            )
            
            if area < 1.0:  # Less than 1 square meter
                return {'valid': False, 'reason': 'Receivers are nearly collinear'}
        
        # Check baseline distances
        distances = cdist(positions, positions)
        avg_distance = np.mean(distances[distances > 0])
        
        if avg_distance < 10:  # Less than 10 meters
            return {'valid': False, 'reason': f'Receivers too close (avg distance: {avg_distance:.1f}m)'}
        
        return {
            'valid': True,
            'num_receivers': len(self.receivers),
            'avg_baseline_m': avg_distance,
            'area_m2': area if len(positions) >= 3 else 0
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_tdoa_engine(receiver_positions: List[Tuple[float, float, float]],
                       receiver_ids: Optional[List[str]] = None,
                       config: Optional[TDOAConfig] = None) -> TDOAEngine:
    """
    Create and configure TDOA engine with receiver positions
    
    Args:
        receiver_positions: List of (x, y, z) positions in ECEF or local coordinates
        receiver_ids: Optional list of receiver IDs (default: 'rx0', 'rx1', ...)
        config: Optional configuration
        
    Returns:
        Configured TDOAEngine instance
    """
    engine = TDOAEngine(config)
    
    if receiver_ids is None:
        receiver_ids = [f"rx_{i}" for i in range(len(receiver_positions))]
    
    for rid, pos in zip(receiver_ids, receiver_positions):
        receiver = Receiver(
            id=rid,
            name=f"Receiver {rid}",
            position=np.array(pos)
        )
        engine.add_receiver(receiver)
    
    return engine


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    # Test TDOA engine with synthetic data
    import matplotlib.pyplot as plt
    
    print("TDOA Engine Test")
    print("=" * 50)
    
    # Define receiver positions (local coordinates in meters)
    receivers = [
        Receiver(id="rx1", name="Receiver 1", position=np.array([0, 0, 0])),
        Receiver(id="rx2", name="Receiver 2", position=np.array([100, 0, 0])),
        Receiver(id="rx3", name="Receiver 3", position=np.array([50, 86.6, 0])),
        Receiver(id="rx4", name="Receiver 4", position=np.array([0, 100, 0])),
    ]
    
    # Create engine
    engine = TDOAEngine(TDOAConfig(
        default_method=TDOAMethod.CHAN_2D,
        dimension=TDOADimension.D2,
        enable_kalman=True
    ))
    
    for rx in receivers:
        engine.add_receiver(rx)
    
    # Validate geometry
    geometry = engine.validate_geometry()
    print(f"Geometry validation: {geometry}")
    
    # True source position
    true_position = np.array([60, 50, 0])
    print(f"True position: {true_position}")
    
    # Simulate TDOA measurements
    c = 299792458.0
    measurements = []
    
    for i in range(1, len(receivers)):
        # Calculate true TDOA
        dist_src = np.linalg.norm(receivers[i].position - true_position)
        dist_ref = np.linalg.norm(receivers[0].position - true_position)
        tdoa_true = (dist_src - dist_ref) / c
        
        # Add noise
        tdoa_noise = np.random.normal(0, 1e-9)  # 1 ns noise
        tdoa = tdoa_true + tdoa_noise
        
        measurement = TDOAMeasurement(
            receiver1_id=receivers[i].id,
            receiver2_id=receivers[0].id,
            tdoa=tdoa,
            tdoa_error=1e-9,
            correlation_quality=0.9,
            snr_db=20
        )
        measurements.append(measurement)
    
    engine.set_measurements(measurements)
    
    # Compute position
    estimate = engine.compute_position()
    
    if estimate:
        print(f"\nEstimated position: {estimate.position[:2]}")
        print(f"Error: {np.linalg.norm(estimate.position[:2] - true_position[:2]):.2f} m")
        print(f"GDOP: {estimate.gdop:.2f}")
        print(f"HDOP: {estimate.hdop:.2f}")
        print(f"Residuals: {estimate.residuals}")
        
        # Get error ellipse
        ellipse = engine.get_covariance_ellipse(0.95)
        if ellipse:
            print(f"\n95% Error Ellipse:")
            print(f"  Major axis: {ellipse['major_axis']:.2f} m")
            print(f"  Minor axis: {ellipse['minor_axis']:.2f} m")
            print(f"  Orientation: {ellipse['orientation_deg']:.1f}°")
        
        # Statistics
        stats = engine.get_statistics()
        print(f"\nEngine Statistics: {stats}")
        
        # Plot results
        plt.figure(figsize=(10, 8))
        
        # Plot receivers
        rx_positions = np.array([r.position[:2] for r in receivers])
        plt.scatter(rx_positions[:, 0], rx_positions[:, 1], 
                   c='blue', s=100, marker='s', label='Receivers')
        
        # Plot true and estimated positions
        plt.scatter(true_position[0], true_position[1], 
                   c='green', s=200, marker='*', label='True Position')
        plt.scatter(estimate.position[0], estimate.position[1], 
                   c='red', s=150, marker='o', label='Estimated Position')
        
        # Plot error ellipse
        if ellipse:
            from matplotlib.patches import Ellipse
            ell = Ellipse(
                xy=ellipse['center'],
                width=2 * ellipse['major_axis'],
                height=2 * ellipse['minor_axis'],
                angle=ellipse['orientation_deg'],
                alpha=0.3,
                color='red',
                label='95% Error Ellipse'
            )
            plt.gca().add_patch(ell)
        
        plt.xlabel('X (meters)')
        plt.ylabel('Y (meters)')
        plt.title('TDOA Position Estimation')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.axis('equal')
        plt.show()
        
    else:
        print("Position estimation failed!")
    
    print("\n" + "=" * 50)
    print("TDOA Engine test complete")