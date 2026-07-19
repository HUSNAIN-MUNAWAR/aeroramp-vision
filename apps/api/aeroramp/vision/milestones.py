from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroramp.vision.geometry import point_in_polygon
from aeroramp.vision.types import MilestoneCandidate, TrackState


@dataclass(slots=True)
class MilestoneRule:
    milestone_type: str
    object_class: str
    zone_polygon: list[list[float]]
    minimum_dwell_seconds: float = 2.0
    observation_kind: str = "inferred"


class TurnaroundMilestoneEngine:
    def __init__(self, rules: list[MilestoneRule]) -> None:
        self.rules = rules
        self.emitted: set[tuple[str, int]] = set()

    def evaluate(self, tracks: list[TrackState]) -> list[MilestoneCandidate]:
        output: list[MilestoneCandidate] = []
        for rule in self.rules:
            for track in tracks:
                key = (rule.milestone_type, track.track_id)
                if key in self.emitted or track.class_name != rule.object_class or len(track.points) < 2:
                    continue
                points_inside = [p for p in track.points if point_in_polygon(p.centroid, rule.zone_polygon)]
                if len(points_inside) < 2:
                    continue
                dwell = points_inside[-1].timestamp_seconds - points_inside[0].timestamp_seconds
                if dwell < rule.minimum_dwell_seconds:
                    continue
                persistence = min(1.0, dwell / max(rule.minimum_dwell_seconds * 2, 0.1))
                confidence = 0.6 * track.confidence_mean + 0.4 * persistence
                output.append(MilestoneCandidate(rule.milestone_type, points_inside[0].timestamp_seconds, confidence, [track.track_id], rule.observation_kind, {"dwell_seconds": dwell}))
                self.emitted.add(key)
        return output


READINESS_REQUIREMENTS: dict[str, str] = {
    "aircraft_on_block": "Aircraft is stably positioned on stand",
    "service_vehicle_clear": "Service vehicles have cleared protected zones",
    "pushback_path_clear": "Configured pushback path is clear",
}


def evaluate_readiness(milestone_types: set[str], active_high_alerts: int) -> dict[str, Any]:
    missing = [name for name in READINESS_REQUIREMENTS if name not in milestone_types]
    if active_high_alerts > 0:
        state = "not_ready"
    elif not missing:
        state = "ready_for_review"
    elif len(missing) == 1:
        state = "nearly_ready"
    else:
        state = "at_risk"
    confidence = max(0.0, min(1.0, (len(READINESS_REQUIREMENTS) - len(missing)) / len(READINESS_REQUIREMENTS)))
    return {
        "state": state,
        "supporting_conditions": [READINESS_REQUIREMENTS[x] for x in READINESS_REQUIREMENTS if x not in missing],
        "missing_conditions": [READINESS_REQUIREMENTS[x] for x in missing],
        "active_high_severity_alerts": active_high_alerts,
        "confidence": round(confidence, 3),
        "manual_confirmation_required": True,
    }
