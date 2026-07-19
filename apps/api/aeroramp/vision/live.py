from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2

from aeroramp.vision.detectors import build_detector
from aeroramp.vision.tracker import CentroidTracker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LiveMetrics:
    connected: bool = False
    reconnects: int = 0
    frames_read: int = 0
    frames_processed: int = 0
    dropped_frames: int = 0
    last_frame_at: float | None = None
    processing_fps: float = 0.0


class LiveStreamProcessor:
    """RTSP/local-stream processing loop with reconnect and measurable frame sampling."""

    def __init__(self, source: str, detector_backend: str = "motion", inference_fps: float = 4.0, reconnect_delay: float = 2.0) -> None:
        self.source = source
        self.detector = build_detector(detector_backend)
        self.tracker = CentroidTracker()
        self.inference_fps = inference_fps
        self.reconnect_delay = reconnect_delay
        self.metrics = LiveMetrics()
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self, on_result: Callable[[dict[str, Any]], None]) -> None:
        started = time.perf_counter()
        while not self._stop:
            capture = cv2.VideoCapture(self.source)
            if not capture.isOpened():
                self.metrics.connected = False
                self.metrics.reconnects += 1
                time.sleep(self.reconnect_delay)
                continue
            self.metrics.connected = True
            source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
            sample_every = max(1, round(source_fps / max(self.inference_fps, 0.1)))
            frame_index = 0
            while not self._stop:
                ok, frame = capture.read()
                if not ok:
                    break
                self.metrics.frames_read += 1
                self.metrics.last_frame_at = time.time()
                if frame_index % sample_every:
                    self.metrics.dropped_frames += 1
                    frame_index += 1
                    continue
                timestamp_seconds = frame_index / source_fps
                detections = self.detector.detect(frame)
                tracks = self.tracker.update(detections, timestamp_seconds)
                self.metrics.frames_processed += 1
                self.metrics.processing_fps = self.metrics.frames_processed / max(time.perf_counter() - started, 1e-9)
                on_result({"timestamp_seconds": timestamp_seconds, "detections": detections, "tracks": tracks, "metrics": self.metrics})
                frame_index += 1
            capture.release()
            self.metrics.connected = False
            if not self._stop:
                self.metrics.reconnects += 1
                time.sleep(self.reconnect_delay)
