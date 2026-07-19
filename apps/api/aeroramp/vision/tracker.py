from __future__ import annotations

import math

from aeroramp.vision.types import Detection, TrackPoint, TrackState


class CentroidTracker:
    """Simple genuine multi-object tracker with class-aware nearest-neighbour association."""

    def __init__(self, max_distance: float = 90.0, max_missed: int = 8) -> None:
        self.max_distance = max_distance
        self.max_missed = max_missed
        self.next_id = 1
        self.tracks: dict[int, TrackState] = {}
        self.finished: list[TrackState] = []

    def _distance(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.dist(a, b)

    def update(self, detections: list[Detection], timestamp_seconds: float) -> list[TrackState]:
        active = [t for t in self.tracks.values() if t.active]
        unmatched_detections = set(range(len(detections)))
        matched_tracks: set[int] = set()
        candidates: list[tuple[float, int, int]] = []
        for track in active:
            for idx, detection in enumerate(detections):
                if track.class_name != detection.class_name:
                    continue
                distance = self._distance(track.latest.centroid, detection.centroid)
                if distance <= self.max_distance:
                    candidates.append((distance, track.track_id, idx))
        for _, track_id, detection_idx in sorted(candidates):
            if track_id in matched_tracks or detection_idx not in unmatched_detections:
                continue
            detection = detections[detection_idx]
            self.tracks[track_id].points.append(
                TrackPoint(timestamp_seconds, detection.bbox, detection.centroid, detection.confidence)
            )
            self.tracks[track_id].missed_frames = 0
            matched_tracks.add(track_id)
            unmatched_detections.remove(detection_idx)

        for track in active:
            if track.track_id not in matched_tracks:
                track.missed_frames += 1
                if track.missed_frames > self.max_missed:
                    track.active = False
                    self.finished.append(track)

        for idx in unmatched_detections:
            detection = detections[idx]
            track = TrackState(track_id=self.next_id, class_name=detection.class_name)
            track.points.append(
                TrackPoint(timestamp_seconds, detection.bbox, detection.centroid, detection.confidence)
            )
            self.tracks[self.next_id] = track
            self.next_id += 1

        return [track for track in self.tracks.values() if track.active]

    def finalize(self) -> list[TrackState]:
        for track in self.tracks.values():
            if track.active:
                track.active = False
                self.finished.append(track)
        return sorted(self.finished, key=lambda t: t.track_id)
