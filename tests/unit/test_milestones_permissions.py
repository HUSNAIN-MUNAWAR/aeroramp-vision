from aeroramp.core.permissions import has_permission
from aeroramp.vision.milestones import MilestoneRule, TurnaroundMilestoneEngine, evaluate_readiness
from aeroramp.vision.types import TrackPoint, TrackState


def test_milestone_confidence_and_readiness() -> None:
    track = TrackState(1, "aircraft", [
        TrackPoint(0, (0, 0, 10, 10), (5, 5), 0.8),
        TrackPoint(2, (1, 0, 11, 10), (6, 5), 0.9),
        TrackPoint(4, (1, 0, 11, 10), (6, 5), 0.95),
    ])
    engine = TurnaroundMilestoneEngine([MilestoneRule("aircraft_on_block", "aircraft", [[0, 0], [20, 0], [20, 20], [0, 20]], 2)])
    milestones = engine.evaluate([track])
    assert len(milestones) == 1
    assert 0.8 <= milestones[0].confidence <= 1
    readiness = evaluate_readiness({"aircraft_on_block", "service_vehicle_clear", "pushback_path_clear"}, 0)
    assert readiness["state"] == "ready_for_review"
    assert readiness["manual_confirmation_required"] is True


def test_permissions() -> None:
    assert has_permission("platform_admin", "users.manage")
    assert has_permission("ramp_safety_officer", "alerts.resolve")
    assert not has_permission("auditor", "alerts.resolve")
