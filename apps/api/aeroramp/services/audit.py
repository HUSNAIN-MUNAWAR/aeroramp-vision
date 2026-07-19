from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aeroramp.db.models import AuditLog
from sqlalchemy.orm import Session


def record_audit(
    db: Session,
    organization_id: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    previous_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    reason: str | None = None,
    request_id: str | None = None,
    ip_metadata: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_state=previous_state or {},
        new_state=new_state or {},
        reason=reason,
        request_id=request_id,
        ip_metadata=ip_metadata or {},
        created_at=datetime.now(UTC),
    )
    db.add(row)
    return row
