from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organization_id: str
    role: str


class OrganizationOut(ORMModel):
    id: str
    name: str
    organization_type: str


class UserOut(ORMModel):
    id: str
    email: str
    full_name: str
    role: str | None = None
    organization_id: str | None = None


class AirportCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    iata_code: str = Field(min_length=3, max_length=3)
    icao_code: str | None = Field(default=None, min_length=4, max_length=4)
    timezone: str = "UTC"

    @field_validator("iata_code", "icao_code")
    @classmethod
    def uppercase_codes(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class AirportOut(ORMModel):
    id: str
    organization_id: str
    name: str
    iata_code: str
    icao_code: str | None
    timezone: str


class StandCreate(BaseModel):
    airport_id: str
    terminal_id: str | None = None
    code: str = Field(min_length=1, max_length=32)
    layout: dict[str, Any] = Field(default_factory=dict)


class StandOut(ORMModel):
    id: str
    airport_id: str
    terminal_id: str | None
    code: str
    status: str
    layout: dict[str, Any]


class CameraCreate(BaseModel):
    airport_id: str
    stand_id: str | None = None
    name: str = Field(min_length=2, max_length=160)
    source_mode: str = "upload"
    stream_url: str | None = None
    camera_type: str = "fixed"
    resolution_width: int = Field(default=1280, ge=160, le=8192)
    resolution_height: int = Field(default=720, ge=120, le=4320)
    frame_rate: float = Field(default=25.0, gt=0, le=240)
    timezone: str = "UTC"
    masked_regions: list[list[list[float]]] = Field(default_factory=list)
    privacy_regions: list[list[list[float]]] = Field(default_factory=list)
    processing_profile: dict[str, Any] = Field(default_factory=dict)
    retention_settings: dict[str, Any] = Field(default_factory=dict)


class CameraOut(ORMModel):
    id: str
    airport_id: str
    stand_id: str | None
    name: str
    source_mode: str
    camera_type: str
    resolution_width: int
    resolution_height: int
    frame_rate: float
    timezone: str
    status: str
    calibration_state: str
    masked_regions: list[Any]
    privacy_regions: list[Any]
    processing_profile: dict[str, Any]
    retention_settings: dict[str, Any]


class CalibrationCreate(BaseModel):
    camera_id: str
    reference_points: list[list[float]] = Field(default_factory=list)
    homography_matrix: list[list[float]] | None = None
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    ground_plane_units: str = "image"
    validation_notes: str | None = None
    error_estimate: float | None = Field(default=None, ge=0)


class ZoneCreate(BaseModel):
    camera_id: str
    stand_id: str | None = None
    name: str
    zone_type: str
    polygon: list[list[float]]
    severity: str = "medium"
    allowed_classes: list[str] = Field(default_factory=list)
    forbidden_classes: list[str] = Field(default_factory=list)
    rule_configuration: dict[str, Any] = Field(default_factory=dict)


class ZoneOut(ORMModel):
    id: str
    camera_id: str
    stand_id: str | None
    name: str
    zone_type: str
    polygon: list[Any]
    severity: str
    allowed_classes: list[str]
    forbidden_classes: list[str]
    rule_configuration: dict[str, Any]
    version: int


class RuleCreate(BaseModel):
    camera_id: str
    zone_id: str | None = None
    name: str
    rule_type: str
    severity: str = "medium"
    config: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: float = Field(default=15, ge=0)
    debounce_seconds: float = Field(default=1, ge=0)


class RuleOut(ORMModel):
    id: str
    camera_id: str
    zone_id: str | None
    name: str
    rule_type: str
    severity: str
    config: dict[str, Any]
    cooldown_seconds: float
    debounce_seconds: float
    version: int


class TurnaroundCreate(BaseModel):
    airport_id: str
    stand_id: str
    airline_code: str
    flight_number: str
    aircraft_registration: str | None = None
    aircraft_type: str | None = None
    scheduled_arrival: datetime | None = None
    scheduled_departure: datetime | None = None


class TurnaroundOut(ORMModel):
    id: str
    airport_id: str
    stand_id: str
    airline_code: str
    flight_number: str
    aircraft_registration: str | None
    aircraft_type: str | None
    scheduled_arrival: datetime | None
    actual_on_block: datetime | None
    scheduled_departure: datetime | None
    actual_off_block: datetime | None
    status: str
    detection_confidence: float | None
    manual_review_state: str


class ProcessingJobOut(ORMModel):
    id: str
    camera_id: str
    video_id: str
    turnaround_id: str | None
    status: str
    progress: float
    detector_backend: str
    error_code: str | None
    error_message: str | None
    metrics: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TrackOut(ORMModel):
    id: str
    external_track_id: int
    object_class: str
    start_seconds: float
    end_seconds: float
    confidence_mean: float
    centroid_history: list[Any]
    velocity_summary: dict[str, Any]
    zone_history: list[Any]


class AlertOut(ORMModel):
    id: str
    rule_id: str
    camera_id: str
    stand_id: str | None
    turnaround_id: str | None
    timestamp_seconds: float
    end_seconds: float | None
    severity: str
    confidence: float
    related_track_ids: list[str]
    zone_id: str | None
    evidence_snapshot_path: str | None
    evidence_clip_path: str | None
    event_metadata: dict[str, Any]
    status: str
    review_notes: str | None
    resolution_reason: str | None
    created_at: datetime


class AlertReview(BaseModel):
    status: str
    notes: str | None = None
    resolution_reason: str | None = None


class MilestoneOut(ORMModel):
    id: str
    turnaround_id: str
    milestone_type: str
    timestamp_seconds: float
    end_seconds: float | None
    observation_kind: str
    confidence: float
    supporting_track_ids: list[str]
    manual_override: bool
    override_reason: str | None


class MilestoneCorrection(BaseModel):
    timestamp_seconds: float = Field(ge=0)
    milestone_type: str | None = None
    reason: str = Field(min_length=5)


class ModelVersionCreate(BaseModel):
    name: str
    version: str
    framework: str
    input_resolution: str
    class_list: list[str]
    checkpoint_path: str | None = None
    checkpoint_checksum: str | None = None
    validation_metrics: dict[str, Any] = Field(default_factory=dict)
    safe_serialization: bool = True


class EdgeSyncRequest(BaseModel):
    node_id: str
    deduplication_key: str
    events: list[dict[str, Any]]
    health: dict[str, Any] = Field(default_factory=dict)


class IncidentCreate(BaseModel):
    alert_id: str
    title: str = Field(min_length=3, max_length=200)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    assigned_to_id: str | None = None


class IncidentUpdate(BaseModel):
    status: Literal["open", "under_review", "confirmed", "false_positive", "resolved", "escalated"] | None = None
    classification: str | None = Field(default=None, max_length=64)
    resolution: str | None = None
    assigned_to_id: str | None = None


class IncidentNoteCreate(BaseModel):
    body: str = Field(min_length=2, max_length=5000)


class IncidentOut(ORMModel):
    id: str
    alert_id: str
    title: str
    severity: str
    status: str
    assigned_to_id: str | None
    classification: str | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class IncidentNoteOut(ORMModel):
    id: str
    incident_id: str
    author_id: str
    body: str
    created_at: datetime


class ModelDeploymentCreate(BaseModel):
    model_version_id: str
    camera_id: str | None = None
    edge_node_id: str | None = None
    backend: Literal[
        "pytorch_cpu",
        "pytorch_cuda",
        "onnxruntime_cpu",
        "onnxruntime_cuda",
        "openvino",
        "tensorrt",
    ] = "onnxruntime_cpu"
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("edge_node_id")
    @classmethod
    def target_required(cls, value: str | None, info: Any) -> str | None:
        if not value and not info.data.get("camera_id"):
            raise ValueError("camera_id or edge_node_id is required")
        return value


class ModelDeploymentRollback(BaseModel):
    target_model_version_id: str
    reason: str = Field(min_length=5, max_length=1000)


class ModelDeploymentOut(ORMModel):
    id: str
    model_version_id: str
    camera_id: str | None
    edge_node_id: str | None
    backend: str
    status: str
    configuration: dict[str, Any]
    deployed_at: datetime
    deployed_by_id: str
    rollback_of_id: str | None
