from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from aeroramp.vision.geometry import (
    angle_difference,
    closest_point_of_approach,
    direction_angle,
    estimate_speed,
    point_in_polygon,
)
from aeroramp.vision.types import AlertCandidate, TrackState


@dataclass(slots=True)
class RuleConfig:
    id: str
    rule_type: str
    severity: str
    zone_id: str | None
    polygon: list[list[float]] | None
    config: dict[str, Any]
    debounce_seconds: float = 1.0
    cooldown_seconds: float = 15.0


class SafetyRuleEngine:
    def __init__(self, rules: list[RuleConfig], metric_scale: float | None = None) -> None:
        self.rules = rules
        self.metric_scale = metric_scale
        self.first_seen: dict[tuple[str, int], float] = {}
        self.last_alert: dict[tuple[str, int], float] = {}
        self.stationary_since: dict[tuple[str, int], float] = {}

    def evaluate(self, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        alerts: list[AlertCandidate] = []
        for rule in self.rules:
            if rule.rule_type in {"person_in_restricted_zone", "restricted_zone_entry", "pushback_path_obstruction"}:
                alerts.extend(self._zone_presence(rule, tracks, timestamp_seconds))
            elif rule.rule_type == "excess_speed":
                alerts.extend(self._speed(rule, tracks, timestamp_seconds))
            elif rule.rule_type == "wrong_way":
                alerts.extend(self._wrong_way(rule, tracks, timestamp_seconds))
            elif rule.rule_type == "equipment_left_behind":
                alerts.extend(self._stationary(rule, tracks, timestamp_seconds))
            elif rule.rule_type == "candidate_near_miss":
                alerts.extend(self._near_miss(rule, tracks, timestamp_seconds))
        return alerts

    def _eligible(self, rule: RuleConfig, track: TrackState) -> bool:
        classes = set(rule.config.get("classes", []))
        return not classes or track.class_name in classes

    def _emit(self, rule: RuleConfig, track: TrackState, timestamp_seconds: float, confidence: float, metadata: dict[str, Any]) -> AlertCandidate | None:
        key = (rule.id, track.track_id)
        last = self.last_alert.get(key, -1e9)
        if timestamp_seconds - last < rule.cooldown_seconds:
            return None
        self.last_alert[key] = timestamp_seconds
        return AlertCandidate(rule.id, rule.rule_type, track.track_id, rule.zone_id, timestamp_seconds, rule.severity, min(0.99, max(0.01, confidence)), metadata)

    def _zone_presence(self, rule: RuleConfig, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        if not rule.polygon:
            return []
        output: list[AlertCandidate] = []
        for track in tracks:
            if not self._eligible(rule, track):
                continue
            key = (rule.id, track.track_id)
            inside = point_in_polygon(track.latest.centroid, rule.polygon)
            if not inside:
                self.first_seen.pop(key, None)
                continue
            first = self.first_seen.setdefault(key, timestamp_seconds)
            dwell = timestamp_seconds - first
            if dwell >= rule.debounce_seconds:
                confidence = 0.55 * track.latest.confidence + 0.45 * min(1.0, dwell / max(rule.debounce_seconds * 2, 0.1))
                candidate = self._emit(rule, track, timestamp_seconds, confidence, {"dwell_seconds": round(dwell, 3), "decision_support": True})
                if candidate:
                    output.append(candidate)
        return output

    def _speed(self, rule: RuleConfig, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        if self.metric_scale is None:
            return []
        threshold = float(rule.config.get("threshold_mps", 5.0))
        output: list[AlertCandidate] = []
        for track in tracks:
            if not self._eligible(rule, track) or len(track.points) < 2:
                continue
            a, b = track.points[-2:]
            speed = estimate_speed(a.centroid, b.centroid, b.timestamp_seconds - a.timestamp_seconds, self.metric_scale)
            if speed is not None and speed > threshold:
                candidate = self._emit(rule, track, timestamp_seconds, min(0.95, speed / max(threshold * 2, 0.1)), {"speed_mps": speed, "threshold_mps": threshold, "metric_calibration": True})
                if candidate:
                    output.append(candidate)
        return output

    def _wrong_way(self, rule: RuleConfig, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        expected = float(rule.config.get("expected_angle_degrees", 0.0))
        tolerance = float(rule.config.get("tolerance_degrees", 60.0))
        min_distance = float(rule.config.get("minimum_distance_pixels", 30.0))
        output: list[AlertCandidate] = []
        for track in tracks:
            if not self._eligible(rule, track) or len(track.points) < 2:
                continue
            first, last = track.points[0], track.points[-1]
            distance = math.dist(first.centroid, last.centroid)
            if distance < min_distance:
                continue
            angle = direction_angle(first.centroid, last.centroid)
            delta = angle_difference(angle, expected)
            if delta > tolerance:
                candidate = self._emit(rule, track, timestamp_seconds, min(0.95, delta / 180.0), {"observed_angle": angle, "expected_angle": expected, "difference": delta})
                if candidate:
                    output.append(candidate)
        return output

    def _stationary(self, rule: RuleConfig, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        max_motion = float(rule.config.get("stationary_distance_pixels", 5.0))
        dwell_threshold = float(rule.config.get("dwell_seconds", 5.0))
        output: list[AlertCandidate] = []
        for track in tracks:
            if not self._eligible(rule, track) or len(track.points) < 2:
                continue
            key = (rule.id, track.track_id)
            motion = math.dist(track.points[-2].centroid, track.points[-1].centroid)
            in_zone = rule.polygon is None or point_in_polygon(track.latest.centroid, rule.polygon)
            if motion <= max_motion and in_zone:
                started = self.stationary_since.setdefault(key, timestamp_seconds)
                dwell = timestamp_seconds - started
                if dwell >= dwell_threshold:
                    candidate = self._emit(rule, track, timestamp_seconds, min(0.95, dwell / max(dwell_threshold * 2, 1.0)), {"stationary_seconds": dwell})
                    if candidate:
                        output.append(candidate)
            else:
                self.stationary_since.pop(key, None)
        return output

    def _near_miss(self, rule: RuleConfig, tracks: list[TrackState], timestamp_seconds: float) -> list[AlertCandidate]:
        distance_threshold = float(rule.config.get("distance_threshold_pixels", 45.0))
        time_threshold = float(rule.config.get("time_threshold_seconds", 2.0))
        output: list[AlertCandidate] = []
        for i, first in enumerate(tracks):
            if len(first.points) < 2:
                continue
            for second in tracks[i + 1:]:
                if len(second.points) < 2:
                    continue
                f0, f1 = first.points[-2:]
                s0, s1 = second.points[-2:]
                fdt = max(f1.timestamp_seconds - f0.timestamp_seconds, 1e-6)
                sdt = max(s1.timestamp_seconds - s0.timestamp_seconds, 1e-6)
                result = closest_point_of_approach(
                    f1.centroid,
                    ((f1.centroid[0] - f0.centroid[0]) / fdt, (f1.centroid[1] - f0.centroid[1]) / fdt),
                    s1.centroid,
                    ((s1.centroid[0] - s0.centroid[0]) / sdt, (s1.centroid[1] - s0.centroid[1]) / sdt),
                )
                if result.distance < distance_threshold and result.time_to_closest < time_threshold:
                    synthetic_track = first
                    pair_key = hashlib.sha1(f"{min(first.track_id, second.track_id)}:{max(first.track_id, second.track_id)}".encode()).hexdigest()[:12]
                    candidate = self._emit(rule, synthetic_track, timestamp_seconds, min(0.9, 1.0 - result.distance / distance_threshold), {"candidate": True, "other_track_id": second.track_id, "closest_distance_pixels": result.distance, "time_to_closest_seconds": result.time_to_closest, "pair_key": pair_key, "monocular_limitations": True})
                    if candidate:
                        output.append(candidate)
        return output


def deduplication_key(candidate: AlertCandidate, processing_job_id: str) -> str:
    raw = f"{processing_job_id}:{candidate.rule_id}:{candidate.track_id}:{int(candidate.timestamp_seconds // 10)}"
    return hashlib.sha256(raw.encode()).hexdigest()
