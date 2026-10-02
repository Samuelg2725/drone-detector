from fastapi.testclient import TestClient
from api.main import app


def test_system_status():
    client = TestClient(app)
    resp = client.get("/system/status")
    assert resp.status_code == 200
    assert "mode" in resp.json()
