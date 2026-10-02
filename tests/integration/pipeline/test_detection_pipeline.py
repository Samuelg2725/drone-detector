from app.services import DetectionService


def test_detection_pipeline_start_stop():
    svc = DetectionService()
    svc.start()
    assert svc.is_running()
    svc.stop()
    assert not svc.is_running()
