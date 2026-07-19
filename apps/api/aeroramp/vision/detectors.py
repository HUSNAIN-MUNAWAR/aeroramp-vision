from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from aeroramp.vision.types import Detection


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError


class MotionDetector(Detector):
    """CPU development baseline that detects moving foreground regions.

    It intentionally emits only ``moving_object`` and never claims airport-specific
    equipment classes. Production deployments should register a validated airport model.
    """

    def __init__(self, min_area: int = 450) -> None:
        self.min_area = min_area
        self.background = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=28, detectShadows=False
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        mask = self.background.apply(frame)
        mask = cv2.medianBlur(mask, 5)
        kernel: np.ndarray = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        frame_area = float(frame.shape[0] * frame.shape[1])
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area or area > frame_area * 0.75:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            confidence = min(0.95, 0.45 + area / max(frame_area * 0.08, 1.0))
            detections.append(Detection((x, y, x + w, y + h), "moving_object", confidence))
        return detections


class SyntheticColorDetector(Detector):
    """Deterministic detector for generated test fixtures.

    Blue objects are aircraft, yellow objects are service vehicles, red objects are
    anonymous persons. This backend is never selected automatically for user video.
    """

    RANGES: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "aircraft": (np.array([95, 100, 80]), np.array([135, 255, 255])),
        "service_vehicle": (np.array([20, 100, 100]), np.array([40, 255, 255])),
        "person": (np.array([0, 120, 100]), np.array([10, 255, 255])),
    }

    def detect(self, frame: np.ndarray) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        output: list[Detection] = []
        for class_name, (lower, upper) in self.RANGES.items():
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if cv2.contourArea(contour) < 80:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                output.append(Detection((x, y, x + w, y + h), class_name, 0.98))
        return output


class YoloDetector(Detector):
    """Optional Ultralytics adapter for supported generic pretrained classes."""

    def __init__(self, checkpoint: str | Path = "yolo11n.pt", confidence: float = 0.3) -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install the 'yolo' optional dependency to use this backend") from exc
        self.model = YOLO(str(checkpoint))
        self.confidence = confidence

    def detect(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.predict(frame, conf=self.confidence, verbose=False)[0]
        names: dict[int, str] = result.names
        allowed = {"person", "car", "bus", "truck", "airplane"}
        detections: list[Detection] = []
        for box in result.boxes:
            class_name = names[int(box.cls.item())]
            if class_name not in allowed:
                continue
            mapped = "aircraft" if class_name == "airplane" else class_name
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            detections.append(Detection((x1, y1, x2, y2), mapped, float(box.conf.item())))
        return detections


def build_detector(name: str, config: dict[str, Any] | None = None) -> Detector:
    config = config or {}
    if name == "motion":
        return MotionDetector(min_area=int(config.get("min_area", 450)))
    if name == "synthetic_color":
        return SyntheticColorDetector()
    if name == "yolo":
        return YoloDetector(config.get("checkpoint", "yolo11n.pt"), float(config.get("confidence", 0.3)))
    raise ValueError(f"Unsupported detector backend: {name}")
