from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


class EdgeQueue:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)")
        self.connection.commit()

    def add(self, payload: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        self.connection.execute("INSERT INTO events(id, payload, created_at) VALUES (?, ?, ?)", (event_id, json.dumps(payload), time.time()))
        self.connection.commit()
        return event_id

    def batch(self, limit: int = 100) -> list[tuple[str, dict[str, Any]]]:
        rows = self.connection.execute("SELECT id, payload FROM events ORDER BY created_at LIMIT ?", (limit,)).fetchall()
        return [(row[0], json.loads(row[1])) for row in rows]

    def acknowledge(self, ids: list[str]) -> None:
        self.connection.executemany("DELETE FROM events WHERE id = ?", [(value,) for value in ids])
        self.connection.commit()

    def mark_failure(self, ids: list[str]) -> None:
        self.connection.executemany("UPDATE events SET attempts = attempts + 1 WHERE id = ?", [(value,) for value in ids])
        self.connection.commit()


def sync(queue: EdgeQueue, api_url: str, api_key: str, node_id: str) -> dict[str, Any]:
    batch = queue.batch()
    if not batch:
        return {"accepted": 0, "queued": 0}
    ids = [item[0] for item in batch]
    events = [item[1] for item in batch]
    dedup = hashlib.sha256("|".join(ids).encode()).hexdigest()
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/api/v1/edge-nodes/sync",
            headers={"X-Edge-Key": api_key},
            json={"node_id": node_id, "deduplication_key": dedup, "events": events, "health": {"queue_depth": len(batch), "storage": "sqlite", "mode": "development"}},
            timeout=20,
        )
        response.raise_for_status()
        queue.acknowledge(ids)
        return {**response.json(), "queued": 0}
    except Exception:
        queue.mark_failure(ids)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("edge-buffer.db"))
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--node-id", required=True)
    args = parser.parse_args()
    print(sync(EdgeQueue(args.db), args.api_url, args.api_key, args.node_id))
