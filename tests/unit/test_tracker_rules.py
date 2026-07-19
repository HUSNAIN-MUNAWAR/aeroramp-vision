from aeroramp.vision.rules import RuleConfig, SafetyRuleEngine, deduplication_key
from aeroramp.vision.tracker import CentroidTracker
from aeroramp.vision.types import Detection


def test_tracker_continuity_and_zone_debounce() -> None:
    tracker = CentroidTracker(max_distance=30, max_missed=2)
    rule = RuleConfig("rule-1", "person_in_restricted_zone", "high", "zone-1", [[0, 0], [100, 0], [100, 100], [0, 100]], {"classes": ["person"]}, debounce_seconds=1.0, cooldown_seconds=10)
    engine = SafetyRuleEngine([rule])
    alerts = []
    for timestamp, x in [(0.0, 10), (0.5, 15), (1.0, 20), (1.5, 25)]:
        tracks = tracker.update([Detection((x, 10, x + 10, 30), "person", 0.9)], timestamp)
        alerts.extend(engine.evaluate(tracks, timestamp))
    finished = tracker.finalize()
    assert len(finished) == 1
    assert len(finished[0].points) == 4
    assert len(alerts) == 1
    assert alerts[0].metadata["dwell_seconds"] >= 1.0
    assert deduplication_key(alerts[0], "job") == deduplication_key(alerts[0], "job")


def test_wrong_way_rule() -> None:
    tracker = CentroidTracker(max_distance=100)
    rule = RuleConfig("rule-2", "wrong_way", "medium", None, None, {"classes": ["service_vehicle"], "expected_angle_degrees": 0, "tolerance_degrees": 45, "minimum_distance_pixels": 10}, debounce_seconds=0, cooldown_seconds=10)
    engine = SafetyRuleEngine([rule])
    tracker.update([Detection((80, 10, 90, 20), "service_vehicle", 0.9)], 0)
    tracks = tracker.update([Detection((40, 10, 50, 20), "service_vehicle", 0.9)], 1)
    alerts = engine.evaluate(tracks, 1)
    assert len(alerts) == 1
    assert alerts[0].rule_type == "wrong_way"
