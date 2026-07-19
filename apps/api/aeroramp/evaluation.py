from __future__ import annotations

from collections import defaultdict
from typing import Any


def _event_type(event: dict[str, Any]) -> str:
    value = event.get("event_type") or event.get("milestone_type") or event.get("type")
    if not value:
        raise ValueError("Each event requires event_type, milestone_type, or type")
    return str(value)


def _event_time(event: dict[str, Any]) -> float:
    value = event.get("timestamp_seconds")
    if value is None:
        raise ValueError("Each event requires timestamp_seconds")
    return float(value)


def evaluate_timed_events(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    tolerance_seconds: float = 2.0,
) -> dict[str, Any]:
    """Match typed events one-to-one within a timestamp tolerance.

    The matcher is deterministic: predictions are considered by descending confidence and
    then by timestamp. Each ground-truth event can be used once. This is suitable for
    milestone and alert timing evaluation, not detection mAP.
    """

    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")
    remaining = set(range(len(ground_truth)))
    ordered_predictions = sorted(
        enumerate(predictions),
        key=lambda item: (
            -float(item[1].get("confidence", 1.0)),
            _event_time(item[1]),
            item[0],
        ),
    )
    matches: list[dict[str, Any]] = []
    unmatched_predictions: list[int] = []
    for prediction_index, prediction in ordered_predictions:
        prediction_type = _event_type(prediction)
        prediction_time = _event_time(prediction)
        candidates = [
            truth_index
            for truth_index in remaining
            if _event_type(ground_truth[truth_index]) == prediction_type
            and abs(_event_time(ground_truth[truth_index]) - prediction_time)
            <= tolerance_seconds
        ]
        if not candidates:
            unmatched_predictions.append(prediction_index)
            continue
        truth_index = min(
            candidates,
            key=lambda index: (
                abs(_event_time(ground_truth[index]) - prediction_time),
                _event_time(ground_truth[index]),
                index,
            ),
        )
        remaining.remove(truth_index)
        timing_error = prediction_time - _event_time(ground_truth[truth_index])
        matches.append(
            {
                "prediction_index": prediction_index,
                "ground_truth_index": truth_index,
                "event_type": prediction_type,
                "timing_error_seconds": timing_error,
                "absolute_timing_error_seconds": abs(timing_error),
            }
        )

    true_positive = len(matches)
    false_positive = len(unmatched_predictions)
    false_negative = len(remaining)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    mean_absolute_timing_error = (
        sum(float(match["absolute_timing_error_seconds"]) for match in matches) / true_positive
        if true_positive
        else None
    )

    types = sorted({_event_type(event) for event in predictions + ground_truth})
    per_type: dict[str, dict[str, Any]] = {}
    for event_type in types:
        type_matches = [match for match in matches if match["event_type"] == event_type]
        type_prediction_count = sum(1 for event in predictions if _event_type(event) == event_type)
        type_truth_count = sum(1 for event in ground_truth if _event_type(event) == event_type)
        type_tp = len(type_matches)
        type_fp = type_prediction_count - type_tp
        type_fn = type_truth_count - type_tp
        type_precision = type_tp / (type_tp + type_fp) if type_tp + type_fp else 0.0
        type_recall = type_tp / (type_tp + type_fn) if type_tp + type_fn else 0.0
        per_type[event_type] = {
            "true_positive": type_tp,
            "false_positive": type_fp,
            "false_negative": type_fn,
            "precision": type_precision,
            "recall": type_recall,
            "mean_absolute_timing_error_seconds": (
                sum(float(match["absolute_timing_error_seconds"]) for match in type_matches)
                / type_tp
                if type_tp
                else None
            ),
        }

    confusion: dict[str, int] = defaultdict(int)
    for prediction_index in unmatched_predictions:
        confusion[f"unmatched_prediction:{_event_type(predictions[prediction_index])}"] += 1
    for truth_index in remaining:
        confusion[f"missed_ground_truth:{_event_type(ground_truth[truth_index])}"] += 1

    return {
        "tolerance_seconds": tolerance_seconds,
        "prediction_count": len(predictions),
        "ground_truth_count": len(ground_truth),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_absolute_timing_error_seconds": mean_absolute_timing_error,
        "matches": sorted(matches, key=lambda match: int(match["prediction_index"])),
        "unmatched_prediction_indices": sorted(unmatched_predictions),
        "unmatched_ground_truth_indices": sorted(remaining),
        "per_type": per_type,
        "error_summary": dict(sorted(confusion.items())),
    }
