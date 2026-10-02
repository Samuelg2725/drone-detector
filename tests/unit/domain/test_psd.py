import numpy as np
from domain.algorithms.psd import compute_psd


def test_psd_shape(iq_samples):
    psd = compute_psd(iq_samples)
    assert psd.shape[0] == iq_samples.shape[0]


def test_psd_reasonable_range(iq_samples):
    psd = compute_psd(iq_samples)
    assert psd.max() > psd.min()
