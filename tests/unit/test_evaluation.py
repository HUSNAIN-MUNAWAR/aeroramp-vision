import pytest
from aeroramp.evaluation import evaluate_timed_events


def test_event_evaluation_matches_once_and_reports_timing() -> None:
    predictions = [
        {"event_type": "aircraft_on_block", "timestamp_seconds": 10.6, "confidence": 0.9},
        {"event_type": "aircraft_on_block", "timestamp_seconds": 10.8, "confidence": 0.4},
        {"event_type": "pushback_obstruction", "timestamp_seconds": 21.0, "confidence": 0.8},
    ]
    ground_truth = [
        {"event_type": "aircraft_on_block", "timestamp_seconds": 10.0},
        {"event_type": "pushback_obstruction", "timestamp_seconds": 20.0},
        {"event_type": "service_vehicle_present", "timestamp_seconds": 30.0},
    ]
    result = evaluate_timed_events(predictions, ground_truth, tolerance_seconds=1.5)
    assert result["true_positive"] == 2
    assert result["false_positive"] == 1
    assert result["false_negative"] == 1
    assert result["precision"] == 2 / 3
    assert result["recall"] == 2 / 3
    assert result["mean_absolute_timing_error_seconds"] == pytest.approx(0.8)
    assert result["per_type"]["aircraft_on_block"]["true_positive"] == 1


def test_event_evaluation_rejects_invalid_input() -> None:
    try:
        evaluate_timed_events([{"event_type": "x"}], [], tolerance_seconds=1)
    except ValueError as exc:
        assert "timestamp_seconds" in str(exc)
    else:
        raise AssertionError("Expected invalid event input to fail")
