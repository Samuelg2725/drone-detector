import numpy as np
from domain.algorithms.fft import compute_fft


def test_fft_output_size(iq_samples):
    fft = compute_fft(iq_samples)
    assert len(fft) == len(iq_samples)


def test_fft_not_nan(iq_samples):
    fft = compute_fft(iq_samples)
    assert not np.isnan(np.abs(fft)).any()
