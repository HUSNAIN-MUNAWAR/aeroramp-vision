from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aeroramp.db.base import Base, IdMixin, TimestampMixin


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    organization_type: Mapped[str] = mapped_column(String(64), default="airport_operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="user")


class OrganizationMembership(Base, IdMixin, TimestampMixin):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(64), index=True)
    user: Mapped[User] = relationship(back_populates="memberships")


class Airport(Base, IdMixin, TimestampMixin):
    __tablename__ = "airports"
    __table_args__ = (UniqueConstraint("organization_id", "iata_code", name="uq_airport_org_iata"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    iata_code: Mapped[str] = mapped_column(String(3), index=True)
    icao_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")


class Terminal(Base, IdMixin, TimestampMixin):
    __tablename__ = "terminals"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    airport_id: Mapped[str] = mapped_column(ForeignKey("airports.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))


class Stand(Base, IdMixin, TimestampMixin):
    __tablename__ = "stands"
    __table_args__ = (UniqueConstraint("airport_id", "code", name="uq_stand_airport_code"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    airport_id: Mapped[str] = mapped_column(ForeignKey("airports.id"), index=True)
    terminal_id: Mapped[str | None] = mapped_column(ForeignKey("terminals.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="available")
    layout: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Camera(Base, IdMixin, TimestampMixin):
    __tablename__ = "cameras"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    airport_id: Mapped[str] = mapped_column(ForeignKey("airports.id"), index=True)
    stand_id: Mapped[str | None] = mapped_column(ForeignKey("stands.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    source_mode: Mapped[str] = mapped_column(String(32), default="upload")
    stream_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    camera_type: Mapped[str] = mapped_column(String(64), default="fixed")
    resolution_width: Mapped[int] = mapped_column(Integer, default=1280)
    resolution_height: Mapped[int] = mapped_column(Integer, default=720)
    frame_rate: Mapped[float] = mapped_column(Float, default=25.0)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calibration_state: Mapped[str] = mapped_column(String(32), default="calibration_required")
    masked_regions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    privacy_regions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    processing_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retention_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CameraCalibration(Base, IdMixin, TimestampMixin):
    __tablename__ = "camera_calibrations"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reference_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    homography_matrix: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    ground_plane_units: Mapped[str] = mapped_column(String(16), default="image")
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CameraZone(Base, IdMixin, TimestampMixin):
    __tablename__ = "camera_zones"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    stand_id: Mapped[str | None] = mapped_column(ForeignKey("stands.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    zone_type: Mapped[str] = mapped_column(String(64), index=True)
    polygon: Mapped[list[Any]] = mapped_column(JSON)
    severity: Mapped[str] = mapped_column(String(24), default="medium")
    allowed_classes: Mapped[list[str]] = mapped_column(JSON, default=list)
    forbidden_classes: Mapped[list[str]] = mapped_column(JSON, default=list)
    rule_configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SafetyRule(Base, IdMixin, TimestampMixin):
    __tablename__ = "safety_rules"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("camera_zones.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    rule_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(24), default="medium")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cooldown_seconds: Mapped[float] = mapped_column(Float, default=15.0)
    debounce_seconds: Mapped[float] = mapped_column(Float, default=1.0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UploadedVideo(Base, IdMixin, TimestampMixin):
    __tablename__ = "uploaded_videos"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)


class ProcessingJob(Base, IdMixin, TimestampMixin):
    __tablename__ = "processing_jobs"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("uploaded_videos.id"), index=True)
    turnaround_id: Mapped[str | None] = mapped_column(ForeignKey("turnarounds.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    detector_backend: Mapped[str] = mapped_column(String(64), default="motion")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Turnaround(Base, IdMixin, TimestampMixin):
    __tablename__ = "turnarounds"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    airport_id: Mapped[str] = mapped_column(ForeignKey("airports.id"), index=True)
    stand_id: Mapped[str] = mapped_column(ForeignKey("stands.id"), index=True)
    airline_code: Mapped[str] = mapped_column(String(8), default="DEV")
    flight_number: Mapped[str] = mapped_column(String(32), index=True)
    aircraft_registration: Mapped[str | None] = mapped_column(String(32), nullable=True)
    aircraft_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scheduled_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_on_block: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_off_block: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="scheduled", index=True)
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_review_state: Mapped[str] = mapped_column(String(32), default="not_reviewed")


class ObjectTrack(Base, IdMixin, TimestampMixin):
    __tablename__ = "object_tracks"
    __table_args__ = (Index("ix_track_job_external", "processing_job_id", "external_track_id"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    processing_job_id: Mapped[str | None] = mapped_column(ForeignKey("processing_jobs.id"), index=True, nullable=True)
    turnaround_id: Mapped[str | None] = mapped_column(ForeignKey("turnarounds.id"), nullable=True)
    external_track_id: Mapped[int] = mapped_column(Integer)
    object_class: Mapped[str] = mapped_column(String(80), index=True)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    confidence_mean: Mapped[float] = mapped_column(Float)
    bbox_history_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    centroid_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    velocity_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    zone_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="terminated")


class OperationalEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "operational_events"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    processing_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("processing_jobs.id"), index=True, nullable=True
    )
    turnaround_id: Mapped[str | None] = mapped_column(ForeignKey("turnarounds.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    observation_kind: Mapped[str] = mapped_column(String(32), default="rule_inference")
    confidence: Mapped[float] = mapped_column(Float)
    supporting_track_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SafetyAlert(Base, IdMixin, TimestampMixin):
    __tablename__ = "safety_alerts"
    __table_args__ = (Index("ix_alert_org_status_time", "organization_id", "status", "created_at"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("safety_rules.id"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    stand_id: Mapped[str | None] = mapped_column(ForeignKey("stands.id"), nullable=True)
    turnaround_id: Mapped[str | None] = mapped_column(ForeignKey("turnarounds.id"), nullable=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(24), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    related_track_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("camera_zones.id"), nullable=True)
    evidence_snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_clip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    assigned_reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String(255), index=True)


class TurnaroundMilestone(Base, IdMixin, TimestampMixin):
    __tablename__ = "turnaround_milestones"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    turnaround_id: Mapped[str] = mapped_column(ForeignKey("turnarounds.id"), index=True)
    milestone_type: Mapped[str] = mapped_column(String(80), index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    observation_kind: Mapped[str] = mapped_column(String(32), default="inferred")
    confidence: Mapped[float] = mapped_column(Float)
    supporting_track_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    original_prediction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class EvidenceAsset(Base, IdMixin, TimestampMixin):
    __tablename__ = "evidence_assets"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    alert_id: Mapped[str | None] = mapped_column(ForeignKey("safety_alerts.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("operational_events.id"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    storage_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Incident(Base, IdMixin, TimestampMixin):
    __tablename__ = "incidents"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("safety_alerts.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigned_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)


class IncidentNote(Base, IdMixin, TimestampMixin):
    __tablename__ = "incident_notes"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)


class ReviewDecision(Base, IdMixin, TimestampMixin):
    __tablename__ = "review_decisions"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    previous_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    corrected_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)


class ModelVersion(Base, IdMixin, TimestampMixin):
    __tablename__ = "model_versions"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(40))
    framework: Mapped[str] = mapped_column(String(40))
    input_resolution: Mapped[str] = mapped_column(String(32))
    class_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    checkpoint_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deployment_status: Mapped[str] = mapped_column(String(32), default="registered")
    safe_serialization: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelDeployment(Base, IdMixin, TimestampMixin):
    __tablename__ = "model_deployments"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), index=True)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id"), nullable=True, index=True)
    edge_node_id: Mapped[str | None] = mapped_column(
        ForeignKey("edge_nodes.id"), nullable=True, index=True
    )
    backend: Mapped[str] = mapped_column(String(40), default="onnxruntime_cpu")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    deployed_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rollback_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_deployments.id"), nullable=True
    )


class EdgeNode(Base, IdMixin, TimestampMixin):
    __tablename__ = "edge_nodes"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="offline")
    configuration_version: Mapped[int] = mapped_column(Integer, default=1)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    api_key_hash: Mapped[str] = mapped_column(String(255))


class EdgeSyncBatch(Base, IdMixin, TimestampMixin):
    __tablename__ = "edge_sync_batches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "edge_node_id",
            "deduplication_key",
            name="uq_edge_sync_batch_dedup",
        ),
    )
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    edge_node_id: Mapped[str] = mapped_column(ForeignKey("edge_nodes.id"), index=True)
    deduplication_key: Mapped[str] = mapped_column(String(64), index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="accepted")


class Notification(Base, IdMixin, TimestampMixin):
    __tablename__ = "notifications"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="in_app")
    notification_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")


class AuditLog(Base, IdMixin):
    __tablename__ = "audit_logs"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    previous_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    new_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
