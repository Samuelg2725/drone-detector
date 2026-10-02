"""
drone-detector/app/pipelines.py
End-to-End Detection Pipeline

Tanggung jawab:
- Mengorkestrasi alur data dari IQ stream
- Memanggil algoritma domain (FFT, detection, ML)
- Mengirim event ke event bus
- Menyimpan hasil ke storage

Tidak boleh:
- Akses langsung ke hardware detail
- Logika UI / API
"""

from typing import Iterator

from app.startup import app_context

from domain.entities.signal import IQSignal
from domain.entities.detection import DetectionEvent

from domain.algorithms.fft import compute_fft
from domain.algorithms.psd import compute_psd
from domain.algorithms.peak_detection import detect_peaks
from domain.algorithms.pattern_matching import match_signature
from domain.algorithms.ml_classifier import classify_signal
from domain.policies.threat_assessment import assess_threat


def run_detection_pipeline() -> None:
    """
    Main detection loop.
    Dipanggil oleh application service / background task.
    """
    _ensure_initialized()

    iq_source: Iterator[IQSignal] = app_context.iq_stream.stream()

    for iq_signal in iq_source:
        event = _process_single_frame(iq_signal)

        if event is not None:
            _handle_detection_event(event)


def _process_single_frame(iq_signal: IQSignal) -> DetectionEvent | None:
    """
    Process satu frame IQ menjadi DetectionEvent.
    """
    # 1. FFT
    spectrum = compute_fft(iq_signal)

    # 2. Power Spectral Density
    psd = compute_psd(spectrum)

    # 3. Peak detection
    peaks = detect_peaks(psd)

    if not peaks:
        return None

    # 4. Signature matching
    signature = match_signature(psd, peaks)

    # 5. ML classification (optional fallback)
    classification = classify_signal(psd, peaks)

    # 6. Threat assessment
    threat = assess_threat(
        signature=signature,
        classification=classification,
        peaks=peaks,
    )

    return DetectionEvent(
        timestamp=iq_signal.timestamp,
        center_frequency=iq_signal.center_frequency,
        peaks=peaks,
        signature=signature,
        classification=classification,
        threat_level=threat,
    )


def _handle_detection_event(event: DetectionEvent) -> None:
    """
    Dispatch detection event ke sistem lain.
    """
    # 1. Publish event (real-time)
    app_context.event_bus.publish(
        topic="detection",
        payload=event.to_dict()
    )

    # 2. Persist ke database
    app_context.database.save_detection(event)


def _ensure_initialized() -> None:
    if app_context.iq_stream is None:
        raise RuntimeError("Application not initialized. Call initialize_app() first.")
