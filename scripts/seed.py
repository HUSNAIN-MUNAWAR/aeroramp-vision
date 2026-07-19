from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from aeroramp.core.security import hash_password
from aeroramp.db.base import Base
from aeroramp.db.models import (
    Airport,
    Camera,
    CameraZone,
    EdgeNode,
    ModelDeployment,
    ModelVersion,
    Organization,
    OrganizationMembership,
    SafetyRule,
    Stand,
    Terminal,
    Turnaround,
    User,
)
from aeroramp.db.session import SessionLocal, engine
from sqlalchemy import select


def seed(reset: bool = False) -> dict[str, str]:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalar(select(Organization).where(Organization.name == "AeroRamp Development Airport"))
        if existing:
            admin = db.scalar(select(User).where(User.email == "admin@aeroramp.local"))
            camera = db.scalar(select(Camera).where(Camera.organization_id == existing.id))
            turnaround = db.scalar(select(Turnaround).where(Turnaround.organization_id == existing.id))
            edge_node = db.scalar(select(EdgeNode).where(EdgeNode.organization_id == existing.id))
            return {
                "organization_id": existing.id,
                "admin_user_id": admin.id if admin else "",
                "camera_id": camera.id if camera else "",
                "turnaround_id": turnaround.id if turnaround else "",
                "edge_node_id": edge_node.id if edge_node else "",
            }

        org = Organization(name="AeroRamp Development Airport", organization_type="airport_operator")
        other_org = Organization(name="Second Tenant Safety Lab", organization_type="safety_audit")
        db.add_all([org, other_org])
        db.flush()
        users = [
            ("admin@aeroramp.local", "Development Administrator", "platform_admin"),
            ("safety@aeroramp.local", "Ramp Safety Officer", "ramp_safety_officer"),
            ("analyst@aeroramp.local", "Operations Analyst", "data_analyst"),
            ("auditor@aeroramp.local", "Read Only Auditor", "auditor"),
        ]
        for email, full_name, role in users:
            user = User(email=email, full_name=full_name, password_hash=hash_password("AeroRamp-Dev-2026!"))
            db.add(user)
            db.flush()
            db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=role))
        outsider = User(email="outsider@aeroramp.local", full_name="Second Tenant Admin", password_hash=hash_password("AeroRamp-Dev-2026!"))
        db.add(outsider)
        db.flush()
        db.add(OrganizationMembership(organization_id=other_org.id, user_id=outsider.id, role="airport_admin"))

        airport = Airport(organization_id=org.id, name="Development International Airport", iata_code="DEV", icao_code="DVLP", timezone="UTC")
        db.add(airport)
        db.flush()
        terminal = Terminal(organization_id=org.id, airport_id=airport.id, name="Terminal 1")
        db.add(terminal)
        db.flush()
        stands = [
            Stand(organization_id=org.id, airport_id=airport.id, terminal_id=terminal.id, code="A12", status="occupied", layout={"x": 80, "y": 80, "width": 480, "height": 210}),
            Stand(organization_id=org.id, airport_id=airport.id, terminal_id=terminal.id, code="A13", status="available", layout={"x": 620, "y": 80, "width": 480, "height": 210}),
            Stand(organization_id=org.id, airport_id=airport.id, terminal_id=terminal.id, code="A14", status="maintenance", layout={"x": 1160, "y": 80, "width": 480, "height": 210}),
        ]
        db.add_all(stands)
        db.flush()
        camera_a = Camera(organization_id=org.id, airport_id=airport.id, stand_id=stands[0].id, name="A12 Ramp Overview", source_mode="upload", camera_type="fixed", resolution_width=640, resolution_height=360, frame_rate=12, timezone="UTC", status="active", calibration_state="calibrated_image_space", processing_profile={"inference_fps": 6, "tracker_max_distance": 110, "min_area": 120}, retention_settings={"raw_video_days": 7, "evidence_days": 90})
        camera_b = Camera(organization_id=org.id, airport_id=airport.id, stand_id=stands[1].id, name="A13 Pushback View", source_mode="simulated_live", camera_type="fixed", resolution_width=640, resolution_height=360, frame_rate=12, timezone="UTC", status="degraded", calibration_state="calibration_required", processing_profile={"inference_fps": 4})
        db.add_all([camera_a, camera_b])
        db.flush()
        envelope = CameraZone(organization_id=org.id, camera_id=camera_a.id, stand_id=stands[0].id, name="Aircraft Safety Envelope", zone_type="aircraft_safety_envelope", polygon=[[170, 90], [540, 90], [540, 290], [170, 290]], severity="high", allowed_classes=["aircraft", "service_vehicle"], forbidden_classes=["person"], rule_configuration={"minimum_presence_seconds": 1.0}, version=1)
        pushback = CameraZone(organization_id=org.id, camera_id=camera_a.id, stand_id=stands[0].id, name="Pushback Route", zone_type="pushback_path", polygon=[[40, 210], [610, 210], [610, 330], [40, 330]], severity="high", allowed_classes=["aircraft", "pushback_tug"], forbidden_classes=["person", "service_vehicle"], rule_configuration={"minimum_presence_seconds": 1.0}, version=1)
        service = CameraZone(organization_id=org.id, camera_id=camera_a.id, stand_id=stands[0].id, name="Service Zone", zone_type="service_zone", polygon=[[250, 200], [520, 200], [520, 320], [250, 320]], severity="medium", allowed_classes=["service_vehicle"], forbidden_classes=[], rule_configuration={"minimum_dwell_seconds": 1.0}, version=1)
        db.add_all([envelope, pushback, service])
        db.flush()
        db.add_all([
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=envelope.id, name="Generic motion inside public-demo envelope", rule_type="restricted_zone_entry", severity="medium", config={"classes": ["moving_object"], "public_dataset_demo": True}, cooldown_seconds=6, debounce_seconds=1.0, version=1),
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=pushback.id, name="Generic motion in public-demo pushback route", rule_type="pushback_path_obstruction", severity="medium", config={"classes": ["moving_object"], "public_dataset_demo": True}, cooldown_seconds=6, debounce_seconds=1.0, version=1),
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=envelope.id, name="Potential person entry into aircraft envelope", rule_type="person_in_restricted_zone", severity="high", config={"classes": ["person"]}, cooldown_seconds=6, debounce_seconds=1.0, version=1),
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=pushback.id, name="Possible pushback route obstruction", rule_type="pushback_path_obstruction", severity="high", config={"classes": ["person", "service_vehicle"]}, cooldown_seconds=6, debounce_seconds=1.0, version=1),
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=service.id, name="Equipment left in service zone", rule_type="equipment_left_behind", severity="medium", config={"classes": ["service_vehicle"], "stationary_distance_pixels": 4, "dwell_seconds": 2.5}, cooldown_seconds=8, debounce_seconds=0.5, version=1),
            SafetyRule(organization_id=org.id, camera_id=camera_a.id, zone_id=None, name="Candidate near-miss", rule_type="candidate_near_miss", severity="high", config={"classes": ["person", "service_vehicle"], "distance_threshold_pixels": 55, "time_threshold_seconds": 1.5}, cooldown_seconds=8, debounce_seconds=0, version=1),
        ])
        now = datetime.now(UTC)
        turnaround = Turnaround(organization_id=org.id, airport_id=airport.id, stand_id=stands[0].id, airline_code="AR", flight_number="ARV101", aircraft_registration="N-DEMO", aircraft_type="A320-simulated", scheduled_arrival=now - timedelta(minutes=25), scheduled_departure=now + timedelta(minutes=25), status="aircraft_approaching", manual_review_state="not_reviewed")
        db.add(turnaround)
        motion_model = ModelVersion(
            organization_id=org.id,
            name="OpenCV Motion Baseline",
            version="1.0.0",
            framework="OpenCV",
            input_resolution="native",
            class_list=["moving_object"],
            validation_metrics={},
            deployment_status="deployed",
            safe_serialization=True,
        )
        fixture_model = ModelVersion(
            organization_id=org.id,
            name="Synthetic Fixture Color Detector",
            version="1.0.0",
            framework="OpenCV",
            input_resolution="640x360",
            class_list=["aircraft", "service_vehicle", "person"],
            validation_metrics={},
            deployment_status="test_only",
            safe_serialization=True,
        )
        db.add_all([motion_model, fixture_model])
        db.flush()
        db.add(
            ModelDeployment(
                organization_id=org.id,
                model_version_id=motion_model.id,
                camera_id=camera_a.id,
                backend="pytorch_cpu",
                status="active",
                configuration={"detector_backend": "motion", "inference_fps": 6},
                deployed_by_id=(
                    db.scalar(select(User.id).where(User.email == "admin@aeroramp.local")) or ""
                ),
            )
        )
        edge_node = EdgeNode(
            organization_id=org.id,
            name="Development Edge Node",
            status="offline",
            configuration_version=1,
            health={},
            api_key_hash=hash_password("edge-development-key"),
        )
        db.add(edge_node)
        db.commit()
        return {
            "organization_id": org.id,
            "admin_user_id": (
                db.scalar(select(User.id).where(User.email == "admin@aeroramp.local")) or ""
            ),
            "camera_id": camera_a.id,
            "turnaround_id": turnaround.id,
            "edge_node_id": edge_node.id,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    print(seed(reset=args.reset))
