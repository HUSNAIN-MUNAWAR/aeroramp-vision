from pathlib import Path

from fastapi.testclient import TestClient

from scripts.generate_synthetic_video import generate


def test_end_to_end_processing_and_review(client: TestClient, admin_headers: dict[str, str], seeded: dict[str, str], tmp_path: Path) -> None:
    video = tmp_path / "ramp.mp4"
    generate(video, seconds=8)
    with video.open("rb") as handle:
        response = client.post(
            "/api/v1/videos/upload",
            headers=admin_headers,
            data={"camera_id": seeded["camera_id"], "turnaround_id": seeded["turnaround_id"], "detector_backend": "synthetic_color", "run_now": "false"},
            files={"file": ("ramp.mp4", handle, "video/mp4")},
        )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    run = client.post(f"/api/v1/processing-jobs/{job_id}/run", headers=admin_headers)
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"
    tracks = client.get(f"/api/v1/tracks?processing_job_id={job_id}", headers=admin_headers)
    assert tracks.status_code == 200
    assert len(tracks.json()) >= 3
    alerts = client.get("/api/v1/alerts", headers=admin_headers)
    assert alerts.status_code == 200
    assert alerts.json()
    alert_id = alerts.json()[0]["id"]
    evidence = client.get(f"/api/v1/evidence/{alert_id}/snapshot", headers=admin_headers)
    assert evidence.status_code == 200
    clip = client.get(f"/api/v1/evidence/{alert_id}/clip", headers=admin_headers)
    assert clip.status_code == 200
    assert len(clip.content) > 0
    review = client.patch(f"/api/v1/alerts/{alert_id}", headers=admin_headers, json={"status": "confirmed", "notes": "Reviewed against the synchronized evidence", "resolution_reason": "Confirmed as a test fixture event"})
    assert review.status_code == 200
    assert review.json()["status"] == "confirmed"
    incident_response = client.post(
        "/api/v1/incidents",
        headers=admin_headers,
        json={"alert_id": alert_id, "title": "Synthetic restricted-zone review"},
    )
    assert incident_response.status_code == 201, incident_response.text
    incident_id = incident_response.json()["id"]
    note = client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers=admin_headers,
        json={"body": "Evidence and synchronized tracks were reviewed."},
    )
    assert note.status_code == 201, note.text
    resolved = client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers=admin_headers,
        json={
            "status": "resolved",
            "classification": "test_fixture_event",
            "resolution": "Closed after deterministic fixture verification",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    incident_detail = client.get(f"/api/v1/incidents/{incident_id}", headers=admin_headers)
    assert incident_detail.status_code == 200
    assert len(incident_detail.json()["notes"]) == 1
    detail = client.get(f"/api/v1/turnarounds/{seeded['turnaround_id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["milestones"]


def test_tenant_isolation(client: TestClient, seeded: dict[str, str]) -> None:
    login = client.post("/api/v1/auth/login", json={"email": "outsider@aeroramp.local", "password": "AeroRamp-Dev-2026!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    detail = client.get(f"/api/v1/turnarounds/{seeded['turnaround_id']}", headers=headers)
    assert detail.status_code == 404
    cameras = client.get("/api/v1/cameras", headers=headers)
    assert cameras.status_code == 200
    assert cameras.json() == []
