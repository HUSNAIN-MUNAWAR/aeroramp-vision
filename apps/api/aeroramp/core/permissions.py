from __future__ import annotations

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "platform_admin": {"*"},
    "airport_admin": {
        "airports.read", "airports.manage", "stands.read", "stands.manage",
        "cameras.read", "cameras.manage", "videos.upload", "videos.process",
        "turnarounds.read", "turnarounds.manage", "events.review", "events.correct",
        "alerts.read", "alerts.acknowledge", "alerts.resolve", "incidents.manage",
        "zones.manage", "models.manage", "reports.export", "audit.read", "users.manage",
    },
    "airline_ops_manager": {
        "airports.read", "stands.read", "cameras.read", "videos.upload", "videos.process",
        "turnarounds.read", "turnarounds.manage", "alerts.read", "alerts.acknowledge",
        "reports.export",
    },
    "ground_handling_supervisor": {
        "stands.read", "cameras.read", "turnarounds.read", "events.review", "events.correct",
        "alerts.read", "alerts.acknowledge", "reports.export",
    },
    "ramp_safety_officer": {
        "airports.read", "stands.read", "cameras.read", "turnarounds.read", "events.review",
        "alerts.read", "alerts.acknowledge", "alerts.resolve", "incidents.manage",
        "reports.export", "audit.read",
    },
    "incident_reviewer": {
        "turnarounds.read", "events.review", "alerts.read", "alerts.acknowledge",
        "alerts.resolve", "incidents.manage",
    },
    "data_analyst": {"airports.read", "stands.read", "turnarounds.read", "alerts.read", "reports.export"},
    "cv_admin": {"cameras.read", "cameras.manage", "zones.manage", "models.manage", "videos.process"},
    "camera_technician": {"cameras.read", "cameras.manage", "zones.manage"},
    "auditor": {"airports.read", "stands.read", "cameras.read", "turnarounds.read", "alerts.read", "audit.read"},
}


def has_permission(role: str, permission: str) -> bool:
    granted = ROLE_PERMISSIONS.get(role, set())
    return "*" in granted or permission in granted
