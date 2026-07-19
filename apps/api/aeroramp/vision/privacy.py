from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from aeroramp.vision.types import TrackState

PERSON_CLASSES = {"person", "passenger", "ramp_worker", "driver", "marshalling_personnel"}


def blur_polygon(frame: np.ndarray, polygon: list[list[float]]) -> np.ndarray:
    if len(polygon) < 3:
        return frame
    points = np.array(polygon, dtype=np.int32)
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    blurred = cv2.GaussianBlur(frame, (51, 51), 0)
    output = frame.copy()
    output[mask > 0] = blurred[mask > 0]
    return output


def blur_person_tracks(frame: np.ndarray, tracks: list[TrackState]) -> np.ndarray:
    output = frame.copy()
    height, width = output.shape[:2]
    for track in tracks:
        if track.class_name not in PERSON_CLASSES or not track.points:
            continue
        x1, y1, x2, y2 = (int(value) for value in track.latest.bbox)
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 - x1 < 3 or y2 - y1 < 3:
            continue
        roi = output[y1:y2, x1:x2]
        kernel_width = max(3, min(51, ((roi.shape[1] // 3) * 2) + 1))
        kernel_height = max(3, min(51, ((roi.shape[0] // 3) * 2) + 1))
        output[y1:y2, x1:x2] = cv2.GaussianBlur(
            roi, (kernel_width, kernel_height), 0
        )
    return output


def apply_privacy(
    frame: np.ndarray,
    tracks: list[TrackState],
    zones: list[dict[str, Any]],
    anonymize_persons: bool,
) -> tuple[np.ndarray, bool]:
    output = frame.copy()
    applied = False
    for zone in zones:
        if zone.get("zone_type") != "privacy_mask":
            continue
        polygon = zone.get("polygon") or []
        if len(polygon) >= 3:
            output = blur_polygon(output, polygon)
            applied = True
    if anonymize_persons and any(track.class_name in PERSON_CLASSES for track in tracks):
        output = blur_person_tracks(output, tracks)
        applied = True
    return output, applied
