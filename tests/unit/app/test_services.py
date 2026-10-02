from app.services import DetectionService


def test_detection_service_start_stop():
    svc = DetectionService()

    assert not svc.is_running()
    svc.start()
    assert svc.is_running()
    svc.stop()
    assert not svc.is_running()
