import numpy as np
from domain.algorithms.peak_detection import detect_peaks


def test_detect_peaks_basic():
    psd = np.array([-90, -80, -30, -80, -90])
    peaks = detect_peaks(psd, threshold_db=-50)
    assert peaks == [2]
