from fastapi.testclient import TestClient


def test_model_deployment_and_rollback(
    client: TestClient, admin_headers: dict[str, str], seeded: dict[str, str]
) -> None:
    models = client.get("/api/v1/models", headers=admin_headers)
    assert models.status_code == 200
    by_name = {item["name"]: item for item in models.json()}
    motion = by_name["OpenCV Motion Baseline"]
    fixture = by_name["Synthetic Fixture Color Detector"]

    deployment = client.post(
        "/api/v1/model-deployments",
        headers=admin_headers,
        json={
            "model_version_id": fixture["id"],
            "edge_node_id": seeded["edge_node_id"],
            "backend": "openvino",
            "configuration": {"inference_fps": 4, "test_only": True},
        },
    )
    assert deployment.status_code == 201, deployment.text
    assert deployment.json()["status"] == "active"

    rollback = client.post(
        f"/api/v1/model-deployments/{deployment.json()['id']}/rollback",
        headers=admin_headers,
        json={
            "target_model_version_id": motion["id"],
            "reason": "Fixture model must not remain assigned outside deterministic testing",
        },
    )
    assert rollback.status_code == 201, rollback.text
    assert rollback.json()["rollback_of_id"] == deployment.json()["id"]
    assert rollback.json()["model_version_id"] == motion["id"]

    deployments = client.get("/api/v1/model-deployments", headers=admin_headers)
    assert deployments.status_code == 200
    assert any(item["status"] == "rolled_back" for item in deployments.json())
