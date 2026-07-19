from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class AeroRampClient:
    def __init__(self, base_url: str, access_token: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.access_token = access_token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def login(self, email: str, password: str, organization_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"email": email, "password": password}
        if organization_id:
            payload["organization_id"] = organization_id
        response = httpx.post(f"{self.base_url}/api/v1/auth/login", json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        return data

    def register_camera(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/api/v1/cameras", payload)

    def upload_video(self, camera_id: str, path: str | Path, turnaround_id: str | None = None, detector_backend: str = "motion") -> dict[str, Any]:
        path = Path(path)
        data = {"camera_id": camera_id, "detector_backend": detector_backend, "run_now": "false"}
        if turnaround_id:
            data["turnaround_id"] = turnaround_id
        with path.open("rb") as handle:
            response = httpx.post(f"{self.base_url}/api/v1/videos/upload", headers=self.headers, data=data, files={"file": (path.name, handle, "video/mp4")}, timeout=max(self.timeout, 120))
        response.raise_for_status()
        return response.json()

    def start_processing(self, job_id: str) -> dict[str, Any]:
        return self._post(f"/api/v1/processing-jobs/{job_id}/run", None)

    def processing_status(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/processing-jobs/{job_id}")

    def list_turnarounds(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/turnarounds")

    def turnaround_timeline(self, turnaround_id: str) -> dict[str, Any]:
        return self._get(f"/api/v1/turnarounds/{turnaround_id}")

    def list_alerts(self, status: str | None = None) -> list[dict[str, Any]]:
        suffix = f"?status={status}" if status else ""
        return self._get(f"/api/v1/alerts{suffix}")

    def acknowledge_alert(self, alert_id: str, notes: str = "Acknowledged through SDK") -> dict[str, Any]:
        return self._patch(f"/api/v1/alerts/{alert_id}", {"status": "acknowledged", "notes": notes})

    def register_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/api/v1/models", payload)

    def create_incident(
        self, alert_id: str, title: str, severity: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"alert_id": alert_id, "title": title}
        if severity:
            payload["severity"] = severity
        return self._post("/api/v1/incidents", payload)

    def download_alert_report(
        self, destination: str | Path, severity: str | None = None
    ) -> Path:
        suffix = f"?severity={severity}" if severity else ""
        response = httpx.get(
            f"{self.base_url}/api/v1/reports/alerts.csv{suffix}",
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        destination = Path(destination)
        destination.write_bytes(response.content)
        return destination

    def download_evidence(self, alert_id: str, destination: str | Path, asset: str = "clip") -> Path:
        response = httpx.get(f"{self.base_url}/api/v1/evidence/{alert_id}/{asset}", headers=self.headers, timeout=max(self.timeout, 120))
        response.raise_for_status()
        destination = Path(destination)
        destination.write_bytes(response.content)
        return destination

    def _get(self, path: str) -> Any:
        response = httpx.get(f"{self.base_url}{path}", headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any] | None) -> Any:
        response = httpx.post(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=max(self.timeout, 120))
        response.raise_for_status()
        return response.json()

    def _patch(self, path: str, payload: dict[str, Any]) -> Any:
        response = httpx.patch(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
