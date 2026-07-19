from aeroramp.db.models import EdgeSyncBatch, OperationalEvent
from aeroramp.db.session import SessionLocal
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_edge_api_key_sync_and_deduplication(
    client: TestClient, seeded: dict[str, str]
) -> None:
    payload = {
        "node_id": seeded["edge_node_id"],
        "deduplication_key": "a" * 64,
        "events": [
            {
                "camera_id": seeded["camera_id"],
                "turnaround_id": seeded["turnaround_id"],
                "event_type": "edge_zone_entry_candidate",
                "timestamp_seconds": 3.5,
                "confidence": 0.72,
                "metadata": {"decision_support": True},
            }
        ],
        "health": {"queue_depth": 1, "disk_free_mb": 2048},
    }
    headers = {"X-Edge-Key": "edge-development-key"}
    first = client.post("/api/v1/edge-nodes/sync", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["accepted"] == 1
    assert first.json()["duplicate"] is False

    duplicate = client.post("/api/v1/edge-nodes/sync", headers=headers, json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["accepted"] == 0
    assert duplicate.json()["duplicate"] is True

    unauthorized = client.post(
        "/api/v1/edge-nodes/sync",
        headers={"X-Edge-Key": "incorrect"},
        json={**payload, "deduplication_key": "b" * 64},
    )
    assert unauthorized.status_code == 401

    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(OperationalEvent).where(
                    OperationalEvent.observation_kind == "edge_sync"
                )
            )
        )
        batches = list(db.scalars(select(EdgeSyncBatch)))
    assert len(events) == 1
    assert len(batches) == 1
    assert batches[0].accepted_count == 1
