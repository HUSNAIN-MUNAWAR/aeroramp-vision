from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Detection:
    bbox: tuple[float, float, float, float]
    class_name: str
    confidence: float

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass(slots=True)
class TrackPoint:
    timestamp_seconds: float
    bbox: tuple[float, float, float, float]
    centroid: tuple[float, float]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrackState:
    track_id: int
    class_name: str
    points: list[TrackPoint] = field(default_factory=list)
    missed_frames: int = 0
    active: bool = True

    @property
    def latest(self) -> TrackPoint:
        return self.points[-1]

    @property
    def confidence_mean(self) -> float:
        return sum(p.confidence for p in self.points) / max(1, len(self.points))


@dataclass(slots=True)
class AlertCandidate:
    rule_id: str
    rule_type: str
    track_id: int
    zone_id: str | None
    timestamp_seconds: float
    severity: str
    confidence: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class MilestoneCandidate:
    milestone_type: str
    timestamp_seconds: float
    confidence: float
    supporting_track_ids: list[int]
    observation_kind: str = "inferred"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineResult:
    metadata: dict[str, Any]
    tracks: list[TrackState]
    alerts: list[AlertCandidate]
    milestones: list[MilestoneCandidate]
    observation_path: str
    annotated_video_path: str | None
    snapshots: dict[str, str]
    evidence_clips: dict[str, str]
