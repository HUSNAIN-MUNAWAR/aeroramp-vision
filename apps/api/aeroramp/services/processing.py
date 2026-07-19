from __future__ import annotations

import logging
import math
from typing import Any

from aeroramp.core.config import get_settings
from aeroramp.db.models import (
    Camera,
    CameraCalibration,
    CameraZone,
    EvidenceAsset,
    Notification,
    ObjectTrack,
    OperationalEvent,
    ProcessingJob,
    SafetyAlert,
    SafetyRule,
    Turnaround,
    TurnaroundMilestone,
    UploadedVideo,
)
from aeroramp.db.session import SessionLocal
from aeroramp.services.storage import sha256_file
from aeroramp.vision.milestones import MilestoneRule
from aeroramp.vision.pipeline import process_video
from aeroramp.vision.rules import RuleConfig, deduplication_key
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _metric_scale(calibration: CameraCalibration | None) -> float | None:
    if not calibration or calibration.ground_plane_units not in {"meter", "meters", "m"}:
        return None
    if not calibration.reference_points:
        return None
    raw_scales = [p.get("meters_per_pixel") for p in calibration.reference_points if isinstance(p, dict)]
    scales: list[float] = [float(v) for v in raw_scales if v is not None]
    return sum(scales) / len(scales) if scales else None


def _velocity_summary(points: list[Any]) -> dict[str, Any]:
    if len(points) < 2:
        return {"mean_pixels_per_second": 0.0, "direction_degrees": None}
    speeds: list[float] = []
    for first, second in zip(points, points[1:], strict=False):
        dt = second.timestamp_seconds - first.timestamp_seconds
        if dt > 0:
            speeds.append(math.dist(first.centroid, second.centroid) / dt)
    first, last = points[0], points[-1]
    direction = math.degrees(math.atan2(last.centroid[1] - first.centroid[1], last.centroid[0] - first.centroid[0]))
    return {"mean_pixels_per_second": sum(speeds) / max(len(speeds), 1), "direction_degrees": direction, "metric": False}


def run_processing_job(job_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if not job:
            raise ValueError("Processing job not found")
        current_job: ProcessingJob = job
        video = db.get(UploadedVideo, current_job.video_id)
        camera = db.get(Camera, current_job.camera_id)
        if not video or not camera:
            raise ValueError("Processing job has missing video or camera")
        current_job.status = "preparing"
        current_job.progress = 0.01
        db.commit()
        zones = list(db.scalars(select(CameraZone).where(CameraZone.camera_id == camera.id, CameraZone.organization_id == current_job.organization_id, CameraZone.active.is_(True))))
        rules = list(db.scalars(select(SafetyRule).where(SafetyRule.camera_id == camera.id, SafetyRule.organization_id == current_job.organization_id, SafetyRule.active.is_(True))))
        zone_map = {zone.id: zone for zone in zones}
        calibration = db.scalar(select(CameraCalibration).where(CameraCalibration.camera_id == camera.id, CameraCalibration.organization_id == current_job.organization_id, CameraCalibration.active.is_(True)).order_by(CameraCalibration.version.desc()))
        vision_rules = [
            RuleConfig(
                id=rule.id,
                rule_type=rule.rule_type,
                severity=rule.severity,
                zone_id=rule.zone_id,
                polygon=zone_map[rule.zone_id].polygon if rule.zone_id and rule.zone_id in zone_map else None,
                config=rule.config,
                debounce_seconds=rule.debounce_seconds,
                cooldown_seconds=rule.cooldown_seconds,
            )
            for rule in rules
        ]
        milestone_rules: list[MilestoneRule] = []
        for zone in zones:
            if zone.zone_type == "aircraft_safety_envelope":
                milestone_rules.append(MilestoneRule("aircraft_on_block", "aircraft", zone.polygon, 2.0, "rule_inference"))
            if zone.zone_type in {"service_zone", "equipment_staging_area"}:
                milestone_rules.append(MilestoneRule("unclassified_service_vehicle_present", "service_vehicle", zone.polygon, 1.0, "rule_inference"))
        output_dir = settings.evidence_dir / current_job.id
        current_job.status = "running"
        db.commit()

        def progress(value: float, metrics: dict[str, Any]) -> None:
            current_job.progress = value
            current_job.metrics = {**(current_job.metrics or {}), **metrics}
            db.commit()

        def cancelled() -> bool:
            db.refresh(current_job)
            return current_job.cancel_requested

        try:
            result = process_video(
                video.storage_path,
                output_dir,
                current_job.detector_backend,
                camera.processing_profile or {},
                [
                    {
                        "id": z.id,
                        "name": z.name,
                        "polygon": z.polygon,
                        "zone_type": z.zone_type,
                    }
                    for z in zones
                ]
                + [
                    {
                        "id": f"camera-privacy-{index}",
                        "name": f"Camera privacy mask {index + 1}",
                        "polygon": polygon,
                        "zone_type": "privacy_mask",
                    }
                    for index, polygon in enumerate(camera.privacy_regions or [])
                ],
                vision_rules,
                milestone_rules,
                target_fps=float((camera.processing_profile or {}).get("inference_fps", settings.inference_fps)),
                metric_scale=_metric_scale(calibration),
                progress_callback=progress,
                cancel_callback=cancelled,
            )
            track_db_ids: dict[int, str] = {}
            for track in result.tracks:
                if not track.points:
                    continue
                track_row = ObjectTrack(
                    organization_id=current_job.organization_id,
                    camera_id=current_job.camera_id,
                    processing_job_id=current_job.id,
                    turnaround_id=current_job.turnaround_id,
                    external_track_id=track.track_id,
                    object_class=track.class_name,
                    start_seconds=track.points[0].timestamp_seconds,
                    end_seconds=track.points[-1].timestamp_seconds,
                    confidence_mean=track.confidence_mean,
                    bbox_history_path=result.observation_path,
                    centroid_history=[{"timestamp_seconds": p.timestamp_seconds, "centroid": p.centroid, "bbox": p.bbox, "confidence": p.confidence} for p in track.points],
                    velocity_summary=_velocity_summary(track.points),
                    zone_history=[],
                    status="terminated",
                )
                db.add(track_row)
                db.flush()
                track_db_ids[track.track_id] = track_row.id
            for milestone in result.milestones:
                if not current_job.turnaround_id:
                    continue
                existing = db.scalar(select(TurnaroundMilestone).where(TurnaroundMilestone.turnaround_id == current_job.turnaround_id, TurnaroundMilestone.milestone_type == milestone.milestone_type, TurnaroundMilestone.organization_id == current_job.organization_id))
                if existing:
                    continue
                milestone_row = TurnaroundMilestone(
                    organization_id=current_job.organization_id,
                    turnaround_id=current_job.turnaround_id,
                    milestone_type=milestone.milestone_type,
                    timestamp_seconds=milestone.timestamp_seconds,
                    end_seconds=None,
                    observation_kind=milestone.observation_kind,
                    confidence=milestone.confidence,
                    supporting_track_ids=[track_db_ids[x] for x in milestone.supporting_track_ids if x in track_db_ids],
                    original_prediction={"metadata": milestone.metadata, "timestamp_seconds": milestone.timestamp_seconds},
                )
                db.add(milestone_row)
                db.add(OperationalEvent(
                    organization_id=current_job.organization_id,
                    camera_id=current_job.camera_id,
                    processing_job_id=current_job.id,
                    turnaround_id=current_job.turnaround_id,
                    event_type=milestone.milestone_type,
                    timestamp_seconds=milestone.timestamp_seconds,
                    observation_kind=milestone.observation_kind,
                    confidence=milestone.confidence,
                    supporting_track_ids=milestone_row.supporting_track_ids,
                    metadata_json=milestone.metadata,
                ))
            for candidate in result.alerts:
                key = deduplication_key(candidate, current_job.id)
                if db.scalar(select(SafetyAlert).where(SafetyAlert.deduplication_key == key, SafetyAlert.organization_id == current_job.organization_id)):
                    continue
                related = [track_db_ids[candidate.track_id]] if candidate.track_id in track_db_ids else []
                prefix = f"{candidate.rule_id}-{candidate.track_id}-"
                snapshot_match = next(
                    (path for snapshot_key, path in result.snapshots.items() if snapshot_key.startswith(prefix)),
                    None,
                )
                clip_match = next(
                    (path for clip_key, path in result.evidence_clips.items() if clip_key.startswith(prefix)),
                    result.annotated_video_path,
                )
                alert = SafetyAlert(
                    organization_id=current_job.organization_id,
                    rule_id=candidate.rule_id,
                    camera_id=current_job.camera_id,
                    stand_id=camera.stand_id,
                    turnaround_id=current_job.turnaround_id,
                    timestamp_seconds=candidate.timestamp_seconds,
                    severity=candidate.severity,
                    confidence=candidate.confidence,
                    related_track_ids=related,
                    zone_id=candidate.zone_id,
                    evidence_snapshot_path=snapshot_match,
                    evidence_clip_path=clip_match,
                    event_metadata=candidate.metadata,
                    status="new",
                    deduplication_key=key,
                )
                db.add(alert)
                db.flush()
                db.add(Notification(organization_id=current_job.organization_id, notification_type="high_severity_alert" if candidate.severity in {"high", "critical"} else "safety_alert", payload={"alert_id": alert.id, "rule_type": candidate.rule_type, "severity": candidate.severity}, status="pending"))
                evidence_metadata = {
                    "rule_version": 1,
                    "camera_calibration_version": calibration.version if calibration else None,
                    "pre_event_seconds": float((camera.processing_profile or {}).get("evidence_before_seconds", 3.0)),
                    "post_event_seconds": float((camera.processing_profile or {}).get("evidence_after_seconds", 3.0)),
                }
                if snapshot_match:
                    db.add(
                        EvidenceAsset(
                            organization_id=current_job.organization_id,
                            alert_id=alert.id,
                            asset_type="snapshot",
                            storage_path=snapshot_match,
                            sha256=sha256_file(snapshot_match),
                            redacted=bool(result.metadata.get("privacy_applied")),
                            metadata_json={
                                **evidence_metadata,
                                "privacy_applied": bool(
                                    result.metadata.get("privacy_applied")
                                ),
                            },
                        )
                    )
                if clip_match:
                    db.add(
                        EvidenceAsset(
                            organization_id=current_job.organization_id,
                            alert_id=alert.id,
                            asset_type="clip",
                            storage_path=clip_match,
                            sha256=sha256_file(clip_match),
                            redacted=bool(result.metadata.get("privacy_applied")),
                            metadata_json={
                                **evidence_metadata,
                                "privacy_applied": bool(
                                    result.metadata.get("privacy_applied")
                                ),
                            },
                        )
                    )
            if current_job.turnaround_id:
                turnaround = db.get(Turnaround, current_job.turnaround_id)
                if turnaround and any(m.milestone_type == "aircraft_on_block" for m in result.milestones):
                    turnaround.status = "on_stand"
                    turnaround.detection_confidence = max(m.confidence for m in result.milestones if m.milestone_type == "aircraft_on_block")
            current_job.status = "completed"
            current_job.progress = 1.0
            current_job.metrics = result.metadata
            db.commit()
        except Exception as exc:
            logger.exception("processing_job_failed", extra={"job_id": current_job.id, "camera_id": current_job.camera_id})
            db.rollback()
            failed_job = db.get(ProcessingJob, job_id)
            if failed_job:
                failed_job.status = "cancelled" if "cancelled" in str(exc).lower() else "failed"
                failed_job.error_code = (
                    "PROCESSING_CANCELLED"
                    if failed_job.status == "cancelled"
                    else "VIDEO_PROCESSING_FAILED"
                )
                failed_job.error_message = str(exc)
                db.commit()
            raise
