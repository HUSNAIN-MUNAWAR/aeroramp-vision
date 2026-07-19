from __future__ import annotations

import gzip
import hashlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2

from aeroramp.vision.detectors import build_detector
from aeroramp.vision.milestones import MilestoneRule, TurnaroundMilestoneEngine
from aeroramp.vision.privacy import apply_privacy
from aeroramp.vision.rules import RuleConfig, SafetyRuleEngine
from aeroramp.vision.tracker import CentroidTracker
from aeroramp.vision.types import AlertCandidate, PipelineResult, TrackState

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, dict[str, Any]], None]


def probe_video(path: str | Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Video cannot be decoded")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise ValueError("Video metadata is invalid")
    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": frame_count / fps if frame_count else None,
    }


def _draw_frame(frame, tracks: list[TrackState], zones: list[dict[str, Any]], alerts: list[AlertCandidate]) -> Any:
    for zone in zones:
        polygon = zone.get("polygon") or []
        if len(polygon) >= 3:
            pts = __import__("numpy").array(polygon, dtype="int32")
            cv2.polylines(frame, [pts], True, (255, 255, 255), 2)
            x, y = pts[0]
            cv2.putText(frame, zone.get("name", "zone"), (int(x), int(y) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    for track in tracks:
        x1, y1, x2, y2 = (int(v) for v in track.latest.bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 230, 120), 2)
        cv2.putText(frame, f"{track.track_id} {track.class_name} {track.latest.confidence:.2f}", (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 120), 1)
        if len(track.points) > 1:
            points = __import__("numpy").array([p.centroid for p in track.points[-30:]], dtype="int32")
            cv2.polylines(frame, [points], False, (0, 220, 255), 2)
    for alert in alerts:
        cv2.putText(frame, f"REVIEW: {alert.rule_type}", (12, 28 + 22 * alerts.index(alert)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
    return frame



def _alert_key(alert: AlertCandidate) -> str:
    return f"{alert.rule_id}-{alert.track_id}-{int(alert.timestamp_seconds * 1000)}"


def _extract_clip(
    annotated_path: Path,
    output_path: Path,
    center_seconds: float,
    before_seconds: float,
    after_seconds: float,
) -> bool:
    capture = cv2.VideoCapture(str(annotated_path))
    if not capture.isOpened():
        return False
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        return False
    duration = frame_count / fps if frame_count else center_seconds + after_seconds
    start_seconds = max(0.0, center_seconds - before_seconds)
    end_seconds = min(duration, center_seconds + after_seconds)
    capture.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000.0)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        return False
    frames_written = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        position_seconds = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        if position_seconds > end_seconds:
            break
        writer.write(frame)
        frames_written += 1
    capture.release()
    writer.release()
    if frames_written == 0:
        output_path.unlink(missing_ok=True)
        return False
    return True

def process_video(
    video_path: str | Path,
    output_dir: str | Path,
    detector_backend: str,
    detector_config: dict[str, Any],
    zones: list[dict[str, Any]],
    rules: list[RuleConfig],
    milestone_rules: list[MilestoneRule],
    target_fps: float = 4.0,
    metric_scale: float | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: Callable[[], bool] | None = None,
) -> PipelineResult:
    metadata = probe_video(video_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    detector = build_detector(detector_backend, detector_config)
    tracker = CentroidTracker(max_distance=float(detector_config.get("tracker_max_distance", 100)))
    rule_engine = SafetyRuleEngine(rules, metric_scale=metric_scale)
    milestone_engine = TurnaroundMilestoneEngine(milestone_rules)
    capture = cv2.VideoCapture(str(video_path))
    source_fps = metadata["fps"]
    frame_count = metadata["frame_count"]
    sample_every = max(1, round(source_fps / max(target_fps, 0.1)))
    annotated_path = output_root / "annotated.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
    writer = cv2.VideoWriter(
        str(annotated_path),
        fourcc,
        source_fps / sample_every,
        (metadata["width"], metadata["height"]),
    )
    observations: list[dict[str, Any]] = []
    alerts: list[AlertCandidate] = []
    milestones = []
    snapshots: dict[str, str] = {}
    evidence_clips: dict[str, str] = {}
    processed_frames = 0
    privacy_applied = False
    started = time.perf_counter()
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if cancel_callback and cancel_callback():
            capture.release()
            writer.release()
            raise RuntimeError("Processing cancelled")
        if frame_index % sample_every:
            frame_index += 1
            continue
        timestamp_seconds = frame_index / source_fps
        detections = detector.detect(frame)
        active_tracks = tracker.update(detections, timestamp_seconds)
        frame_alerts = rule_engine.evaluate(active_tracks, timestamp_seconds)
        alerts.extend(frame_alerts)
        milestones.extend(milestone_engine.evaluate(active_tracks))
        observations.append(
            {
                "frame_index": frame_index,
                "timestamp_seconds": timestamp_seconds,
                "detections": [
                    {"bbox": d.bbox, "class_name": d.class_name, "confidence": d.confidence}
                    for d in detections
                ],
                "tracks": [
                    {"track_id": t.track_id, "class_name": t.class_name, "bbox": t.latest.bbox, "centroid": t.latest.centroid, "confidence": t.latest.confidence}
                    for t in active_tracks
                ],
            }
        )
        for alert in frame_alerts:
            alert_key = _alert_key(alert)
            snapshot_path = output_root / f"alert-{alert_key}.jpg"
            privacy_frame, frame_redacted = apply_privacy(
                frame,
                active_tracks,
                zones,
                bool(detector_config.get("anonymize_persons", False)),
            )
            privacy_applied = privacy_applied or frame_redacted
            rendered = _draw_frame(privacy_frame, active_tracks, zones, [alert])
            cv2.imwrite(str(snapshot_path), rendered)
            snapshots[alert_key] = str(snapshot_path)
        privacy_frame, frame_redacted = apply_privacy(
            frame,
            active_tracks,
            zones,
            bool(detector_config.get("anonymize_persons", False)),
        )
        privacy_applied = privacy_applied or frame_redacted
        writer.write(_draw_frame(privacy_frame, active_tracks, zones, frame_alerts))
        processed_frames += 1
        if progress_callback and processed_frames % 5 == 0:
            progress_callback(min(0.99, frame_index / max(frame_count, 1)), {"processed_frames": processed_frames, "timestamp_seconds": timestamp_seconds})
        frame_index += 1
    capture.release()
    writer.release()
    tracks = tracker.finalize()
    observation_path = output_root / "observations.json.gz"
    with gzip.open(observation_path, "wt", encoding="utf-8") as handle:
        json.dump(observations, handle)
    before_seconds = float(detector_config.get("evidence_before_seconds", 3.0))
    after_seconds = float(detector_config.get("evidence_after_seconds", 3.0))
    for alert in alerts:
        alert_key = _alert_key(alert)
        clip_path = output_root / f"alert-{alert_key}.mp4"
        if _extract_clip(
            annotated_path,
            clip_path,
            alert.timestamp_seconds,
            before_seconds,
            after_seconds,
        ):
            evidence_clips[alert_key] = str(clip_path)
    elapsed = max(time.perf_counter() - started, 1e-9)
    metadata.update(
        {
            "processed_frames": processed_frames,
            "sample_every": sample_every,
            "processing_seconds": elapsed,
            "processing_fps": processed_frames / elapsed,
            "detector_backend": detector_backend,
            "metric_calibration": metric_scale is not None,
            "privacy_applied": privacy_applied,
            "observation_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
        }
    )
    if progress_callback:
        progress_callback(1.0, metadata)
    return PipelineResult(
        metadata,
        tracks,
        alerts,
        milestones,
        str(observation_path),
        str(annotated_path),
        snapshots,
        evidence_clips,
    )
