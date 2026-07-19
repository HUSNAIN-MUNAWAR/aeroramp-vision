from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func, select

from aeroramp.api.deps import AuthContext, CurrentContext, DbSession, require_permission
from aeroramp.api.schemas import (
    AirportCreate,
    AirportOut,
    AlertOut,
    AlertReview,
    CalibrationCreate,
    CameraCreate,
    CameraOut,
    EdgeSyncRequest,
    IncidentCreate,
    IncidentNoteCreate,
    IncidentNoteOut,
    IncidentOut,
    IncidentUpdate,
    LoginRequest,
    MilestoneCorrection,
    MilestoneOut,
    ModelDeploymentCreate,
    ModelDeploymentOut,
    ModelDeploymentRollback,
    ModelVersionCreate,
    OrganizationOut,
    ProcessingJobOut,
    RuleCreate,
    RuleOut,
    StandCreate,
    StandOut,
    TokenResponse,
    TrackOut,
    TurnaroundCreate,
    TurnaroundOut,
    UserOut,
    ZoneCreate,
    ZoneOut,
)
from aeroramp.core.config import get_settings
from aeroramp.core.security import create_token, decode_token, verify_password
from aeroramp.db.models import (
    Airport,
    AuditLog,
    Camera,
    CameraCalibration,
    CameraZone,
    EdgeNode,
    EdgeSyncBatch,
    Incident,
    IncidentNote,
    ModelDeployment,
    ModelVersion,
    ObjectTrack,
    OperationalEvent,
    Organization,
    OrganizationMembership,
    ProcessingJob,
    ReviewDecision,
    SafetyAlert,
    SafetyRule,
    Stand,
    Turnaround,
    TurnaroundMilestone,
    UploadedVideo,
    User,
)
from aeroramp.services.audit import record_audit
from aeroramp.services.processing import run_processing_job
from aeroramp.services.storage import encrypt_secret, validate_video_name
from aeroramp.vision.geometry import valid_polygon
from aeroramp.vision.milestones import evaluate_readiness
from aeroramp.vision.pipeline import probe_video

router = APIRouter(prefix="/api/v1")
settings = get_settings()

DISCLAIMER = (
    "AeroRamp Vision is an operational decision-support and analytics platform. "
    "Production deployment requires airport-specific validation, camera calibration, safety assessment, "
    "cybersecurity review, privacy review, legal review, and approval from relevant airport and aviation authorities."
)


def _ensure_tenant(row: Any, context: AuthContext) -> Any:
    if row is None or getattr(row, "organization_id", None) != context.organization_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    return row


def _audit_request(request: Request) -> tuple[str | None, dict[str, Any]]:
    return (
        getattr(request.state, "request_id", None),
        {"client": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent")},
    )


@router.get("/system/info")
def system_info() -> dict[str, Any]:
    return {
        "name": "AeroRamp Vision",
        "version": "0.1.0",
        "environment": settings.environment,
        "aviation_disclaimer": DISCLAIMER,
        "biometric_identification": False,
        "decision_support_only": True,
    }


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    request_id, ip_metadata = _audit_request(request)
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id))
            if membership:
                record_audit(db, membership.organization_id, user.id, "login.failed", "user", user.id, request_id=request_id, ip_metadata=ip_metadata)
                db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    memberships = list(db.scalars(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)))
    membership = next((m for m in memberships if m.organization_id == payload.organization_id), None) if payload.organization_id else (memberships[0] if memberships else None)
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership available")
    record_audit(db, membership.organization_id, user.id, "login.success", "user", user.id, request_id=request_id, ip_metadata=ip_metadata)
    db.commit()
    return TokenResponse(
        access_token=create_token(user.id, membership.organization_id, membership.role, "access"),
        refresh_token=create_token(user.id, membership.organization_id, membership.role, "refresh"),
        organization_id=membership.organization_id,
        role=membership.role,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(refresh_token: Annotated[str, Form()]) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    return TokenResponse(
        access_token=create_token(str(payload["sub"]), str(payload["org"]), str(payload["role"]), "access"),
        refresh_token=create_token(str(payload["sub"]), str(payload["org"]), str(payload["role"]), "refresh"),
        organization_id=str(payload["org"]),
        role=str(payload["role"]),
    )


@router.get("/auth/me", response_model=UserOut)
def me(context: CurrentContext) -> UserOut:
    return UserOut.model_validate(context.user).model_copy(update={"role": context.role, "organization_id": context.organization_id})


@router.get("/organizations/current", response_model=OrganizationOut)
def current_organization(context: CurrentContext, db: DbSession) -> Organization:
    row = db.get(Organization, context.organization_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return row


@router.get("/airports", response_model=list[AirportOut])
def list_airports(context: CurrentContext, db: DbSession, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> list[Airport]:
    return list(db.scalars(select(Airport).where(Airport.organization_id == context.organization_id).order_by(Airport.name).limit(limit).offset(offset)))


@router.post("/airports", response_model=AirportOut, status_code=201)
def create_airport(payload: AirportCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("airports.manage"))]) -> Airport:
    row = Airport(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "airport.create", "airport", row.id, new_state=payload.model_dump(mode="json"), request_id=request_id, ip_metadata=ip)
    db.commit()
    db.refresh(row)
    return row


@router.get("/stands", response_model=list[StandOut])
def list_stands(context: CurrentContext, db: DbSession, airport_id: str | None = None) -> list[Stand]:
    query = select(Stand).where(Stand.organization_id == context.organization_id)
    if airport_id:
        query = query.where(Stand.airport_id == airport_id)
    return list(db.scalars(query.order_by(Stand.code)))


@router.post("/stands", response_model=StandOut, status_code=201)
def create_stand(payload: StandCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("stands.manage"))]) -> Stand:
    _ensure_tenant(db.get(Airport, payload.airport_id), context)
    row = Stand(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "stand.create", "stand", row.id, new_state=payload.model_dump(mode="json"), request_id=request_id, ip_metadata=ip)
    db.commit()
    return row


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(context: CurrentContext, db: DbSession, stand_id: str | None = None) -> list[Camera]:
    query = select(Camera).where(Camera.organization_id == context.organization_id)
    if stand_id:
        query = query.where(Camera.stand_id == stand_id)
    return list(db.scalars(query.order_by(Camera.name)))


@router.post("/cameras", response_model=CameraOut, status_code=201)
def create_camera(payload: CameraCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("cameras.manage"))]) -> Camera:
    _ensure_tenant(db.get(Airport, payload.airport_id), context)
    if payload.stand_id:
        _ensure_tenant(db.get(Stand, payload.stand_id), context)
    data = payload.model_dump(exclude={"stream_url"})
    row = Camera(organization_id=context.organization_id, **data, stream_url_encrypted=encrypt_secret(payload.stream_url) if payload.stream_url else None)
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "camera.create", "camera", row.id, new_state={**data, "stream_url": "[REDACTED]" if payload.stream_url else None}, request_id=request_id, ip_metadata=ip)
    db.commit()
    return row


@router.post("/calibrations", status_code=201)
def create_calibration(payload: CalibrationCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("zones.manage"))]) -> dict[str, Any]:
    camera = _ensure_tenant(db.get(Camera, payload.camera_id), context)
    previous = db.scalar(select(CameraCalibration).where(CameraCalibration.camera_id == camera.id, CameraCalibration.organization_id == context.organization_id, CameraCalibration.active.is_(True)).order_by(CameraCalibration.version.desc()))
    if previous:
        previous.active = False
    version = (previous.version + 1) if previous else 1
    row = CameraCalibration(organization_id=context.organization_id, version=version, active=True, **payload.model_dump())
    db.add(row)
    camera.calibration_state = "calibrated_metric" if payload.ground_plane_units in {"meter", "meters", "m"} else "calibrated_image_space"
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "calibration.create", "camera_calibration", row.id, previous_state={"version": previous.version} if previous else {}, new_state={"version": version, **payload.model_dump(mode="json")}, request_id=request_id, ip_metadata=ip)
    db.commit()
    return {"id": row.id, "camera_id": row.camera_id, "version": row.version, "ground_plane_units": row.ground_plane_units, "active": row.active}


@router.get("/zones", response_model=list[ZoneOut])
def list_zones(context: CurrentContext, db: DbSession, camera_id: str | None = None) -> list[CameraZone]:
    query = select(CameraZone).where(CameraZone.organization_id == context.organization_id, CameraZone.active.is_(True))
    if camera_id:
        query = query.where(CameraZone.camera_id == camera_id)
    return list(db.scalars(query.order_by(CameraZone.name)))


@router.post("/zones", response_model=ZoneOut, status_code=201)
def create_zone(payload: ZoneCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("zones.manage"))]) -> CameraZone:
    _ensure_tenant(db.get(Camera, payload.camera_id), context)
    if not valid_polygon(payload.polygon):
        raise HTTPException(status_code=422, detail="Polygon must contain at least three points and be geometrically valid")
    row = CameraZone(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "zone.create", "camera_zone", row.id, new_state=payload.model_dump(mode="json"), request_id=request_id, ip_metadata=ip)
    db.commit()
    return row


@router.get("/safety-rules", response_model=list[RuleOut])
def list_rules(context: CurrentContext, db: DbSession, camera_id: str | None = None) -> list[SafetyRule]:
    query = select(SafetyRule).where(SafetyRule.organization_id == context.organization_id, SafetyRule.active.is_(True))
    if camera_id:
        query = query.where(SafetyRule.camera_id == camera_id)
    return list(db.scalars(query.order_by(SafetyRule.name)))


@router.post("/safety-rules", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("zones.manage"))]) -> SafetyRule:
    _ensure_tenant(db.get(Camera, payload.camera_id), context)
    if payload.zone_id:
        _ensure_tenant(db.get(CameraZone, payload.zone_id), context)
    if payload.rule_type == "excess_speed":
        calibration = db.scalar(select(CameraCalibration).where(CameraCalibration.camera_id == payload.camera_id, CameraCalibration.organization_id == context.organization_id, CameraCalibration.active.is_(True)))
        if not calibration or calibration.ground_plane_units not in {"meter", "meters", "m"}:
            raise HTTPException(status_code=409, detail={"code": "CAMERA_CALIBRATION_REQUIRED", "message": "This safety rule requires metric camera calibration."})
    row = SafetyRule(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "rule.create", "safety_rule", row.id, new_state=payload.model_dump(mode="json"), request_id=request_id, ip_metadata=ip)
    db.commit()
    return row


@router.get("/turnarounds", response_model=list[TurnaroundOut])
def list_turnarounds(context: CurrentContext, db: DbSession, status_filter: str | None = Query(None, alias="status"), limit: int = Query(100, ge=1, le=500)) -> list[Turnaround]:
    query = select(Turnaround).where(Turnaround.organization_id == context.organization_id)
    if status_filter:
        query = query.where(Turnaround.status == status_filter)
    return list(db.scalars(query.order_by(Turnaround.created_at.desc()).limit(limit)))


@router.post("/turnarounds", response_model=TurnaroundOut, status_code=201)
def create_turnaround(payload: TurnaroundCreate, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("turnarounds.manage"))]) -> Turnaround:
    _ensure_tenant(db.get(Airport, payload.airport_id), context)
    _ensure_tenant(db.get(Stand, payload.stand_id), context)
    row = Turnaround(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.get("/turnarounds/{turnaround_id}")
def get_turnaround(turnaround_id: str, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    row = _ensure_tenant(db.get(Turnaround, turnaround_id), context)
    milestones = list(db.scalars(select(TurnaroundMilestone).where(TurnaroundMilestone.turnaround_id == row.id, TurnaroundMilestone.organization_id == context.organization_id).order_by(TurnaroundMilestone.timestamp_seconds)))
    alerts = list(db.scalars(select(SafetyAlert).where(SafetyAlert.turnaround_id == row.id, SafetyAlert.organization_id == context.organization_id).order_by(SafetyAlert.timestamp_seconds)))
    active_high = sum(1 for alert in alerts if alert.severity in {"high", "critical"} and alert.status in {"new", "acknowledged", "under_review", "escalated"})
    milestone_types = {m.milestone_type for m in milestones}
    readiness = evaluate_readiness(milestone_types, active_high)
    kpis: dict[str, Any] = {
        "milestone_count": len(milestones),
        "alert_count": len(alerts),
        "confirmed_alert_count": sum(1 for a in alerts if a.status == "confirmed"),
        "manual_corrections": sum(1 for m in milestones if m.manual_override),
    }
    if row.actual_on_block and row.actual_off_block:
        kpis["turnaround_duration_minutes"] = (row.actual_off_block - row.actual_on_block).total_seconds() / 60
    return {
        "turnaround": TurnaroundOut.model_validate(row),
        "milestones": [MilestoneOut.model_validate(m) for m in milestones],
        "alerts": [AlertOut.model_validate(a) for a in alerts],
        "readiness": readiness,
        "kpis": kpis,
        "aviation_disclaimer": DISCLAIMER,
    }


@router.post("/videos/upload", response_model=ProcessingJobOut, status_code=201)
def upload_video(
    background_tasks: BackgroundTasks,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("videos.upload"))],
    camera_id: Annotated[str, Form()],
    turnaround_id: Annotated[str | None, Form()] = None,
    detector_backend: Annotated[str, Form()] = "motion",
    run_now: Annotated[bool, Form()] = False,
    file: UploadFile = File(...),
) -> ProcessingJob:
    camera = _ensure_tenant(db.get(Camera, camera_id), context)
    if turnaround_id:
        _ensure_tenant(db.get(Turnaround, turnaround_id), context)
    try:
        clean_name = validate_video_name(file.filename or "upload.bin")
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    upload_id = __import__("uuid").uuid4().hex
    destination = settings.upload_dir / f"{upload_id}-{clean_name}"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    with destination.open("wb") as handle:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Uploaded video exceeds configured size limit")
            handle.write(chunk)
    try:
        metadata = probe_video(destination)
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    video = UploadedVideo(
        organization_id=context.organization_id,
        camera_id=camera.id,
        original_name=clean_name,
        storage_path=str(destination),
        content_type=file.content_type or "application/octet-stream",
        size_bytes=written,
        duration_seconds=metadata["duration_seconds"],
        width=metadata["width"],
        height=metadata["height"],
        fps=metadata["fps"],
    )
    db.add(video)
    db.flush()
    job = ProcessingJob(organization_id=context.organization_id, camera_id=camera.id, video_id=video.id, turnaround_id=turnaround_id, status="queued", progress=0.0, detector_backend=detector_backend)
    db.add(job)
    db.commit()
    if run_now:
        background_tasks.add_task(run_processing_job, job.id)
    return job


@router.get("/processing-jobs", response_model=list[ProcessingJobOut])
def list_jobs(context: CurrentContext, db: DbSession, limit: int = Query(100, ge=1, le=500)) -> list[ProcessingJob]:
    return list(db.scalars(select(ProcessingJob).where(ProcessingJob.organization_id == context.organization_id).order_by(ProcessingJob.created_at.desc()).limit(limit)))


@router.get("/processing-jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: str, context: CurrentContext, db: DbSession) -> ProcessingJob:
    return _ensure_tenant(db.get(ProcessingJob, job_id), context)


@router.post("/processing-jobs/{job_id}/run", response_model=ProcessingJobOut)
def run_job(job_id: str, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("videos.process"))]) -> ProcessingJob:
    job = _ensure_tenant(db.get(ProcessingJob, job_id), context)
    if job.status not in {"queued", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Job is already running or completed")
    run_processing_job(job.id)
    db.expire_all()
    return _ensure_tenant(db.get(ProcessingJob, job_id), context)


@router.post("/processing-jobs/{job_id}/cancel", response_model=ProcessingJobOut)
def cancel_job(job_id: str, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("videos.process"))]) -> ProcessingJob:
    job = _ensure_tenant(db.get(ProcessingJob, job_id), context)
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    job.cancel_requested = True
    db.commit()
    return job


@router.get("/processing-jobs/{job_id}/events")
async def job_events(job_id: str, context: CurrentContext, db: DbSession) -> StreamingResponse:
    _ensure_tenant(db.get(ProcessingJob, job_id), context)

    async def stream():
        while True:
            db.expire_all()
            job = db.get(ProcessingJob, job_id)
            if not job:
                yield "event: error\ndata: {\"message\":\"Job not found\"}\n\n"
                return
            payload = ProcessingJobOut.model_validate(job).model_dump(mode="json")
            yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
            if job.status in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/tracks", response_model=list[TrackOut])
def list_tracks(context: CurrentContext, db: DbSession, processing_job_id: str, start_seconds: float | None = None, end_seconds: float | None = None) -> list[ObjectTrack]:
    _ensure_tenant(db.get(ProcessingJob, processing_job_id), context)
    query = select(ObjectTrack).where(ObjectTrack.organization_id == context.organization_id, ObjectTrack.processing_job_id == processing_job_id)
    if start_seconds is not None:
        query = query.where(ObjectTrack.end_seconds >= start_seconds)
    if end_seconds is not None:
        query = query.where(ObjectTrack.start_seconds <= end_seconds)
    return list(db.scalars(query.order_by(ObjectTrack.external_track_id)))


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(context: CurrentContext, db: DbSession, status_filter: str | None = Query(None, alias="status"), severity: str | None = None, limit: int = Query(200, ge=1, le=1000)) -> list[SafetyAlert]:
    query = select(SafetyAlert).where(SafetyAlert.organization_id == context.organization_id)
    if status_filter:
        query = query.where(SafetyAlert.status == status_filter)
    if severity:
        query = query.where(SafetyAlert.severity == severity)
    return list(db.scalars(query.order_by(SafetyAlert.created_at.desc()).limit(limit)))


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def review_alert(alert_id: str, payload: AlertReview, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("alerts.resolve"))]) -> SafetyAlert:
    allowed = {"acknowledged", "under_review", "confirmed", "false_positive", "resolved", "escalated", "dismissed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported alert status: {payload.status}")
    alert = _ensure_tenant(db.get(SafetyAlert, alert_id), context)
    previous = {"status": alert.status, "review_notes": alert.review_notes, "resolution_reason": alert.resolution_reason}
    alert.status = payload.status
    alert.review_notes = payload.notes
    alert.resolution_reason = payload.resolution_reason
    alert.assigned_reviewer_id = context.user.id
    db.add(ReviewDecision(organization_id=context.organization_id, resource_type="safety_alert", resource_id=alert.id, reviewer_id=context.user.id, decision=payload.status, previous_value=previous, corrected_value=payload.model_dump(), reason=payload.notes or payload.resolution_reason or "Alert lifecycle update"))
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, f"alert.{payload.status}", "safety_alert", alert.id, previous_state=previous, new_state=payload.model_dump(), reason=payload.resolution_reason, request_id=request_id, ip_metadata=ip)
    db.commit()
    return alert


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    context: Annotated[AuthContext, Depends(require_permission("alerts.read"))],
    db: DbSession,
    status_filter: str | None = Query(None, alias="status"),
) -> list[Incident]:
    query = select(Incident).where(Incident.organization_id == context.organization_id)
    if status_filter:
        query = query.where(Incident.status == status_filter)
    return list(db.scalars(query.order_by(Incident.created_at.desc())))


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("incidents.manage"))],
) -> Incident:
    alert = _ensure_tenant(db.get(SafetyAlert, payload.alert_id), context)
    existing = db.scalar(
        select(Incident).where(
            Incident.organization_id == context.organization_id,
            Incident.alert_id == alert.id,
            Incident.status != "resolved",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="An active incident already exists for this alert")
    if payload.assigned_to_id:
        assignee = _ensure_tenant(
            db.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == context.organization_id,
                    OrganizationMembership.user_id == payload.assigned_to_id,
                )
            ),
            context,
        )
        assigned_to_id = assignee.user_id
    else:
        assigned_to_id = None
    incident = Incident(
        organization_id=context.organization_id,
        alert_id=alert.id,
        title=payload.title,
        severity=payload.severity or alert.severity,
        status="open",
        assigned_to_id=assigned_to_id,
    )
    alert.status = "escalated"
    db.add(incident)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "incident.create",
        "incident",
        incident.id,
        new_state={"alert_id": alert.id, "title": incident.title, "severity": incident.severity},
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    context: Annotated[AuthContext, Depends(require_permission("alerts.read"))],
    db: DbSession,
) -> dict[str, Any]:
    incident = _ensure_tenant(db.get(Incident, incident_id), context)
    notes = list(
        db.scalars(
            select(IncidentNote)
            .where(
                IncidentNote.organization_id == context.organization_id,
                IncidentNote.incident_id == incident.id,
            )
            .order_by(IncidentNote.created_at)
        )
    )
    return {
        "incident": IncidentOut.model_validate(incident),
        "notes": [IncidentNoteOut.model_validate(note) for note in notes],
    }


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("incidents.manage"))],
) -> Incident:
    incident = _ensure_tenant(db.get(Incident, incident_id), context)
    previous = {
        "status": incident.status,
        "classification": incident.classification,
        "resolution": incident.resolution,
        "assigned_to_id": incident.assigned_to_id,
    }
    updates = payload.model_dump(exclude_unset=True)
    if "assigned_to_id" in updates and updates["assigned_to_id"]:
        membership = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == context.organization_id,
                OrganizationMembership.user_id == updates["assigned_to_id"],
            )
        )
        if not membership:
            raise HTTPException(status_code=422, detail="Incident assignee is not in this organization")
    for field, value in updates.items():
        setattr(incident, field, value)
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "incident.update",
        "incident",
        incident.id,
        previous_state=previous,
        new_state=updates,
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.post("/incidents/{incident_id}/notes", response_model=IncidentNoteOut, status_code=201)
def add_incident_note(
    incident_id: str,
    payload: IncidentNoteCreate,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("incidents.manage"))],
) -> IncidentNote:
    incident = _ensure_tenant(db.get(Incident, incident_id), context)
    note = IncidentNote(
        organization_id=context.organization_id,
        incident_id=incident.id,
        author_id=context.user.id,
        body=payload.body,
    )
    db.add(note)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "incident.note.create",
        "incident",
        incident.id,
        new_state={"note_id": note.id},
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    db.refresh(note)
    return note


@router.get("/milestones", response_model=list[MilestoneOut])
def list_milestones(context: CurrentContext, db: DbSession, turnaround_id: str) -> list[TurnaroundMilestone]:
    _ensure_tenant(db.get(Turnaround, turnaround_id), context)
    return list(db.scalars(select(TurnaroundMilestone).where(TurnaroundMilestone.organization_id == context.organization_id, TurnaroundMilestone.turnaround_id == turnaround_id).order_by(TurnaroundMilestone.timestamp_seconds)))


@router.patch("/milestones/{milestone_id}", response_model=MilestoneOut)
def correct_milestone(milestone_id: str, payload: MilestoneCorrection, request: Request, db: DbSession, context: Annotated[AuthContext, Depends(require_permission("events.correct"))]) -> TurnaroundMilestone:
    milestone = _ensure_tenant(db.get(TurnaroundMilestone, milestone_id), context)
    previous = {"milestone_type": milestone.milestone_type, "timestamp_seconds": milestone.timestamp_seconds, "observation_kind": milestone.observation_kind}
    milestone.milestone_type = payload.milestone_type or milestone.milestone_type
    milestone.timestamp_seconds = payload.timestamp_seconds
    milestone.manual_override = True
    milestone.override_reason = payload.reason
    milestone.reviewer_id = context.user.id
    milestone.observation_kind = "manual_correction"
    db.add(ReviewDecision(organization_id=context.organization_id, resource_type="turnaround_milestone", resource_id=milestone.id, reviewer_id=context.user.id, decision="corrected", previous_value=previous, corrected_value=payload.model_dump(), reason=payload.reason))
    request_id, ip = _audit_request(request)
    record_audit(db, context.organization_id, context.user.id, "milestone.correct", "turnaround_milestone", milestone.id, previous_state=previous, new_state=payload.model_dump(), reason=payload.reason, request_id=request_id, ip_metadata=ip)
    db.commit()
    return milestone


@router.get("/dashboard")
def dashboard(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    active_turnarounds = db.scalar(select(func.count()).select_from(Turnaround).where(Turnaround.organization_id == context.organization_id, Turnaround.status.in_(["aircraft_approaching", "on_stand", "servicing", "boarding", "departure_preparation", "pushback"]))) or 0
    active_alerts = db.scalar(select(func.count()).select_from(SafetyAlert).where(SafetyAlert.organization_id == context.organization_id, SafetyAlert.status.in_(["new", "acknowledged", "under_review", "escalated"]))) or 0
    high_alerts = db.scalar(select(func.count()).select_from(SafetyAlert).where(SafetyAlert.organization_id == context.organization_id, SafetyAlert.severity.in_(["high", "critical"]), SafetyAlert.status.in_(["new", "acknowledged", "under_review", "escalated"]))) or 0
    offline_cameras = db.scalar(select(func.count()).select_from(Camera).where(Camera.organization_id == context.organization_id, Camera.status.in_(["offline", "degraded"]))) or 0
    running_jobs = db.scalar(select(func.count()).select_from(ProcessingJob).where(ProcessingJob.organization_id == context.organization_id, ProcessingJob.status.in_(["queued", "preparing", "running"]))) or 0
    severity_rows = db.execute(select(SafetyAlert.severity, func.count()).where(SafetyAlert.organization_id == context.organization_id).group_by(SafetyAlert.severity)).all()
    alerts_by_severity: dict[str, int] = {str(name): int(count) for name, count in severity_rows}
    recent_alerts = list(db.scalars(select(SafetyAlert).where(SafetyAlert.organization_id == context.organization_id).order_by(SafetyAlert.created_at.desc()).limit(8)))
    recent_jobs = list(db.scalars(select(ProcessingJob).where(ProcessingJob.organization_id == context.organization_id).order_by(ProcessingJob.created_at.desc()).limit(8)))
    return {
        "kpis": {
            "active_turnarounds": active_turnarounds,
            "active_alerts": active_alerts,
            "high_severity_alerts": high_alerts,
            "offline_or_degraded_cameras": offline_cameras,
            "processing_jobs_in_flight": running_jobs,
        },
        "alerts_by_severity": alerts_by_severity,
        "recent_alerts": [AlertOut.model_validate(x) for x in recent_alerts],
        "recent_jobs": [ProcessingJobOut.model_validate(x) for x in recent_jobs],
        "aviation_disclaimer": DISCLAIMER,
    }


@router.get("/models")
def list_models(context: CurrentContext, db: DbSession) -> list[dict[str, Any]]:
    rows = list(db.scalars(select(ModelVersion).where(ModelVersion.organization_id == context.organization_id).order_by(ModelVersion.created_at.desc())))
    return [{"id": x.id, "name": x.name, "version": x.version, "framework": x.framework, "input_resolution": x.input_resolution, "class_list": x.class_list, "checkpoint_checksum": x.checkpoint_checksum, "validation_metrics": x.validation_metrics, "deployment_status": x.deployment_status, "safe_serialization": x.safe_serialization, "created_at": x.created_at} for x in rows]


@router.post("/models", status_code=201)
def register_model(
    payload: ModelVersionCreate,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("models.manage"))],
) -> dict[str, Any]:
    if payload.checkpoint_path and Path(payload.checkpoint_path).suffix.lower() not in {".onnx", ".safetensors"} and payload.safe_serialization:
        raise HTTPException(status_code=422, detail="Safe model registration accepts ONNX or safetensors. Pickle-based checkpoints require isolated review and safe_serialization=false.")
    row = ModelVersion(organization_id=context.organization_id, **payload.model_dump())
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "model.register",
        "model_version",
        row.id,
        new_state={
            **payload.model_dump(mode="json"),
            "checkpoint_path": "[REGISTERED]" if payload.checkpoint_path else None,
        },
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "deployment_status": row.deployment_status,
    }


@router.get("/model-deployments", response_model=list[ModelDeploymentOut])
def list_model_deployments(
    context: CurrentContext, db: DbSession
) -> list[ModelDeployment]:
    return list(
        db.scalars(
            select(ModelDeployment)
            .where(ModelDeployment.organization_id == context.organization_id)
            .order_by(ModelDeployment.deployed_at.desc())
        )
    )


@router.post("/model-deployments", response_model=ModelDeploymentOut, status_code=201)
def create_model_deployment(
    payload: ModelDeploymentCreate,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("models.manage"))],
) -> ModelDeployment:
    model = _ensure_tenant(db.get(ModelVersion, payload.model_version_id), context)
    if not model.safe_serialization:
        raise HTTPException(
            status_code=409,
            detail="Unsafe serialized models cannot be deployed through the standard workflow",
        )
    if bool(payload.camera_id) == bool(payload.edge_node_id):
        raise HTTPException(
            status_code=422, detail="Exactly one of camera_id or edge_node_id is required"
        )
    if payload.camera_id:
        _ensure_tenant(db.get(Camera, payload.camera_id), context)
    if payload.edge_node_id:
        _ensure_tenant(db.get(EdgeNode, payload.edge_node_id), context)
    previous_query = select(ModelDeployment).where(
        ModelDeployment.organization_id == context.organization_id,
        ModelDeployment.status == "active",
    )
    if payload.camera_id:
        previous_query = previous_query.where(ModelDeployment.camera_id == payload.camera_id)
    else:
        previous_query = previous_query.where(
            ModelDeployment.edge_node_id == payload.edge_node_id
        )
    previous = list(db.scalars(previous_query))
    for deployment in previous:
        deployment.status = "superseded"
    row = ModelDeployment(
        organization_id=context.organization_id,
        model_version_id=model.id,
        camera_id=payload.camera_id,
        edge_node_id=payload.edge_node_id,
        backend=payload.backend,
        status="active",
        configuration=payload.configuration,
        deployed_by_id=context.user.id,
    )
    model.deployment_status = "deployed"
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "model.deploy",
        "model_deployment",
        row.id,
        previous_state={"superseded_deployment_ids": [item.id for item in previous]},
        new_state=payload.model_dump(mode="json"),
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/model-deployments/{deployment_id}/rollback",
    response_model=ModelDeploymentOut,
    status_code=201,
)
def rollback_model_deployment(
    deployment_id: str,
    payload: ModelDeploymentRollback,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("models.manage"))],
) -> ModelDeployment:
    current = _ensure_tenant(db.get(ModelDeployment, deployment_id), context)
    target_model = _ensure_tenant(db.get(ModelVersion, payload.target_model_version_id), context)
    if not target_model.safe_serialization:
        raise HTTPException(status_code=409, detail="Rollback target is not a safe model format")
    current.status = "rolled_back"
    row = ModelDeployment(
        organization_id=context.organization_id,
        model_version_id=target_model.id,
        camera_id=current.camera_id,
        edge_node_id=current.edge_node_id,
        backend=current.backend,
        status="active",
        configuration=current.configuration,
        deployed_by_id=context.user.id,
        rollback_of_id=current.id,
    )
    target_model.deployment_status = "deployed"
    db.add(row)
    db.flush()
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "model.rollback",
        "model_deployment",
        row.id,
        previous_state={
            "deployment_id": current.id,
            "model_version_id": current.model_version_id,
        },
        new_state={
            "deployment_id": row.id,
            "model_version_id": target_model.id,
            "rollback_of_id": current.id,
        },
        reason=payload.reason,
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/edge-nodes/sync")
def edge_sync(
    payload: EdgeSyncRequest,
    request: Request,
    db: DbSession,
    edge_api_key: Annotated[str, Header(alias="X-Edge-Key")],
) -> dict[str, Any]:
    node = db.get(EdgeNode, payload.node_id)
    if not node or not verify_password(edge_api_key, node.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid edge node credentials")
    existing = db.scalar(
        select(EdgeSyncBatch).where(
            EdgeSyncBatch.organization_id == node.organization_id,
            EdgeSyncBatch.edge_node_id == node.id,
            EdgeSyncBatch.deduplication_key == payload.deduplication_key,
        )
    )
    if existing:
        return {
            "accepted": 0,
            "duplicate": True,
            "configuration_version": node.configuration_version,
        }
    accepted = 0
    for event in payload.events:
        camera_id = event.get("camera_id")
        if not camera_id:
            continue
        camera = db.get(Camera, camera_id)
        if not camera or camera.organization_id != node.organization_id:
            continue
        db.add(
            OperationalEvent(
                organization_id=node.organization_id,
                camera_id=camera_id,
                processing_job_id=event.get("processing_job_id"),
                turnaround_id=event.get("turnaround_id"),
                event_type=event.get("event_type", "edge_event"),
                timestamp_seconds=float(event.get("timestamp_seconds", 0)),
                observation_kind="edge_sync",
                confidence=float(event.get("confidence", 0.5)),
                supporting_track_ids=event.get("supporting_track_ids", []),
                metadata_json={
                    **event.get("metadata", {}),
                    "edge_deduplication_key": payload.deduplication_key,
                    "edge_node_id": node.id,
                },
            )
        )
        accepted += 1
    payload_bytes = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    db.add(
        EdgeSyncBatch(
            organization_id=node.organization_id,
            edge_node_id=node.id,
            deduplication_key=payload.deduplication_key,
            event_count=len(payload.events),
            accepted_count=accepted,
            payload_sha256=hashlib.sha256(payload_bytes).hexdigest(),
            status="accepted",
        )
    )
    node.status = "online"
    node.last_sync_at = datetime.now(UTC)
    node.health = payload.health
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        node.organization_id,
        None,
        "edge.sync",
        "edge_node",
        node.id,
        new_state={
            "accepted": accepted,
            "event_count": len(payload.events),
            "deduplication_key": payload.deduplication_key,
        },
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    return {
        "accepted": accepted,
        "duplicate": False,
        "configuration_version": node.configuration_version,
    }


@router.get("/audit-logs")
def list_audit_logs(context: Annotated[AuthContext, Depends(require_permission("audit.read"))], db: DbSession, limit: int = Query(200, ge=1, le=1000)) -> list[dict[str, Any]]:
    rows = list(db.scalars(select(AuditLog).where(AuditLog.organization_id == context.organization_id).order_by(AuditLog.created_at.desc()).limit(limit)))
    return [{"id": x.id, "actor_id": x.actor_id, "action": x.action, "resource_type": x.resource_type, "resource_id": x.resource_id, "reason": x.reason, "request_id": x.request_id, "created_at": x.created_at} for x in rows]


@router.get("/reports/alerts.csv")
def alert_report(
    request: Request,
    context: Annotated[AuthContext, Depends(require_permission("reports.export"))],
    db: DbSession,
    severity: str | None = None,
) -> Response:
    query = select(SafetyAlert).where(SafetyAlert.organization_id == context.organization_id)
    if severity:
        query = query.where(SafetyAlert.severity == severity)
    rows = list(db.scalars(query.order_by(SafetyAlert.created_at.desc())))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["alert_id", "camera_id", "stand_id", "turnaround_id", "severity", "confidence", "status", "timestamp_seconds", "created_at"])
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.camera_id,
                row.stand_id,
                row.turnaround_id,
                row.severity,
                row.confidence,
                row.status,
                row.timestamp_seconds,
                row.created_at.isoformat(),
            ]
        )
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "report.export",
        "safety_alert_report",
        None,
        new_state={"format": "csv", "severity": severity, "row_count": len(rows)},
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aeroramp-alerts.csv"},
    )


@router.get("/evidence/{alert_id}/{asset}")
def get_evidence(
    alert_id: str,
    asset: str,
    request: Request,
    db: DbSession,
    context: Annotated[AuthContext, Depends(require_permission("alerts.read"))],
) -> FileResponse:
    alert = _ensure_tenant(db.get(SafetyAlert, alert_id), context)
    path_value = alert.evidence_snapshot_path if asset == "snapshot" else alert.evidence_clip_path if asset == "clip" else None
    if not path_value:
        raise HTTPException(status_code=404, detail="Evidence asset not available")
    path = Path(path_value).resolve()
    if settings.evidence_dir.resolve() not in path.parents:
        raise HTTPException(status_code=403, detail="Invalid evidence path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing")
    request_id, ip = _audit_request(request)
    record_audit(
        db,
        context.organization_id,
        context.user.id,
        "evidence.access",
        "safety_alert",
        alert.id,
        new_state={"asset": asset},
        request_id=request_id,
        ip_metadata=ip,
    )
    db.commit()
    return FileResponse(path)
