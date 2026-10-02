"""
drone-detector/domain/algorithms/ml_classifier.py
ML Classifier (Domain Layer)

Tanggung jawab:
- Menyediakan interface klasifikasi sinyal berbasis fitur
- Menghasilkan label + confidence

Tidak mengandung:
- Model loading (pickle, torch, onnx)
- Training logic
- Hardware / file I/O
"""

from typing import Dict, List, Optional, Tuple
import numpy as np


class MLClassifier:
    """
    Abstract ML classifier interface.
    Implementasi konkrit ada di infrastructure layer.
    """

    def predict(self, features: Dict[str, float]) -> Tuple[str, float]:
        """
        Return (label, confidence).
        """
        raise NotImplementedError


def extract_features(
    psd: np.ndarray,
    peaks: List[int],
) -> Dict[str, float]:
    """
    Ekstraksi fitur sederhana dari PSD & peaks.
    """
    if psd.size == 0:
        return {}

    features = {
        "peak_count": float(len(peaks)),
        "mean_power": float(np.mean(psd)),
        "max_power": float(np.max(psd)),
        "power_variance": float(np.var(psd)),
    }

    if peaks:
        peak_powers = [psd[p] for p in peaks]
        features.update(
            {
                "peak_mean_power": float(np.mean(peak_powers)),
                "peak_max_power": float(np.max(peak_powers)),
            }
        )

    return features


def classify_signal(
    psd: np.ndarray,
    peaks: List[int],
    classifier: Optional[MLClassifier] = None,
) -> Optional[str]:
    """
    Klasifikasi sinyal menggunakan ML classifier (jika tersedia).

    Parameters
    ----------
    psd : np.ndarray
        Power spectral density
    peaks : List[int]
        Indeks peak
    classifier : Optional[MLClassifier]
        Instance classifier (di-inject dari luar)

    Returns
    -------
    label : Optional[str]
        Label hasil klasifikasi
    """
    if classifier is None:
        return None

    features = extract_features(psd, peaks)
    if not features:
        return None

    label, confidence = classifier.predict(features)

    # Confidence gating
    if confidence < 0.5:
        return None

    return label
