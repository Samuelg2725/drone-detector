from fastapi.testclient import TestClient
from api.main import app


def test_detection_latest():
    client = TestClient(app)
    resp = client.get("/detection/latest")
    assert resp.status_code == 200
