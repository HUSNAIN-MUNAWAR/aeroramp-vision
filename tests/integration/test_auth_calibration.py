from fastapi.testclient import TestClient


def test_login_and_metric_rule_requires_calibration(client: TestClient, admin_headers: dict[str, str], seeded: dict[str, str]) -> None:
    me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    response = client.post("/api/v1/safety-rules", headers=admin_headers, json={"camera_id": seeded["camera_id"], "name": "Speed candidate", "rule_type": "excess_speed", "severity": "high", "config": {"classes": ["service_vehicle"], "threshold_mps": 5}, "cooldown_seconds": 5, "debounce_seconds": 1})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "CAMERA_CALIBRATION_REQUIRED"
